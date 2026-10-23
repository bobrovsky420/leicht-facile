"""Changing the settings from the command line (docs/configuration.md):

- `leichtfacile setup` asks for a model endpoint and saves it as `[endpoints.<name>]`,
  its key in the `.env` next to the config file;
- `leichtfacile endpoint list | use | remove` shows and switches the saved endpoints;
- `leichtfacile config show | path | set | unset | edit` covers every other setting.

Each change is checked together with every other source before it is written, and
tomlkit keeps the file's comments and order. Any OpenAI-compatible endpoint works; a
preset (config.PRESETS) fills in what is known about one.
"""

from __future__ import annotations

import getpass
import os
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Callable, MutableMapping
from functools import reduce
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import tomlkit
from pydantic import SecretStr

from leichtfacile import config
from leichtfacile.config import ENDPOINT_NAME, PRESETS, SECRETS, SECTIONS, ConfigError

_PLAIN = re.compile(r"[\w.:/@+=,{}\[\]-]*")
HEADER = (
    "# Leicht·Facile settings (docs/configuration.md). `leichtfacile config show --defaults`\n"
    "# prints every setting with its default and meaning.\n"
)


def list_models(base_url: str, api_key: str) -> list[str]:
    """The endpoint's model names (GET /models), with the client's User-Agent: some
    gateways refuse requests without one."""
    import openai

    from leichtfacile.llm.client import USER_AGENT

    client = openai.OpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=15.0,
        max_retries=0,
        default_headers={"User-Agent": USER_AGENT},
    )
    return sorted(m.id for m in client.models.list())


# -- setup ------------------------------------------------------------------------------


def run_setup(
    *,
    preset: str | None = None,
    name: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    api_key_env: str | None = None,
    model: str | None = None,
    judge: str | None = None,
    force: bool = False,
    ask: Callable[[str], str] = input,
    ask_secret: Callable[[str], str] = getpass.getpass,
    models: Callable[[str, str], list[str]] = list_models,
    say: Callable[[str], None] = print,
) -> int:
    """Ask for what the arguments leave open, save the endpoint in the config file and
    use it. Nothing is asked when the address, the key and the model are given (or come
    from the preset). 0 when it is saved."""
    path = config.config_file()
    doc = read_document(path)
    values = PRESETS[preset].values if preset else {}
    known: dict[str, str] = values.get("models", {})
    scripted = bool(
        (base_url or values.get("url"))
        and (api_key or api_key_env or values.get("api_key"))
        and (model or known.get("writer"))
    )

    if preset is None and not scripted:
        choices = [*PRESETS, "other"]
        say("Which model endpoint should Leicht·Facile use?")
        for i, key in enumerate(choices, 1):
            label = PRESETS[key].label if key in PRESETS else "Another OpenAI-compatible endpoint"
            say(f"  {i}. {label}")
        answer = ask(f"Endpoint [1-{len(choices)}, Enter: 1]: ").strip() or "1"
        while not (answer.isdigit() and 1 <= int(answer) <= len(choices)):
            answer = ask(f"A number from 1 to {len(choices)}: ").strip()
        preset = None if choices[int(answer) - 1] == "other" else choices[int(answer) - 1]
        values = PRESETS[preset].values if preset else {}
        known = values.get("models", {})

    url = base_url or values.get("url", "")
    if not scripted and not base_url:
        url = _required(ask, "Address of the endpoint", url)

    default_name = preset or _name_for(url)
    if not (name or scripted):
        name = ask(f"Name for this endpoint (Enter: {default_name}): ").strip()
    name = name or default_name
    while not ENDPOINT_NAME.fullmatch(name):
        if scripted:
            raise ConfigError(f"endpoint name {name!r}: use lowercase letters, digits, - and _")
        name = ask("Name for this endpoint (lowercase letters, digits, - and _): ").strip()
    endpoints = doc.get("endpoints") or {}
    exists = name in endpoints and not force
    if exists and (scripted or not _yes(ask(f"Endpoint {name} exists. Update it? [y/N] "))):
        say(f"Nothing changed ({name} exists in {path}; --force updates it).")
        return 1

    # The key: named by a variable, stored in the .env next to the config file, or the
    # preset's own (a server of one's own takes any key).
    variable = api_key_env or values.get("api_key_env") or _variable_for(name)
    store = api_key
    found = config.secret_value(variable)
    if not (api_key or api_key_env or scripted):
        default = values.get("api_key")
        hint = (f" (Enter: {default})" if default
                else f" (Enter: keep the one in {variable})" if found else "")  # fmt: skip
        store = ask_secret(f"API key{hint}: ").strip()
        while not (store or default or found):
            store = ask_secret("API key (required): ").strip()
    named = bool(store or api_key_env or (found and not values.get("api_key")))
    key = store or (found[0] if found and named else values.get("api_key", ""))

    listed: list[str] = []
    if not scripted:
        try:
            listed = models(url, key)
        except Exception as exc:  # the address or the key may be wrong: ask anyway
            say(f"The endpoint's model list could not be read ({type(exc).__name__}).")
    if not model and not scripted:
        if listed:
            say("The endpoint lists these models:")
            for listed_name in listed[:40]:
                say(f"  - {listed_name}")
            if len(listed) > 40:
                say(f"  ... and {len(listed) - 40} more")
        only = listed[0] if len(listed) == 1 else ""
        model = _required(ask, "Model", known.get("writer") or only)
        if listed and model not in listed:
            say(f"Note: {model} is not in the endpoint's list.")
    model = model or known.get("writer", "")
    if judge is None:
        judge = known.get("judge") or ""
        if not scripted:
            automatic = judge or config.LLM(models=config.Models(writer=model)).judge_for(listed)
            judge = ask(f"Judge model (Enter: {automatic}): ").strip() or judge

    table = endpoints.get(name)
    if table is None:
        table = tomlkit.table()
        if "endpoints" not in doc:
            doc["endpoints"] = tomlkit.table(is_super_table=True)
        doc["endpoints"][name] = table
    _put(table, "preset", preset)
    _put(table, "url", url if url != values.get("url") else None)
    if named:
        table.pop("api_key", None)
        _put(table, "api_key_env", variable if variable != values.get("api_key_env") else None)
    chosen = table.get("models")
    chosen = chosen if isinstance(chosen, MutableMapping) else tomlkit.inline_table()
    _put(chosen, "writer", model if model != known.get("writer") else None)
    _put(chosen, "judge", judge if judge and judge != known.get("judge") else None)
    _put(table, "models", chosen or None)

    active = (doc.get("llm") or {}).get("endpoint")
    use = True
    if active and active != name and not scripted:
        use = not _no(ask(f"Use {name} from now on, instead of {active}? [Y/n] "))
    if use:
        set_key(doc, ["llm", "endpoint"], name)

    check(path, doc)
    secrets = path.parent / ".env"
    if store:
        save_secret(secrets, variable, store)
    write_document(path, doc)
    say(f"Saved the endpoint {name} to {path}{' (in use)' if use else ''}.")
    if store:
        say(f"Its key is in {secrets} as {variable}.")
    elif named:
        say(f"Its key comes from the variable {variable}.")
    if use and (other := overridden("llm.endpoint", path)):
        say(f"Note: {other} picks another endpoint and wins over the config file.")
    say("Check it with `leichtfacile check-llm`; start the app with `leichtfacile serve`.")
    return 0


def _required(ask: Callable[[str], str], label: str, default: str) -> str:
    prompt = f"{label} (Enter: {default}): " if default else f"{label}: "
    value = ask(prompt).strip() or default
    while not value:
        value = ask(f"{label} (required): ").strip()
    return value


def _yes(answer: str) -> bool:
    return answer.strip().lower() in ("y", "yes")


def _no(answer: str) -> bool:
    return answer.strip().lower() in ("n", "no")


def _variable_for(name: str) -> str:
    """The variable a saved endpoint's key goes into: local-gpu -> LOCAL_GPU_API_KEY."""
    return f"{name.upper().replace('-', '_')}_API_KEY"


def _name_for(url: str) -> str:
    """A name from the endpoint's host: api.example.org/v1 -> example, 127.0.0.1 -> local."""
    host = (urlsplit(url).hostname or "").lower()
    labels = [label for label in host.split(".") if label not in ("api", "www")]
    if not labels or host == "localhost" or host.replace(".", "").replace(":", "").isdigit():
        return "local"
    return re.sub(r"[^a-z0-9_-]", "-", labels[0]).strip("-") or "default"


def _put(table: MutableMapping[str, Any], key: str, value: Any) -> None:
    """Set a key, or remove it for None."""
    if value is None:
        table.pop(key, None)
    else:
        table[key] = value


# -- endpoint list | use | remove -------------------------------------------------------


def list_endpoints(*, say: Callable[[str], None] = print) -> int:
    flat = config.collect()
    names = sorted({key.split(".")[1] for key in flat if key.startswith("endpoints.")})
    if not names:
        say("No endpoint is saved: run `leichtfacile setup`.")
        return 0
    chosen = flat.get("llm.endpoint")
    active = chosen.value if chosen else names[0] if len(names) == 1 else None
    rows = []
    for name in names:
        prefix = f"endpoints.{name}."
        own = {k.removeprefix(prefix): v.value for k, v in flat.items() if k.startswith(prefix)}
        preset = PRESETS.get(own.get("preset", ""), config.Preset(""))
        defaults = config.flatten(preset.values, "")
        url = own.get("url") or getattr(defaults.get("url"), "value", "")
        writer = own.get("models.writer") or getattr(defaults.get("models.writer"), "value", "")
        rows.append(("*" if name == active else " ", name, url, writer))
    names, urls = (max(len(row[i]) for row in rows) for i in (1, 2))
    for mark, name, url, writer in rows:
        say(f"{mark} {name:<{names}}  {url:<{urls}}  {writer}".rstrip())
    if chosen and active:
        say(f"In use: {active} ({_label(chosen.source)}).")
    return 0


def use_endpoint(name: str, *, path: Path, say: Callable[[str], None] = print) -> int:
    doc = read_document(path)
    set_key(doc, ["llm", "endpoint"], name)
    save(path, doc)
    say(f"In use: {name} ({path}).")
    if other := overridden("llm.endpoint", path):
        say(f"Note: {other} picks another endpoint and wins over {path}.")
    return 0


def remove_endpoint(name: str, *, path: Path, say: Callable[[str], None] = print) -> int:
    doc = read_document(path)
    endpoints = doc.get("endpoints")
    if not isinstance(endpoints, MutableMapping) or name not in endpoints:
        say(f"No endpoint {name} in {path}.")
        return 1
    rest = [other for other in endpoints if other != name]
    llm = doc.get("llm")
    if isinstance(llm, MutableMapping) and llm.get("endpoint") == name:
        if len(rest) > 1:
            say(f"{name} is in use: switch first, `leichtfacile endpoint use <name>`.")
            return 1
        del llm["endpoint"]
        if rest:
            say(f"In use now: {rest[0]}, the only one left.")
    del endpoints[name]
    if not rest:
        del doc["endpoints"]
    save(path, doc)
    say(f"Removed the endpoint {name} from {path}.")
    return 0


# -- config show | path | set | unset | edit ---------------------------------------------


def show(*, say: Callable[[str], None] = print) -> int:
    """Every setting in use, its value and its source."""
    loaded = config.load(strict=False)
    say(f"config file:  {config.config_file()}{_missing(config.config_file())}")
    say(f"this folder:  {config.PROJECT_FILE.resolve()}{_missing(config.PROJECT_FILE)}")
    say(f"keys (.env):  {', '.join(f'{p.resolve()}{_missing(p)}' for p in config.env_files())}")
    rows = []
    for section, model in SECTIONS.items():
        for key, _ in config.fields(model):
            full = f"{section}.{key}"
            value = reduce(getattr, full.split("."), loaded.settings)
            item = loaded.flat.get(full)
            rows.append((full, _shown(full, value), _label(item.source) if item else "default"))
    keys = max(len(row[0]) for row in rows)
    shown = min(48, max(len(row[1]) for row in rows))
    say("")
    for key, value, source in rows:
        say(f"{key:<{keys}}  {value:<{shown}}  {source}")
    if loaded.problems:
        say("")
        say("Not ready to call the model:")
        for problem in loaded.problems:
            say(f"- {problem}")
    return 0


def set_value(path: Path, key: str, raw: str, *, say: Callable[[str], None] = print) -> int:
    """Set a key to a value as TOML reads it (8001, true, ["understand"]), else to the
    text as it is."""
    parts = _parts(key)
    value = parse_value(raw)
    try:
        save(path, _with(path, parts, value))
    except ConfigError:
        if isinstance(value, str):
            raise
        save(path, _with(path, parts, raw))  # a model named 8 or true is still a name
    say(f"{key} set in {path}.")
    if other := overridden(key, path):
        say(f"Note: {other} sets it too and wins over {path}.")
    return 0


def unset_value(path: Path, key: str, *, say: Callable[[str], None] = print) -> int:
    parts = _parts(key)
    doc = read_document(path)
    node: Any = doc
    for part in parts[:-1]:
        node = node.get(part)
        if not isinstance(node, MutableMapping):
            break
    if not isinstance(node, MutableMapping) or parts[-1] not in node:
        say(f"{key} is not set in {path}.")
        return 1
    del node[parts[-1]]
    save(path, doc)
    say(f"{key} removed from {path}.")
    return 0


def edit(
    path: Path,
    *,
    run: Callable[[list[str]], Any] = subprocess.run,
    ask: Callable[[str], str] = input,
    say: Callable[[str], None] = print,
) -> int:
    """Open the file in the editor; check it once the editor closes."""
    if not path.exists():
        write_private(path, HEADER)
    while True:
        run([*editor(), str(path)])
        try:
            config.load(strict=False)
        except ConfigError as exc:
            say(str(exc))
            if _no(ask("Edit again? [Y/n] ")):
                return 1
            continue
        say(f"{path}: valid.")
        return 0


def editor() -> list[str]:
    """VISUAL or EDITOR, else the system's plain text editor."""
    for variable in ("VISUAL", "EDITOR"):
        if command := os.environ.get(variable, "").strip():
            words = [w.strip('"') for w in shlex.split(command, posix=os.name != "nt")]
            return [shutil.which(words[0]) or words[0], *words[1:]]
    if sys.platform == "win32":
        return ["notepad"]
    if sys.platform == "darwin":
        return ["open", "-W", "-t"]
    for name in ("nano", "vi"):
        if found := shutil.which(name):
            return [found]
    raise ConfigError("No editor found: set EDITOR, or edit the file yourself.")


# -- files -------------------------------------------------------------------------------


def read_document(path: Path) -> tomlkit.TOMLDocument:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return tomlkit.document()
    try:
        return tomlkit.parse(text)
    except tomlkit.exceptions.ParseError as exc:
        raise ConfigError(f"{path}: {exc}") from None


def check(path: Path, doc: tomlkit.TOMLDocument) -> None:
    """Refuse a file that would leave the settings invalid, with every other source."""
    config.load(strict=False, replace={path: doc.unwrap()})


def save(path: Path, doc: tomlkit.TOMLDocument) -> None:
    check(path, doc)
    write_document(path, doc)


def write_document(path: Path, doc: tomlkit.TOMLDocument) -> None:
    text = re.sub(r"\n{3,}", "\n\n", tomlkit.dumps(doc)).lstrip("\n")
    if not path.exists() and not text.startswith("#"):
        text = HEADER + "\n" + text
    write_private(path, text)


def write_private(path: Path, text: str) -> None:
    """Write a file readable by its owner alone where the system supports it (it may
    hold a key)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    if os.name == "posix":  # a file that existed keeps its mode through O_TRUNC
        os.chmod(path, 0o600)


def save_secret(path: Path, name: str, value: str) -> None:
    """Set one variable in a .env file, keeping its other lines."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else [
        "# Keys for Leicht·Facile, named by api_key_env in config.toml. Nothing else goes here."
    ]  # fmt: skip
    entry = f"{name}={_dotenv(value)}"
    pattern = re.compile(rf"\s*(export\s+)?{re.escape(name)}\s*=")
    for i, line in enumerate(lines):
        if pattern.match(line):
            lines[i] = entry
            break
    else:
        lines.append(entry)
    write_private(path, "\n".join(lines) + "\n")


def set_key(doc: MutableMapping[str, Any], parts: list[str], value: Any) -> None:
    node = doc
    for i, part in enumerate(parts[:-1]):
        child = node.get(part)
        if child is None:
            if part == "models":
                child = tomlkit.inline_table()
            else:
                child = tomlkit.table(is_super_table=(i == 0 and part == "endpoints"))
            node[part] = child
        elif not isinstance(child, MutableMapping):
            raise ConfigError(f"{'.'.join(parts[: i + 1])} is a value, not a table")
        node = child
    node[parts[-1]] = value


def parse_value(raw: str) -> Any:
    """A value as TOML reads it (8001, true, ["understand"], "text"), else the text."""
    try:
        return tomllib.loads(f"v = {raw}")["v"]
    except tomllib.TOMLDecodeError:
        return raw


def overridden(key: str, path: Path) -> str | None:
    """The source that wins over `path` for this key, if any."""
    item = config.collect().get(key)
    return _label(item.source) if item and item.source != str(path) else None


def _with(path: Path, parts: list[str], value: Any) -> tomlkit.TOMLDocument:
    doc = read_document(path)
    set_key(doc, parts, value)
    return doc


def _parts(key: str) -> list[str]:
    parts = key.strip().split(".")
    if len(parts) < 2 or not all(parts):
        raise ConfigError(f"{key!r}: name a setting as section.key (server.port); "
                          "`leichtfacile config show` lists them")  # fmt: skip
    return parts


def _shown(key: str, value: Any) -> str:
    if key in SECRETS or isinstance(value, SecretStr):
        secret = value.get_secret_value() if isinstance(value, SecretStr) else ""
        return "" if not secret else "****" + secret[-4:] if len(secret) > 11 else "****"
    if value is None or value == "":
        return ""
    if isinstance(value, str | Path):
        return str(value)
    return config.toml_value(value)


def _label(source: str) -> str:
    if source == str(config.config_file()):
        return "config file"
    if source == str(config.PROJECT_FILE):
        return f"./{config.PROJECT_FILE}"
    return source


def _missing(path: Path) -> str:
    return "" if path.exists() else " (none)"


def _dotenv(value: str) -> str:
    """A value as .env reads it back unchanged: bare when plain, else in single quotes
    (taken literally), else in double quotes with the backslashes and quotes escaped."""
    if _PLAIN.fullmatch(value):
        return value
    if "'" not in value:
        return f"'{value}'"
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
