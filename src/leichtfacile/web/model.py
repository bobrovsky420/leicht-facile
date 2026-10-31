"""The model page (`/model`, docs/ui-design.md §5.9): the presets in three groups
(Switzerland, this computer, clouds for public documents only), each with its provider,
where the text goes, the cost per page and whether it is ready; the key of the chosen
preset's provider; a check of the key and a test call; and, folded away, a preset of the
user's own on the chosen provider.

Plain forms: every action is a POST to `/model` with an `action` field, so the page
works without JavaScript. The page changes the settings only on the machine the app
runs on (`server.host`, or `server.published_on` in a container, bound to loopback): on
a published server everyone shares one login, so there it shows the choice and nothing
else. A source that wins over the
config file (`leichtfacile.toml`, a variable) locks the choice too. A key goes into
the `.env` next to the config file (`configure.save_secret`) and is never shown again.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse

from leichtfacile import config, configure
from leichtfacile.config import Available, ConfigError
from leichtfacile.llm.client import LLMError
from leichtfacile.llm.registry import Registry
from leichtfacile.web.i18n import Translator
from leichtfacile.web.pages import _render, translator

log = logging.getLogger(__name__)
router = APIRouter()
GROUPS = ("ch", "local", "cloud")
THINK_STAGES = ("understand", "write", "judge", "repair")
TEST_QUESTION = "Wie viel ist 17 + 25? Antworte nur mit der Zahl."
NEW = "new:"  # the value of a model a local server lists: new:<provider>:<model>


def page_shown(settings: config.Settings) -> bool:
    """Whether the page and its link are shown: not when an organisation offers one
    preset alone (`llm.offer`), since there is nothing to choose."""
    return len(settings.llm.offer) != 1


@router.get("/model", response_class=HTMLResponse)
def model_page(request: Request, saved: str | None = None) -> HTMLResponse:
    state = request.app.state
    if not page_shown(state.settings):
        raise HTTPException(404, "the model is set in the settings")
    t = translator(request)
    message = t("model.saved", name=saved) if saved else None
    return _page(request, t, message=message)


@router.post("/model", response_class=HTMLResponse)
async def model_action(request: Request):
    """Use a preset (with its key), check a key, make a test call, or save a preset of
    the user's own: `action` says which."""
    state = request.app.state
    if not page_shown(state.settings):
        raise HTTPException(404, "the model is set in the settings")
    t = translator(request)
    form = {key: str(value) for key, value in (await request.form()).items()}
    if not _editable(state)[0]:
        return _page(request, t, error=t("model.readonly"), status_code=403, form=form)
    action = form.get("action", "use")
    try:
        outcome = await run_in_threadpool(_act, state, t, action, form)
    except ConfigError as exc:
        return _page(request, t, error=str(exc), status_code=400, form=form)
    if outcome.get("saved"):
        return RedirectResponse(f"/model?saved={outcome['saved']}", status_code=303)
    if outcome.get("error"):
        return _page(request, t, error=outcome["error"], status_code=400, form=form)
    return _page(request, t, message=outcome.get("message"), form=form)


# -- the page ----------------------------------------------------------------------------


def _page(
    request: Request,
    t: Translator,
    *,
    message: str | None = None,
    error: str | None = None,
    status_code: int = 200,
    form: dict[str, str] | None = None,
) -> HTMLResponse:
    state = request.app.state
    registry: Registry = state.registry
    editable, locked_by = _editable(state)
    form = form or {}
    chosen = form.get("preset") or registry.in_use
    return _render(
        request,
        "model.html",
        status_code,
        t=t,
        message=message,
        error=error,
        groups=_groups(registry, t, chosen),
        editable=editable,
        locked_by=locked_by,
        think_stages=THINK_STAGES,
        form=form,
        section="model",
    )


def _editable(state) -> tuple[bool, str | None]:
    """Whether the page may change the choice, and what locks it otherwise: a server
    beyond this machine, or a source that wins over the config file."""
    if not state.settings.server.bound_to_loopback:
        return False, None
    winner = configure.overridden("llm.preset", config.config_file())
    return winner is None, winner


def _groups(registry: Registry, t: Translator, chosen: str) -> list[dict[str, Any]]:
    """The presets by group with their status, the local servers' models among them."""
    entries: dict[str, list[dict[str, Any]]] = {key: [] for key in GROUPS}
    available = registry.available()
    for item in available:
        entries[_group_of(item.location)].append(_entry(item, t, chosen, registry.in_use))
    for provider, table in _discoverable(registry).items():
        label = str(table.get("label") or provider)
        models = registry.discover(provider)
        if models is None:
            entries["local"].append(
                _row(
                    "",
                    label,
                    provider,
                    label,
                    desc=t("model.not_running.desc"),
                    status="not_running",
                    status_text=t("model.status.not_running"),
                )
            )
            continue
        used = {item.writer for item in available if item.provider == provider}
        for model in models:
            if model in used:
                continue
            value = f"{NEW}{provider}:{model}"
            entries["local"].append(
                _row(
                    value,
                    model,
                    provider,
                    label,
                    desc=_desc(t, "local", "any", None),
                    status="running",
                    status_text=t("model.status.running"),
                    selected=value == chosen,
                )
            )
    return [
        {"key": key, "title": t(f"model.group.{key}"), "entries": entries[key]}
        for key in GROUPS
        if entries[key]
    ]


def _group_of(location: str) -> str:
    return location if location in ("ch", "local") else "cloud"


def _row(
    value: str,
    label: str,
    provider: str,
    provider_label: str,
    *,
    desc: str,
    status: str,
    status_text: str,
    selected: bool = False,
    in_use: bool = False,
    key: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "value": value,
        "label": label,
        "provider": provider,
        "provider_label": provider_label,
        "desc": desc,
        "status": status,
        "status_text": status_text,
        "selectable": bool(value),
        "selected": selected,
        "in_use": in_use,
        "key": key,
    }


def _entry(item: Available, t: Translator, chosen: str, in_use: str) -> dict[str, Any]:
    if item.ready:
        status, text = "ready", t("model.status.ready")
    elif not item.has_key and len(item.missing) == 1:
        status, text = "needs_key", t("model.status.needs_key")
    else:
        status, text = "missing", t("model.status.missing", what="; ".join(item.missing))
    key = {"has_key": item.has_key, "key_url": item.key_url} if item.key_variable else None
    return _row(
        item.name,
        item.label,
        item.provider,
        item.provider_label,
        desc=_desc(t, item.location, item.documents, item.cost_per_page),
        status=status,
        status_text=text,
        selected=item.name == chosen,
        in_use=item.name == in_use,
        key=key,
    )


def _desc(t: Translator, location: str, documents: str, cost: float | None) -> str:
    parts = [t(f"model.location.{location}"), t(f"model.documents.{documents}")]
    if location != "local":
        cost_text = t("model.cost", usd=f"{cost:.2f}") if cost is not None else t("model.cost.none")
        parts.append(cost_text)
    return " · ".join(parts)


def _discoverable(registry: Registry) -> dict[str, dict[str, Any]]:
    """The providers that list their own models (`discover = true`), by name."""
    flat = config.collect()
    found = {}
    for name in config.provider_names(flat):
        table = config.provider_table(flat, name)
        if table.get("discover"):
            found[name] = table
    return found


# -- the actions -------------------------------------------------------------------------


def _act(state, t: Translator, action: str, form: dict[str, str]) -> dict[str, Any]:
    registry: Registry = state.registry
    value = form.get("preset", "").strip()
    if not value:
        return {"error": t("model.none_chosen")}
    if value.startswith(NEW):  # a model a local server lists, no preset yet
        provider, _, model = value.removeprefix(NEW).partition(":")
        name = None
    else:
        name, provider, model = value, _provider_of(registry, value), _writer_of(registry, value)
    path = config.config_file()
    table = config.provider_table(config.collect(), provider)
    variable = str(table.get("api_key_env") or configure._variable_for(provider))
    key = form.get(f"api_key_{provider}", "").strip()

    if action == "check":
        return _check(t, table, provider, key or _saved_key(table), model)
    if action == "test":
        return _test(registry, t, name)
    if action == "save":
        return _save_own(state, t, form, provider, model, path)

    # use: the key first, then the preset
    if key:
        configure.save_secret(path.parent / ".env", variable, key)
        if not table.get("api_key_env"):  # a server of one's own: its provider names it
            doc = configure.read_document(path)
            configure.set_key(doc, ["providers", provider, "api_key_env"], variable)
            configure.save(path, doc)
    if name is None:
        name = configure._slug(provider, model)
        configure.save_preset(
            path, name, {"provider": provider, "models": {"writer": model}}, say=log.info
        )
    else:
        configure.use_preset(name, path=path, say=log.info)
    _reload(state)
    if not registry.is_ready(name):
        return {"error": t("model.status.missing", what=_missing(registry, name))}
    return {"saved": name}


def _provider_of(registry: Registry, name: str) -> str:
    for item in registry.available():
        if item.name == name:
            return item.provider
    raise ConfigError(f"no preset {name!r}")


def _writer_of(registry: Registry, name: str) -> str:
    return next((item.writer for item in registry.available() if item.name == name), "")


def _missing(registry: Registry, name: str) -> str:
    found = (item for item in registry.available() if item.name == name)
    return next(("; ".join(item.missing) for item in found), "")


def _saved_key(table: dict[str, Any]) -> str:
    if table.get("api_key"):
        return str(table["api_key"])
    if table.get("api_key_env") and (found := config.secret_value(str(table["api_key_env"]))):
        return found[0]
    return ""


def _check(
    t: Translator, table: dict[str, Any], provider: str, key: str, model: str
) -> dict[str, Any]:
    label = str(table.get("label") or provider)
    if not key:
        return {"error": t("model.key.needed", provider=label)}
    try:
        models = configure.list_models(str(table.get("url", "")), key, table.get("headers"))
    except Exception as exc:  # the address or the key is wrong: the page says so
        return {"error": t("model.check.failed", provider=label, error=_error_text(exc))}
    key_name = "model.check.ok" if config.listed(model, models) else "model.check.unlisted"
    return {"message": t(key_name, provider=label, count=len(models), model=model)}


def _test(registry: Registry, t: Translator, name: str | None) -> dict[str, Any]:
    if name is None:
        return {"error": t("model.test.unsaved")}
    if not registry.is_ready(name):
        return {"error": t("model.test.not_ready", what=_missing(registry, name))}
    try:
        result = registry.client_for(name).complete(
            [{"role": "user", "content": TEST_QUESTION}], max_tokens=64, stage="check"
        )
    except LLMError as exc:
        return {"error": t("model.test.failed", error=str(exc)[:300])}
    usage = result.usage
    return {
        "message": t(
            "model.test.ok",
            answer=result.text.strip()[:60],
            ms=usage.latency_ms,
            tokens_in=usage.tokens_in,
            tokens_out=usage.tokens_out,
        )
    }


def _save_own(
    state, t: Translator, form: dict[str, str], provider: str, writer: str, path: Path
) -> dict[str, Any]:
    """The fine-tune panel: a preset of the user's own on the chosen provider."""
    name = form.get("name", "").strip().lower()
    if not name:
        return {"error": t("model.finetune.name_needed")}
    models: dict[str, str] = {"writer": form.get("writer", "").strip() or writer}
    for role in ("understand", "judge"):
        if form.get(role, "").strip():
            models[role] = form[role].strip()
    table: dict[str, Any] = {"provider": provider, "label": name, "models": models}
    table["thinking_stages"] = [stage for stage in THINK_STAGES if form.get(f"think_{stage}")]
    if form.get("timeout_s", "").strip():
        try:
            table["timeout_s"] = float(form["timeout_s"])
        except ValueError:
            return {"error": t("model.finetune.timeout_number")}
    configure.save_preset(path, name, table, say=log.info)
    _reload(state)
    return {"saved": name}


def _reload(state) -> None:
    """The settings changed on disk: the registry reads them again, and the app's
    settings follow (the pages read `state.settings`)."""
    state.registry.reload()
    state.settings = state.registry.settings


def _error_text(exc: Exception) -> str:
    status = getattr(exc, "status_code", None)
    return f"{type(exc).__name__} {status}" if status else type(exc).__name__
