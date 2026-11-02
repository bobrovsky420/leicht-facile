"""Workspaces (`server.workspaces`, off by default): the jobs a browser sees are those
of its workspace, a link anyone may open (docs/architecture.md §7).

A workspace is a random token of 128 bits (22 characters, URL-safe base64), carried in
the cookie `workspace` (a year, HttpOnly, SameSite=Lax, Secure over HTTPS) or, for
scripts, in the header `X-Workspace`. The store keeps the token's SHA-256 on every job
(`jobs.workspace`), never the token, so a copy of the database holds no working link.

`Workspaces` is ASGI middleware inside the hardening layer (web/security.py), so a
request that the login refuses gets no workspace: it reads the token, makes one for a
browser that has none and sets the cookie on the response. The routes read
`request.state.workspace` (the hash; None while workspaces are off) and
`request.state.workspace_token` (the token, for the drafts list's link and the API's
answer), through `current_workspace` and `current_token`.

`GET /w/{token}` makes the link's workspace the browser's; `POST /w/new` moves the
workspace's jobs under a new token, so the old link then opens an empty workspace. The
access line writes `/w/[token]` (web/observability.py).

Workspaces separate the jobs; the login protects them: a link works only for people who
get past the login. Jobs made outside every workspace (the command line, or before the
setting was switched on) belong to none and are listed again once it is off.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import cookie_parser
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from leichtfacile.web.security import is_open_path

if TYPE_CHECKING:
    from fastapi import FastAPI

    from leichtfacile.config import Settings

COOKIE = "workspace"
HEADER = "x-workspace"
TOKEN_BYTES = 16  # 128 bits
TOKEN = re.compile(r"[A-Za-z0-9_-]{22}")  # what token_urlsafe(16) writes
ONE_YEAR = 365 * 24 * 3600
router = APIRouter()


def install(app: FastAPI, settings: Settings) -> None:
    """Inside the hardening layer: called before `security.install`, since Starlette runs
    the middleware added last first."""
    app.add_middleware(Workspaces, settings=settings)


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def workspace_hash(token: str) -> str:
    """What the store keeps of a token."""
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def cookie_header(token: str, *, secure: bool) -> str:
    """The `Set-Cookie` value: a year, the whole site, no script access, not sent from
    another site's page, and over HTTPS only when the request came over HTTPS."""
    value = f"{COOKIE}={token}; Max-Age={ONE_YEAR}; Path=/; HttpOnly; SameSite=lax"
    return value + "; Secure" if secure else value


def current_workspace(request: Request) -> str | None:
    """The hash of the request's workspace, None while workspaces are off."""
    return getattr(request.state, "workspace", None)


def current_token(request: Request) -> str | None:
    """The request's token, None while workspaces are off."""
    return getattr(request.state, "workspace_token", None)


class Workspaces:
    """ASGI middleware: the workspace on `scope["state"]`, a cookie for a browser that
    has none (not for the probes and the static files, and not when the header named
    the workspace: a script keeps its own token)."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.enabled = settings.server.workspaces

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        state = scope.setdefault("state", {})
        if not self.enabled:
            state["workspace"] = state["workspace_token"] = None
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        given = headers.get(HEADER)
        if given is not None:
            if not TOKEN.fullmatch(given.strip()):
                response = JSONResponse(
                    {"detail": f"{HEADER}: not a workspace token"}, status_code=400
                )
                await response(scope, receive, send)
                return
            token, issue = given.strip(), False
        else:
            cookie = cookie_parser(headers.get("cookie", "")).get(COOKIE, "")
            token, issue = (cookie, False) if TOKEN.fullmatch(cookie) else (new_token(), True)
        state["workspace_token"] = token
        state["workspace"] = workspace_hash(token)
        if not issue or is_open_path(scope["path"]):
            await self.app(scope, receive, send)
            return
        cookie = cookie_header(token, secure=scope.get("scheme") == "https")

        async def send_with_cookie(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                # A route that sets the cookie itself (the link, New link) has the last
                # word: of two values for one cookie the browser keeps the later.
                if not any(v.startswith(f"{COOKIE}=") for v in headers.getlist("set-cookie")):
                    headers.append("set-cookie", cookie)
            await send(message)

        await self.app(scope, receive, send_with_cookie)


def _enabled(request: Request) -> None:
    if not request.app.state.settings.server.workspaces:
        raise HTTPException(404, "no workspaces on this server")


def _to_workspace(request: Request, token: str) -> RedirectResponse:
    """The drafts list, with the cookie for `token`."""
    response = RedirectResponse("/", status_code=303)
    response.headers.append(
        "set-cookie", cookie_header(token, secure=request.url.scheme == "https")
    )
    return response


@router.get("/w/{token}", include_in_schema=False)
def open_workspace(request: Request, token: str) -> RedirectResponse:
    """The link: that workspace is this browser's from now on, then the drafts list.
    A malformed token is 404; a well-formed one nobody has used opens an empty
    workspace, so the answer never says whether a workspace exists."""
    _enabled(request)
    if not TOKEN.fullmatch(token):
        raise HTTPException(404, "no such page")
    return _to_workspace(request, token)


@router.post("/w/new", include_in_schema=False)
def new_link(request: Request) -> RedirectResponse:
    """New link: the workspace's jobs move under a new token, this browser follows them,
    and the old link opens an empty workspace from now on."""
    _enabled(request)
    token = new_token()
    request.app.state.store.move_workspace(request.state.workspace, workspace_hash(token))
    return _to_workspace(request, token)
