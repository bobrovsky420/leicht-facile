"""The safe fetcher (ingest/fetch.py): redirects, the address check on every hop, the
connection pinned to the checked address, the budgets. No DNS and no network: the
resolver is a stub and the transport a mock, but for one server on 127.0.0.1 that
trickles its headers (the mock has no connection the deadline could shut)."""

from __future__ import annotations

import gzip
import ipaddress
import socket
import threading
import time
import tracemalloc
import zlib
from datetime import UTC

import httpx
import pytest

from leichtfacile.ingest.errors import FetchError, PrivateAddressError, UnknownHostError
from leichtfacile.ingest.fetch import (
    ACCEPT_ENCODING,
    MAX_REDIRECTS,
    USER_AGENT,
    fetch_url,
    is_public_address,
    resolve_host,
)
from tests.conftest import fetch_client

PUBLIC = "93.184.216.34"
PUBLIC_V6 = "2606:2800:220:1:248:1893:25c8:1946"
NAMES = {
    "www.example.ch": [PUBLIC],
    "cdn.example.ch": [PUBLIC_V6, PUBLIC],
    "intranet.example.ch": ["10.1.2.3"],
    "both.example.ch": [PUBLIC, "192.168.1.9"],  # one public and one private answer
}


def resolve(host: str, port: int) -> list[str]:
    if host in NAMES:
        return list(NAMES[host])
    try:
        ipaddress.ip_address(host)
    except ValueError:
        raise UnknownHostError(host) from None
    return [host]


def _client(handler) -> httpx.Client:
    return fetch_client(handler)


def _page(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200, content=b"<html></html>", headers={"content-type": "text/html; charset=utf-8"}
    )


def test_fetch_follows_redirects_and_sends_user_agent():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/old":
            return httpx.Response(301, headers={"location": "https://www.example.ch/new"})
        return _page(request)

    resource = fetch_url("https://www.example.ch/old", client=_client(handler), resolve=resolve)
    assert resource.final_url == "https://www.example.ch/new"
    assert resource.media_type == "text/html"
    assert resource.charset == "utf-8"
    assert resource.content == b"<html></html>"
    assert resource.fetched_at.tzinfo == UTC
    assert [r.url.path for r in seen] == ["/old", "/new"]
    assert all(r.headers["user-agent"] == USER_AGENT for r in seen)
    assert USER_AGENT.startswith("leicht-facile/")


def test_the_connection_is_pinned_to_the_checked_address():
    """The request goes to the resolved address; the name travels in the Host header and
    as the TLS server name; the connection is closed after the hop. So a DNS answer that
    changes between the check and the connect (rebinding) changes nothing."""
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _page(request)

    fetch_url("https://www.example.ch:8443/a?b=1", client=_client(handler), resolve=resolve)
    (request,) = seen
    assert request.url == httpx.URL(f"https://{PUBLIC}:8443/a?b=1")
    assert request.headers["host"] == "www.example.ch:8443"
    assert request.headers["connection"] == "close"
    assert request.extensions["sni_hostname"] == "www.example.ch"


def test_a_relative_redirect_is_resolved_against_the_name_not_the_address():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/x/a":
            return httpx.Response(302, headers={"location": "../b"})
        return _page(request)

    resource = fetch_url("https://www.example.ch/x/a", client=_client(handler), resolve=resolve)
    assert resource.final_url == "https://www.example.ch/b"


@pytest.mark.parametrize(
    ("location", "host"),
    [
        ("http://169.254.169.254/latest/meta-data/", "169.254.169.254"),  # cloud metadata
        ("http://127.0.0.1:8000/api/v1/jobs", "127.0.0.1"),  # the app itself
        ("http://intranet.example.ch/", "intranet.example.ch"),  # a name that resolves inside
        ("http://both.example.ch/", "both.example.ch"),  # one of its answers is private
        ("http://[::ffff:10.0.0.1]/", "::ffff:10.0.0.1"),  # IPv4 inside an IPv6 literal
    ],
)
def test_redirects_into_the_private_network_are_refused(location, host):
    fetched = []

    def handler(request: httpx.Request) -> httpx.Response:
        fetched.append(str(request.url))
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": location})
        return _page(request)

    with pytest.raises(PrivateAddressError) as info:
        fetch_url("https://www.example.ch/start", client=_client(handler), resolve=resolve)
    assert info.value.host == host
    assert "private network" in str(info.value)
    assert len(fetched) == 1, "the redirect target was never requested"


def test_the_first_url_is_checked_too():
    with pytest.raises(PrivateAddressError, match="private network"):
        fetch_url("http://intranet.example.ch/", client=_client(_page), resolve=resolve)
    with pytest.raises(UnknownHostError, match="cannot be found"):
        fetch_url("http://nowhere.example.ch/", client=_client(_page), resolve=resolve)


def test_allow_private_lifts_the_address_check_only():
    resource = fetch_url(
        "http://intranet.example.ch/", client=_client(_page), resolve=resolve, allow_private=True
    )
    assert resource.final_url == "http://intranet.example.ch/"

    def to_file(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "file:///etc/passwd"})

    with pytest.raises(FetchError, match="only http and https"):
        fetch_url(
            "http://intranet.example.ch/",
            client=_client(to_file),
            resolve=resolve,
            allow_private=True,
        )


def test_redirect_to_another_scheme_and_too_many_redirects():
    def to_ftp(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "ftp://www.example.ch/x"})

    with pytest.raises(FetchError, match="only http and https"):
        fetch_url("https://www.example.ch/", client=_client(to_ftp), resolve=resolve)

    hops = []

    def loop(request: httpx.Request) -> httpx.Response:
        hops.append(request.url.path)
        return httpx.Response(302, headers={"location": f"/hop{len(hops)}"})

    with pytest.raises(FetchError, match=f"more than {MAX_REDIRECTS} times"):
        fetch_url("https://www.example.ch/", client=_client(loop), resolve=resolve)
    assert len(hops) == MAX_REDIRECTS + 1


def test_the_next_address_is_tried_when_one_refuses_the_connection():
    tried = []

    def handler(request: httpx.Request) -> httpx.Response:
        tried.append(request.url.host)
        if request.url.host != PUBLIC:
            raise httpx.ConnectError("unreachable", request=request)
        return _page(request)

    resource = fetch_url("https://cdn.example.ch/", client=_client(handler), resolve=resolve)
    assert tried == [PUBLIC_V6, PUBLIC] and resource.content

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(FetchError, match="ConnectError: refused"):
        fetch_url("https://www.example.ch/", client=_client(refuse), resolve=resolve)


@pytest.mark.parametrize(
    ("handler", "message"),
    [
        (lambda r: httpx.Response(404), "HTTP 404"),
        (lambda r: httpx.Response(200, content=b"x" * 101), "larger than 100 bytes"),
        (
            lambda r: httpx.Response(200, content=b"x", headers={"content-length": "5000"}),
            "larger than 100 bytes",
        ),
    ],
)
def test_fetch_errors(handler, message):
    with pytest.raises(FetchError, match=message):
        fetch_url(
            "https://www.example.ch/", max_bytes=100, client=_client(handler), resolve=resolve
        )


def test_the_total_budget_ends_a_trickling_download():
    """One byte every few seconds stays under the read timeout; the budget for the whole
    fetch ends it (the audit's T2)."""

    class Trickle(httpx.SyncByteStream):
        def __iter__(self):
            for _ in range(20):
                time.sleep(0.02)
                yield b"x"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=Trickle(), headers={"content-type": "text/plain"})

    with pytest.raises(FetchError, match="took longer than 0.1 s"):
        fetch_url(
            "https://www.example.ch/", total_timeout_s=0.1, client=_client(handler), resolve=resolve
        )
    whole = fetch_url(
        "https://www.example.ch/", total_timeout_s=10, client=_client(handler), resolve=resolve
    )
    assert whole.content == b"x" * 20


def _encoded(body: bytes, coding: str) -> httpx.Response:
    return httpx.Response(
        200,
        headers={"content-type": "text/html", "content-encoding": coding},
        stream=httpx.ByteStream(body),
    )


def test_a_compressed_body_is_inflated_no_further_than_the_size_budget():
    """One coding, gzip or deflate (zlib-wrapped or raw), inflated chunk by chunk and
    never past `max_bytes` in memory; a coding on a coding and one the request did not
    ask for are refused. A 612-byte answer with `gzip, gzip` took 618 MB of memory
    before the limit was seen."""
    page = "<p>Prämie 1'500 Franken</p>".encode() * 200
    raw = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
    for coding, body in (
        ("gzip", gzip.compress(page)),
        ("deflate", zlib.compress(page)),
        ("deflate", raw.compress(page) + raw.flush()),
    ):
        resource = fetch_url(
            "https://www.example.ch/",
            client=_client(lambda r, b=body, c=coding: _encoded(b, c)),
            resolve=resolve,
        )
        assert resource.content == page, coding

    # 20 MB of zeros in about 20 kB: inflated up to the limit and no further
    bomb = zlib.compressobj(9, zlib.DEFLATED, 16 + zlib.MAX_WBITS)
    payload = b"".join(bomb.compress(bytes(1_000_000)) for _ in range(20)) + bomb.flush()
    tracemalloc.start()
    try:
        with pytest.raises(FetchError, match="larger than 1000000 bytes"):
            fetch_url(
                "https://www.example.ch/",
                max_bytes=1_000_000,
                client=_client(lambda r: _encoded(payload, "gzip")),
                resolve=resolve,
            )
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert peak < 8_000_000, f"{peak:,} bytes at the peak"

    for coding, message in (("gzip, gzip", "encoded more than once"), ("br", "encoded as br")):
        with pytest.raises(FetchError, match=message):
            fetch_url(
                "https://www.example.ch/",
                client=_client(lambda r, c=coding: _encoded(payload, c)),
                resolve=resolve,
            )
    seen: list[str] = []

    def page_handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["accept-encoding"])
        return _page(request)

    fetch_url("https://www.example.ch/", client=_client(page_handler), resolve=resolve)
    assert seen == [ACCEPT_ENCODING] == ["gzip, deflate"]


def test_the_total_budget_ends_a_server_that_trickles_its_headers():
    """The read timeout restarts with every byte, and the budget was asked only between
    the reads of the body: a server that sent its status line and headers a byte at a
    time held the fetch far past the budget (3 s ended after 44 s). The deadline shuts
    the connection; a real socket on 127.0.0.1, since the mock has none."""
    head = (
        b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nX-Pad: " + b"a" * 60
        + b"\r\nContent-Length: 2\r\n\r\nok"
    )  # fmt: skip
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    stop = threading.Event()

    def serve() -> None:
        conn, _ = server.accept()
        with conn:
            conn.recv(65536)
            for byte in head:  # about 10 s, each byte well within the read timeout
                if stop.wait(0.1):
                    return
                try:
                    conn.sendall(bytes([byte]))
                except OSError:
                    return

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    start = time.monotonic()
    try:
        with pytest.raises(FetchError, match="took longer than 1 s"):
            fetch_url(
                f"http://127.0.0.1:{server.getsockname()[1]}/",
                allow_private=True,
                timeout_s=0.5,
                total_timeout_s=1,
            )
    finally:
        stop.set()
        server.close()
        thread.join(5)
    assert time.monotonic() - start < 3


def test_the_total_budget_spans_the_redirect_chain():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        time.sleep(0.06)
        return httpx.Response(302, headers={"location": f"https://www.example.ch/hop{len(seen)}"})

    with pytest.raises(FetchError, match="took longer than 0.1 s"):
        fetch_url(
            "https://www.example.ch/", total_timeout_s=0.1, client=_client(handler), resolve=resolve
        )
    assert len(seen) <= 2, "no hop starts after the deadline"


def test_fetch_timeout_scheme_and_host():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(FetchError, match="timed out"):
        fetch_url("https://www.example.ch/", client=_client(handler), resolve=resolve)
    with pytest.raises(FetchError, match="only http and https"):
        fetch_url("file:///etc/passwd")
    with pytest.raises(FetchError, match="no host name"):
        fetch_url("http:///path")


@pytest.mark.parametrize(
    ("address", "public"),
    [
        ("8.8.8.8", True),
        ("2a00:1450:4001:80b::200e", True),
        ("10.0.0.1", False),
        ("172.16.5.5", False),
        ("192.168.1.1", False),
        ("127.0.0.1", False),
        ("::1", False),
        ("0.0.0.0", False),
        ("::", False),
        ("169.254.169.254", False),
        ("fe80::1", False),
        ("fc00::1", False),
        ("100.64.0.1", False),  # shared address space (carrier NAT)
        ("224.0.0.1", False),  # multicast
        ("ff02::1", False),
        ("240.0.0.1", False),  # reserved
        ("203.0.113.5", False),  # documentation
        ("::ffff:127.0.0.1", False),  # IPv4-mapped
        ("::ffff:8.8.8.8", True),
        ("64:ff9b::7f00:1", False),  # NAT64 of 127.0.0.1
        ("64:ff9b::808:808", True),  # NAT64 of 8.8.8.8
        # Missing from the tables of CPython 3.12.0 to 3.12.3; blocked on every version.
        ("192.0.0.8", False),  # IETF protocol assignments
        ("64:ff9b:1::7f00:1", False),  # local-use translation
        ("2002:7f00:1::", False),  # 6to4 of 127.0.0.1
        ("3fff::1", False),  # documentation
    ],
)
def test_is_public_address(address, public):
    assert is_public_address(address) is public


def test_resolve_host_uses_the_system_resolver():
    assert resolve_host("127.0.0.1", 80) == ["127.0.0.1"]
    assert set(resolve_host("localhost", 80)) <= {"127.0.0.1", "::1"}
    with pytest.raises(UnknownHostError, match="cannot be found"):
        resolve_host("no-such-host.invalid", 80)
