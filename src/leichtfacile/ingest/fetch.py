"""Downloading a URL a user submitted, safely (server-side request forgery).

The server fetches what a user submits, so a URL must not reach internal services: the
cloud metadata address, the app itself, the model server, an intranet host. Three
things make the fetch safe:

- Every hop is checked before it is fetched: the first URL and every redirect target.
  Only http and https; the host must resolve to public addresses, not private,
  loopback, link-local, reserved, multicast or unspecified ones, also not an IPv6
  address that carries such an IPv4 address (IPv4-mapped, NAT64). A redirect chain
  of more than `MAX_REDIRECTS` hops is refused.
- The connection goes to the address that was checked: the URL is rewritten to that
  address, the host name travels in the Host header and, for https, as the TLS server
  name (so the certificate is still checked against the name). A DNS answer that
  changes between the check and the connect (rebinding) cannot redirect the fetch.
- Every hop uses `Connection: close`, so a pooled connection to one address is never
  reused for another host name.
- Three budgets: `timeout_s` for each connect and each read; `total_timeout_s` for the
  whole fetch across its hops, asked between the reads and held by a watchdog that
  shuts the connection at the deadline (a server that trickles its headers or its body
  one byte at a time stays under the read timeout and would otherwise hold a thread
  for hours); `max_bytes` for the body after decoding, checked on the declared length
  and while the body arrives, inflated chunk by chunk never further than the budget
  (one content coding, gzip or deflate; a coding on a coding is refused).

`allow_private=True` lifts the address check for an intranet deployment that needs
internal pages (`server.allow_private_urls`); the hops are still walked and checked for
their scheme. `resolve` replaces the system resolver in tests.
"""

from __future__ import annotations

import contextlib
import ipaddress
import re
import socket
import threading
import time
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from leichtfacile import __version__
from leichtfacile.ingest.errors import FetchError, PrivateAddressError, UnknownHostError

USER_AGENT = f"leicht-facile/{__version__} (+https://leichtfacile.ch)"
DEFAULT_TIMEOUT_S = 30.0  # each connect, each read
DEFAULT_TOTAL_TIMEOUT_S = 120.0  # the whole fetch, redirects included
DEFAULT_MAX_BYTES = 15_000_000
MAX_REDIRECTS = 5
# The content codings a fetch asks for and reads, one at a time and inflated here under
# the size budget (`_Inflater`): httpx inflates a chunk whole and stacks codings, so a
# 612-byte answer with `Content-Encoding: gzip, gzip` became 300 MB in memory before the
# budget saw it.
ACCEPT_ENCODING = "gzip, deflate"
_CODINGS = frozenset({"gzip", "x-gzip", "deflate"})

Resolver = Callable[[str, int], list[str]]
"""`resolve(host, port)` gives the addresses of a host, or raises `UnknownHostError`."""

_CHARSET = re.compile(r"charset\s*=\s*[\"']?([\w.:-]+)", re.IGNORECASE)
_NAT64 = ipaddress.ip_network("64:ff9b::/96")  # RFC 6052: an IPv4 address in the low 32 bits
# Not global, but missing from the tables of CPython 3.12.0 to 3.12.3 (fixed in 3.12.4
# with CVE-2024-4032), so `is_global` alone would let them through there.
_NOT_GLOBAL = (
    ipaddress.ip_network("192.0.0.0/24"),  # IETF protocol assignments
    ipaddress.ip_network("64:ff9b:1::/48"),  # local-use IPv4/IPv6 translation
    ipaddress.ip_network("2002::/16"),  # 6to4: an IPv4 address in bits 16 to 48
    ipaddress.ip_network("3fff::/20"),  # documentation
)


@dataclass(frozen=True)
class FetchedResource:
    content: bytes
    content_type: str  # the Content-Type header as sent, possibly with parameters
    final_url: str  # after redirects
    fetched_at: datetime

    @property
    def media_type(self) -> str:
        return self.content_type.split(";", 1)[0].strip().lower()

    @property
    def charset(self) -> str | None:
        match = _CHARSET.search(self.content_type)
        return match.group(1) if match else None


def resolve_host(host: str, port: int) -> list[str]:
    """The addresses a host name resolves to, as the system gives them (an IP literal
    comes back as it is), without duplicates and zone ids."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise UnknownHostError(host) from exc
    addresses: list[str] = []
    for info in infos:
        address = str(info[4][0]).split("%")[0]
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise UnknownHostError(host)
    return addresses


def is_public_address(text: str) -> bool:
    """True for an address on the public internet. False for private, loopback,
    link-local, reserved, multicast and unspecified addresses, and for an IPv6 address
    that carries such an IPv4 address (IPv4-mapped `::ffff:a.b.c.d`, NAT64)."""
    address = ipaddress.ip_address(text)
    if isinstance(address, ipaddress.IPv6Address):
        inner = address.ipv4_mapped
        if inner is None and address in _NAT64:
            inner = ipaddress.IPv4Address(int(address) & 0xFFFFFFFF)
        if inner is not None:
            return is_public_address(str(inner))
    if any(address in network for network in _NOT_GLOBAL):
        return False
    return address.is_global and not address.is_multicast


def fetch_url(
    url: str,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    total_timeout_s: float = DEFAULT_TOTAL_TIMEOUT_S,
    max_bytes: int = DEFAULT_MAX_BYTES,
    client: httpx.Client | None = None,
    allow_private: bool = False,
    resolve: Resolver | None = None,
) -> FetchedResource:
    """Download a URL within the three budgets, following at most `MAX_REDIRECTS`
    redirects, every hop checked and pinned as the module docstring says.

    Raises `PrivateAddressError` for a hop into the private network (unless
    `allow_private`), `UnknownHostError` for a name that does not resolve, else
    `FetchError`."""
    http = client or httpx.Client()
    resolve = resolve or resolve_host
    target = _checked_url(url)
    budget = _Budget(time.monotonic() + total_timeout_s, total_timeout_s)
    try:
        for _ in range(MAX_REDIRECTS + 1):
            remaining = budget.remaining(target)
            result = _fetch_hop(
                http,
                target,
                timeout_s=min(timeout_s, remaining),
                budget=budget,
                max_bytes=max_bytes,
                allow_private=allow_private,
                resolve=resolve,
            )
            if isinstance(result, FetchedResource):
                return result
            target = _checked_url(str(target.join(result)))
        raise FetchError(f"{url} redirects more than {MAX_REDIRECTS} times")
    finally:
        if client is None:
            http.close()


@dataclass(frozen=True)
class _Budget:
    """The deadline of the whole fetch, asked before every hop and every chunk."""

    deadline: float
    total_s: float

    def remaining(self, target: httpx.URL) -> float:
        left = self.deadline - time.monotonic()
        if left <= 0:
            raise FetchError(f"{target} took longer than {self.total_s:g} s")
        return left


def _checked_url(url: str) -> httpx.URL:
    """The URL parsed, with the scheme and the host checked (every hop)."""
    try:
        parsed = httpx.URL(url)
    except (httpx.InvalidURL, TypeError) as exc:
        raise FetchError(f"invalid URL {url!r}") from exc
    if parsed.scheme not in ("http", "https"):
        raise FetchError(f"only http and https URLs can be fetched, not {url!r}")
    if not parsed.host:
        raise FetchError(f"the URL {url!r} has no host name")
    return parsed


def _fetch_hop(
    http: httpx.Client,
    target: httpx.URL,
    *,
    timeout_s: float,
    budget: _Budget,
    max_bytes: int,
    allow_private: bool,
    resolve: Resolver,
) -> FetchedResource | str:
    """One hop: the resource, or the Location of a redirect."""
    host = target.raw_host.decode("ascii")
    port = target.port or (443 if target.scheme == "https" else 80)
    addresses = resolve(host, port)
    if not allow_private:
        for address in addresses:
            if not is_public_address(address):
                raise PrivateAddressError(host, address)
    headers = {
        "User-Agent": USER_AGENT,
        "Host": target.netloc.decode("ascii"),
        "Connection": "close",
        "Accept-Encoding": ACCEPT_ENCODING,
    }
    extensions: dict[str, Any] = {"sni_hostname": host} if target.scheme == "https" else {}
    unreachable: httpx.ConnectError | None = None
    for address in addresses:  # the next address when one refuses the connection
        deadline = _Deadline(budget.deadline - time.monotonic())
        try:
            with (
                deadline,
                http.stream(
                    "GET",
                    target.copy_with(host=address),
                    headers=headers,
                    extensions={**extensions, "trace": deadline.trace},
                    follow_redirects=False,
                    timeout=timeout_s,
                ) as response,
            ):
                if response.has_redirect_location:
                    return response.headers["location"]
                response.raise_for_status()
                return FetchedResource(
                    content=_read_limited(response, target, max_bytes, budget),
                    content_type=response.headers.get("content-type", ""),
                    final_url=str(target),
                    fetched_at=datetime.now(UTC),
                )
        except httpx.HTTPError as exc:
            if deadline.fired:
                raise FetchError(f"{target} took longer than {budget.total_s:g} s") from exc
            if not isinstance(exc, httpx.ConnectError):
                raise _hop_error(target, exc, timeout_s) from exc
            unreachable = exc
    raise FetchError(f"GET {target} failed: ConnectError: {unreachable}") from unreachable


def _hop_error(target: httpx.URL, exc: httpx.HTTPError, timeout_s: float) -> FetchError:
    if isinstance(exc, httpx.HTTPStatusError):
        return FetchError(f"GET {target} failed: HTTP {exc.response.status_code}")
    if isinstance(exc, httpx.TimeoutException):
        return FetchError(f"GET {target} timed out after {timeout_s:g} s")
    return FetchError(f"GET {target} failed: {type(exc).__name__}: {exc}")


class _Deadline:
    """Shuts the hop's connection when the fetch's time is up. `_Budget` is asked between
    the reads of the body, and the read timeout restarts with every byte, so a server
    that trickled its status line and headers one byte at a time held the thread and an
    ingest slot far past the budget (3 s ended after 44 s). httpcore's trace of the
    connect and of the TLS handshake hands over the socket; a transport without
    httpcore (the tests' mock) has none to shut."""

    def __init__(self, seconds: float) -> None:
        self.fired = False
        self._socket: socket.socket | None = None
        self._lock = threading.Lock()
        self._timer = threading.Timer(max(seconds, 0.0), self._fire)
        self._timer.daemon = True

    def __enter__(self) -> _Deadline:
        self._timer.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._timer.cancel()

    def trace(self, event: str, info: dict[str, Any]) -> None:
        if event not in ("connection.connect_tcp.complete", "connection.start_tls.complete"):
            return
        stream = info.get("return_value")
        with self._lock:  # the TLS socket replaces the plain one it wraps
            self._socket = stream.get_extra_info("socket") if stream is not None else None
            if self.fired:
                self._shut()

    def _fire(self) -> None:
        with self._lock:
            self.fired = True
            self._shut()

    def _shut(self) -> None:
        if self._socket is not None:
            with contextlib.suppress(OSError):
                self._socket.shutdown(socket.SHUT_RDWR)


def _read_limited(
    response: httpx.Response, target: httpx.URL, max_bytes: int, budget: _Budget
) -> bytes:
    """The body, at most `max_bytes` after decoding, the budget asked before every raw
    chunk."""
    declared = response.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > max_bytes:
        raise FetchError(f"{target} is larger than {max_bytes} bytes")
    inflate = _inflater(response, target)
    body = bytearray()
    try:
        for chunk in response.iter_raw():
            budget.remaining(target)
            body += chunk if inflate is None else inflate(chunk, max_bytes + 1 - len(body))
            if len(body) > max_bytes:
                raise FetchError(f"{target} is larger than {max_bytes} bytes")
    except zlib.error as exc:
        raise FetchError(f"{target} could not be decoded ({exc})") from exc
    return bytes(body)


def _inflater(response: httpx.Response, target: httpx.URL) -> _Inflater | None:
    """The inflater for the response's content coding, None without one. One coding
    that the request asked for: a coding on a coding, or another one, is refused."""
    codings = [c.strip().lower() for c in response.headers.get("content-encoding", "").split(",")]
    codings = [c for c in codings if c and c != "identity"]
    if not codings:
        return None
    if len(codings) > 1:
        raise FetchError(f"{target} is encoded more than once ({', '.join(codings)})")
    if codings[0] not in _CODINGS:
        raise FetchError(f"{target} is encoded as {codings[0]}, which is not read here")
    return _Inflater()


class _Inflater:
    """Inflates a gzip or deflate body chunk by chunk, each call to at most `room` bytes
    (zlib's `max_length`; the input it did not get to waits in `unconsumed_tail`), so a
    compression bomb never grows past the size budget in memory. Deflate is wrapped in
    zlib as RFC 9110 says; raw deflate, which some servers send, is read too."""

    def __init__(self) -> None:
        self._zlib = zlib.decompressobj(32 + zlib.MAX_WBITS)  # a gzip or a zlib header
        self._fresh = True  # nothing read yet: raw deflate may still be tried

    def __call__(self, chunk: bytes, room: int) -> bytes:
        out = bytearray()
        data = chunk
        while data and len(out) < room:
            try:
                out += self._zlib.decompress(data, room - len(out))
            except zlib.error:
                if not self._fresh:
                    raise
                self._zlib = zlib.decompressobj(-zlib.MAX_WBITS)
                self._fresh = False
                continue
            self._fresh = False
            data = self._zlib.unconsumed_tail
        return bytes(out)
