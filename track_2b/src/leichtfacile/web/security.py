"""Cross-site request forgery: a guard for every state-changing request.

The forms and the JavaScript of the pages post to their own origin. A page on another
site that posts to this app (a hidden form that deletes a job, re-runs it or starts
model calls) is refused with 403 before any route runs. Today the app has no session,
so such a page only uses the victim's browser as a bridge into the intranet; behind
the login proxy the deployment plans (track_2b/docs/architecture.md §10) its session
cookie would make this classic CSRF, and the guard holds there too.

How a request is judged, in this order:

- `Sec-Fetch-Site`, which every current browser sends and a page cannot set: only
  `cross-site` is refused (`same-origin`, `same-site` and `none`, a typed address or a
  bookmark, pass).
- Without it, `Origin`: a browser sends it with every POST, so it must name this
  server (the `Host` the request came to; the scheme is left out because a proxy
  that ends TLS reports http inside). `null` (an opaque origin) is refused.
- A request with neither header is not from a browser (curl, the Python client, the
  tests) and passes: the API stays usable from scripts.

Only the unsafe methods are judged (POST, PUT, PATCH, DELETE); reads are never refused.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def is_cross_site(headers: Headers) -> bool:
    """True when the request comes from a page on another site (see the module docstring)."""
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
    """ASGI middleware: refuses unsafe requests from another site with 403."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and scope["method"] in UNSAFE_METHODS
            and is_cross_site(Headers(scope=scope))
        ):
            response = JSONResponse({"detail": "cross-site request refused"}, status_code=403)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
