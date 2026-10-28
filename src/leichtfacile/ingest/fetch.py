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
- Three budgets: `timeout_s` for each connect and each read, `total_timeout_s` for the
  whole fetch across its hops (a server that trickles one byte at a time stays under
  the read timeout and would otherwise hold a thread for hours), `max_bytes` for the
  body, checked on the declared length and again while it arrives.

`allow_private=True` lifts the address check for an intranet deployment that needs
internal pages (`server.allow_private_urls`); the hops are still walked and checked for
their scheme. `resolve` replaces the system resolver in tests.
"""

from __future__ import annotations

import ipaddress
import re
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from leichtfacile import __version__
from leichtfacile.ingest.errors import FetchError, PrivateAddressError, UnknownHostError

USER_AGENT = f"leicht-facile/{__version__} (+https://leichtfacile.ch)"
DEFAULT_TIMEOUT_S = 30.0  # each connect, each read
DEFAULT_TOTAL_TIMEOUT_S = 120.0  # the whole fetch, redirects included
DEFAULT_MAX_BYTES = 15_000_000
MAX_REDIRECTS = 5

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
    }
    extensions = {"sni_hostname": host} if target.scheme == "https" else {}
    unreachable: httpx.ConnectError | None = None
    for address in addresses:  # the next address when one refuses the connection
        try:
            with http.stream(
                "GET",
                target.copy_with(host=address),
                headers=headers,
                extensions=extensions,
                follow_redirects=False,
                timeout=timeout_s,
            ) as response:
                if response.has_redirect_location:
                    return response.headers["location"]
                response.raise_for_status()
                return FetchedResource(
                    content=_read_limited(response, target, max_bytes, budget),
                    content_type=response.headers.get("content-type", ""),
                    final_url=str(target),
                    fetched_at=datetime.now(UTC),
                )
        except httpx.ConnectError as exc:
            unreachable = exc
        except httpx.HTTPStatusError as exc:
            raise FetchError(f"GET {target} failed: HTTP {exc.response.status_code}") from exc
        except httpx.TimeoutException as exc:
            raise FetchError(f"GET {target} timed out after {timeout_s:g} s") from exc
        except httpx.HTTPError as exc:
            raise FetchError(f"GET {target} failed: {type(exc).__name__}: {exc}") from exc
    raise FetchError(f"GET {target} failed: ConnectError: {unreachable}") from unreachable


def _read_limited(
    response: httpx.Response, target: httpx.URL, max_bytes: int, budget: _Budget
) -> bytes:
    declared = response.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > max_bytes:
        raise FetchError(f"{target} is larger than {max_bytes} bytes")
    chunks: list[bytes] = []
    size = 0
    for chunk in response.iter_bytes():
        budget.remaining(target)
        size += len(chunk)
        if size > max_bytes:
            raise FetchError(f"{target} is larger than {max_bytes} bytes")
        chunks.append(chunk)
    return b"".join(chunks)
