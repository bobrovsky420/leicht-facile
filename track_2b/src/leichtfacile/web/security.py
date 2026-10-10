"""The hardening layer: everything that stands between the network and the routes.

Five pieces of ASGI middleware, installed by `install` in this order (the first named
sees a request first and a response last):

1. `SecurityHeaders`: a Content-Security-Policy with a nonce for the one inline script
   in base.html (`request.state.csp_nonce`), `frame-ancestors 'self'`, no plug-ins, no
   script from anywhere but this server; `X-Content-Type-Options`, `X-Frame-Options`,
   `Referrer-Policy` (nothing about a job's address leaves the site),
   `Permissions-Policy`. The API documentation pages load Swagger UI from a CDN with
   inline scripts and get the headers without the policy. HTTPS and its
   `Strict-Transport-Security` belong to the reverse proxy that ends TLS.
2. `RateLimitGuard`: at most `RATE_LIMIT_PER_MINUTE` writes (POST, PUT, PATCH, DELETE:
   submissions, model calls, saves, deletions) per client address in any minute, 429
   with `Retry-After` beyond; reads are never limited. In memory, per process.
3. `Authentication`, off unless configured (`Settings.auth_mode`):
   - `token`: `AUTH_TOKEN` is a shared secret. Browsers are asked for it with HTTP
     Basic (any user name, the token as the password); scripts send
     `Authorization: Bearer <token>`. Compared in constant time; a client with
     `AUTH_FAILURES_PER_MINUTE` wrong tries in a minute gets 429.
   - `proxy`: the reverse proxy logs the user in and names them in the header
     `AUTH_PROXY_HEADER` (`X-Forwarded-User`, `Remote-User`). The header is trusted
     only from the proxy's addresses (`AUTH_PROXY_FROM`); a request from elsewhere is
     403, one without the header 401. The user lands in `request.state.user`.
   The probes `/healthz` and `/readyz` and the static files need no login.
   `Settings` refuses to start the app published beyond the loopback interface
   (`BIND_HOST`) without one of the two.
4. `CrossSiteGuard`: a state-changing request from a page on another site is refused
   with 403 (cross-site request forgery), see its docstring.
5. `BodyLimit`: a request body over `MAX_BODY_BYTES` is refused with 413, by its
   `Content-Length` before a byte is read, else as soon as the count passes the limit
   while the route reads it; the 15 MB file limit in web/jobs.py then holds inside.

Every refusal is a small JSON body `{"detail": ...}`, as FastAPI's own errors are.
"""

from __future__ import annotations

import base64
import binascii
import hmac
import ipaddress
import math
import secrets
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from leichtfacile.web.jobs import MAX_FILE_BYTES

if TYPE_CHECKING:
    from fastapi import FastAPI

    from leichtfacile.config import Network, Settings

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# The file limit plus the other form fields and the multipart framing.
MAX_BODY_BYTES = MAX_FILE_BYTES + 1_000_000
AUTH_FAILURES_PER_MINUTE = 10
OPEN_PATHS = frozenset({"/healthz", "/readyz"})  # the probes: no login
OPEN_PREFIXES = ("/static/",)  # the interface's own files: no login, no data
DOCS_PATHS = frozenset({"/docs", "/docs/oauth2-redirect", "/redoc"})  # Swagger UI from a CDN
REALM = 'Basic realm="Leicht-Facile", charset="UTF-8"'

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'nonce-{nonce}'; "
    "style-src 'self' 'unsafe-inline'; "  # the templates set widths and margins inline
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-src 'self'; "  # the reader view inside the review page
    "frame-ancestors 'self'; "
    "form-action 'self'; "
    "base-uri 'self'; "
    "object-src 'none'"
)


def install(app: FastAPI, settings: Settings) -> None:
    """Put the layer in front of the routes. Starlette runs the middleware added last
    first, so the order here is the reverse of the module docstring's."""
    app.add_middleware(BodyLimit)
    app.add_middleware(CrossSiteGuard)
    app.add_middleware(Authentication, settings=settings)
    app.add_middleware(RateLimitGuard, settings=settings)
    app.add_middleware(SecurityHeaders)


async def _refuse(
    scope: Scope,
    receive: Receive,
    send: Send,
    status: int,
    detail: str,
    headers: dict[str, str] | None = None,
) -> None:
    response = JSONResponse({"detail": detail}, status_code=status, headers=headers)
    await response(scope, receive, send)


def _retry_after(wait_s: float) -> dict[str, str]:
    return {"Retry-After": str(max(1, math.ceil(wait_s)))}


# -- 1. Security headers ---------------------------------------------------------------


def security_headers(path: str, nonce: str) -> dict[str, str]:
    """The headers every response carries; the policy on all but the API docs pages."""
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "SAMEORIGIN",
        "Referrer-Policy": "same-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }
    if path not in DOCS_PATHS:
        headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY.format(nonce=nonce)
    return headers


class SecurityHeaders:
    """ASGI middleware: a nonce per request in `scope["state"]["csp_nonce"]` (the
    templates read it as `request.state.csp_nonce`), the headers on the response. A
    header the route set itself stays."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        nonce = secrets.token_urlsafe(16)
        scope.setdefault("state", {})["csp_nonce"] = nonce
        wanted = security_headers(scope["path"], nonce)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in wanted.items():
                    headers.setdefault(name, value)
            await send(message)

        await self.app(scope, receive, send_with_headers)


# -- 2. Rate limit -----------------------------------------------------------------------


class RateLimit:
    """At most `per_minute` events per key in any sliding minute. In memory, one
    process, safe across threads; `per_minute` 0 allows everything."""

    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic) -> None:
        self.per_minute = per_minute
        self._clock = clock
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def take(self, key: str) -> float:
        """0.0 when the event is allowed, and then it counts; else the seconds until the
        next one would be."""
        if self.per_minute <= 0:
            return 0.0
        now = self._clock()
        with self._lock:
            if len(self._events) > 1_000:
                self._forget_idle(now)
            events = self._events.setdefault(key, deque())
            while events and events[0] <= now - 60:
                events.popleft()
            if len(events) >= self.per_minute:
                return events[0] + 60 - now
            events.append(now)
            return 0.0

    def _forget_idle(self, now: float) -> None:
        for key in [k for k, e in self._events.items() if not e or e[-1] <= now - 60]:
            del self._events[key]


def _in_networks(address: str, networks: list[Network]) -> bool:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return False  # the test client's "testclient", a socket path
    return any(parsed in network for network in networks)


def client_address(scope: Scope, settings: Settings) -> str:
    """The client's address: the connection's, or, when the connection comes from the
    trusted reverse proxy, the one the proxy appended to `X-Forwarded-For`."""
    client = scope.get("client")
    peer = client[0] if client else "unknown"
    if settings.auth_proxy_header and _in_networks(peer, settings.proxy_networks):
        forwarded = Headers(scope=scope).get("x-forwarded-for", "")
        if forwarded.strip():
            return forwarded.rsplit(",", 1)[-1].strip() or peer
    return peer


class RateLimitGuard:
    """ASGI middleware: writes beyond the client's budget are refused with 429."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings
        self.limit = RateLimit(settings.rate_limit_per_minute)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] in UNSAFE_METHODS:
            wait = self.limit.take(client_address(scope, self.settings))
            if wait:
                await _refuse(scope, receive, send, 429, "too many requests", _retry_after(wait))
                return
        await self.app(scope, receive, send)


# -- 3. Authentication -------------------------------------------------------------------


def token_matches(authorization: str | None, token: str) -> bool:
    """True when the `Authorization` header carries the shared secret: `Bearer <token>`,
    or `Basic` with the token as the password and any user name."""
    if not authorization or not token:
        return False
    scheme, _, credentials = authorization.strip().partition(" ")
    credentials = credentials.strip()
    if scheme.lower() == "bearer":
        given = credentials
    elif scheme.lower() == "basic":
        try:
            decoded = base64.b64decode(credentials, validate=True).decode("utf-8")
        except (binascii.Error, ValueError):
            return False
        _, _, given = decoded.partition(":")
    else:
        return False
    return hmac.compare_digest(given.encode("utf-8"), token.encode("utf-8"))


def is_open_path(path: str) -> bool:
    return path in OPEN_PATHS or path.startswith(OPEN_PREFIXES)


class Authentication:
    """ASGI middleware: the login the settings ask for (module docstring, 3)."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings
        self.mode = settings.auth_mode
        self.failures = RateLimit(AUTH_FAILURES_PER_MINUTE)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self.mode == "none" or is_open_path(scope["path"]):
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        if self.mode == "token":
            if token_matches(headers.get("authorization"), self.settings.auth_token_value):
                await self.app(scope, receive, send)
                return
            wait = self.failures.take(client_address(scope, self.settings))
            if wait:
                await _refuse(
                    scope, receive, send, 429, "too many failed logins", _retry_after(wait)
                )
            else:
                await _refuse(
                    scope, receive, send, 401, "login required", {"WWW-Authenticate": REALM}
                )
            return
        # proxy: the connection must come from the proxy, and the proxy must name the user
        client = scope.get("client")
        peer = client[0] if client else ""
        if not _in_networks(peer, self.settings.proxy_networks):
            await _refuse(scope, receive, send, 403, "not from the trusted reverse proxy")
            return
        user = (headers.get(self.settings.auth_proxy_header or "") or "").strip()
        if not user:
            await _refuse(scope, receive, send, 401, "the reverse proxy sent no user")
            return
        scope.setdefault("state", {})["user"] = user
        await self.app(scope, receive, send)


# -- 4. Cross-site request forgery ----------------------------------------------------------


def is_cross_site(headers: Headers) -> bool:
    """True when the request comes from a page on another site, judged in this order:

    - `Sec-Fetch-Site`, which every current browser sends and a page cannot set: only
      `cross-site` is refused (`same-origin`, `same-site` and `none`, a typed address
      or a bookmark, pass).
    - Without it, `Origin`: a browser sends it with every POST, so it must name this
      server (the `Host` the request came to; the scheme is left out because a proxy
      that ends TLS reports http inside). `null` (an opaque origin) is refused.
    - A request with neither header is not from a browser (curl, the Python client,
      the tests) and passes: the API stays usable from scripts."""
    site = headers.get("sec-fetch-site")
    if site is not None:
        return site.strip().lower() == "cross-site"
    origin = headers.get("origin")
    if origin is None:
        return False
    origin = origin.strip()
    if origin.lower() == "null":
        return True
    host = headers.get("host", "")
    return urlsplit(origin).netloc.lower() != host.strip().lower()


class CrossSiteGuard:
    """ASGI middleware: refuses unsafe requests from another site with 403.

    The forms and the JavaScript of the pages post to their own origin. A page on
    another site that posts to this app (a hidden form that deletes a job, re-runs it
    or starts model calls) is refused before any route runs. Today the app has no
    session of its own, so such a page only uses the victim's browser as a bridge into
    the intranet; behind the login proxy of a deployment (track_2b/docs/architecture.md
    §10) the proxy's session cookie would make this classic CSRF, and the guard holds
    there too. Only the unsafe methods are judged; reads are never refused."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and scope["method"] in UNSAFE_METHODS
            and is_cross_site(Headers(scope=scope))
        ):
            await _refuse(scope, receive, send, 403, "cross-site request refused")
            return
        await self.app(scope, receive, send)


# -- 5. Body limit -------------------------------------------------------------------------


class BodyTooLarge(Exception):
    """Raised into the route's read of the body once the limit is passed; the 413 has
    gone out by then and whatever the route answers is dropped."""


class BodyLimit:
    """ASGI middleware: a request body over `max_bytes` is refused with 413."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        detail = f"the request body is larger than {self.max_bytes // 1_000_000} MB"
        declared = Headers(scope=scope).get("content-length", "").strip()
        if declared.isdigit() and int(declared) > self.max_bytes:
            await _refuse(scope, receive, send, 413, detail)
            return
        received = 0
        started = False  # the route began its response
        refused = False  # the 413 went out

        async def counted_receive() -> Message:
            nonlocal received, refused
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    if not started:
                        await _refuse(scope, receive, send, 413, detail)
                    refused = True
                    raise BodyTooLarge
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal started
            if refused:
                return  # the route's answer to its broken read: the client has the 413
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counted_receive, guarded_send)
        except BodyTooLarge:
            if not refused:  # pragma: no cover - the flag is set before the raise
                raise
