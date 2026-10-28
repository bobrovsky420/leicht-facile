"""Changing the settings from the command line (docs/configuration.md):

- `leichtfacile setup` asks for a provider, its key and a preset, saves a preset of the
  user's own as `[presets.<name>]` (and a server of their own as `[providers.<name>]`),
  the key in the `.env` next to the config file, and uses the preset;
- `leichtfacile preset list | use | remove` shows and switches the presets;
- `leichtfacile config show | path | set | unset | edit` covers every other setting.

The model page of the web app writes through the same helpers (`save_preset`,
`use_preset`, `save_secret`). Each change is checked together with every other source
before it is written, and tomlkit keeps the file's comments and order.
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
from leichtfacile.config import (
    IN_USE,
    NAME,
    PRESETS,
    SECRETS,
    ConfigError,
    preset_layer,
    preset_names,
    provider_names,
    provider_table,
)

_PLAIN = re.compile(r"[\w.:/@+=,{}\[\]-]*")
HEADER = (
    "# Leicht·Facile settings (docs/configuration.md). `leichtfacile config show --defaults`\n"
    "# prints every setting with its default and meaning.\n"
)
ANOTHER_SERVER = "Another OpenAI-compatible server"
ANOTHER_MODEL = "Another model the provider lists"


def list_models(
    base_url: str, api_key: str, headers: dict[str, str] | None = None, timeout_s: float = 15.0
) -> list[str]:
    """The provider's model names (GET /models), with the client's User-Agent (some
    gateways refuse requests without one) and the provider's own headers."""
    import openai

    from leichtfacile.llm.client import USER_AGENT

    client = openai.OpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=timeout_s,
        max_retries=0,
        default_headers={"User-Agent": USER_AGENT, **(headers or {})},
    )
    return sorted(m.id for m in client.models.list())


# -- setup ------------------------------------------------------------------------------


def run_setup(
    *,
    provider: str | None = None,
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
    models: Callable[..., list[str]] = list_models,
    say: Callable[[str], None] = print,
) -> int:
    """Ask for what the arguments leave open: the provider (or a preset, which names
    its provider), its key (nothing when the key's variable is set or the provider needs
    none), and the preset: one of the provider's, or a model the provider lists, saved
    as a preset of the user's own. A server of the user's own becomes a provider with
    its address. The key goes into the .env next to the config file, the preset into
    use. 0 when it is saved."""
    path = config.config_file()
    doc = read_document(path)
    flat = config.collect()

    # The provider: from the preset, named, a new server (--base-url), or asked.
    if preset is not None:
        if preset not in preset_names(flat):
            raise ConfigError(f"no preset {preset!r}; known: {', '.join(preset_names(flat))}")
        provider = str(preset_layer(flat, preset)["provider"].value)
    new_server = False
    if provider is None and base_url is None:
        offered = provider_names(flat)
        labels = [*(_provider_label(flat, key) for key in offered), ANOTHER_SERVER]
        index = _pick(ask, say, "Where should Leicht·Facile's model run?", labels, "Provider")
        provider = offered[index] if index < len(offered) else None
    if provider is None:
        new_server = True
        url = base_url or _required(ask, "Address of the server (OpenAI-compatible)", "")
        provider = name or _ask_name(ask, f"Name for this server (Enter: {_name_for(url)}): ",
                                     _name_for(url), scripted=bool(base_url and name))  # fmt: skip
        table: dict[str, Any] = {"url": url}
    else:
        if provider not in provider_names(flat):
            raise ConfigError(f"no provider {provider!r}; known: {', '.join(provider_names(flat))}")
        table = provider_table(flat, provider)
        url = base_url or str(table.get("url", ""))
    label = table.get("label") or provider

    # Nothing is asked when the provider, the key and the preset or model are given
    # or known: the key counts as known when its variable is set.
    variable = api_key_env or table.get("api_key_env") or _variable_for(provider)
    found = config.secret_value(variable)
    key_known = bool(api_key or api_key_env or table.get("api_key") or found)
    scripted = bool((base_url or not new_server) and key_known and (preset or model))

    # The key: named by a variable, stored in the .env next to the config file, or the
    # provider's own (a server of one's own takes any key).
    store = api_key
    if not (api_key or api_key_env or table.get("api_key") or (scripted and found)):
        hint = f" (Enter: keep the one in {variable})" if found else ""
        store = ask_secret(f"API key for {label}{hint}: ").strip()
        while not (store or found):
            store = ask_secret("API key (required): ").strip()
    named = bool(store or api_key_env or (found and not table.get("api_key")))
    key = store or (found[0] if found and named else str(table.get("api_key", "")))

    # The preset: given, one of the provider's, or a model the provider lists, saved
    # as a preset of the user's own. A key just entered is tried on the list as well, so
    # a wrong one shows now and not at the first draft.
    listed: list[str] = []
    if store or not (preset or model):
        try:
            listed = models(url, key, table.get("headers") or None)
        except Exception as exc:  # the address or the key may be wrong: go on anyway
            say(f"The provider's model list could not be read ({type(exc).__name__}).")
        else:
            say(f"{label} lists {len(listed)} models.")
    offered = [key for key in preset_names(flat)
               if str(preset_layer(flat, key)["provider"].value) == provider]  # fmt: skip
    if preset is None and model is None and offered:
        labels = [*(_preset_label(flat, key) for key in offered), ANOTHER_MODEL]
        index = _pick(ask, say, "Which model should Leicht·Facile use?", labels, "Model")
        if index < len(offered):
            preset = offered[index]
    if preset is None and model is None:
        for listed_name in listed[:40]:
            say(f"  - {listed_name}")
        if len(listed) > 40:
            say(f"  ... and {len(listed) - 40} more")
        model = _required(ask, "Model", listed[0] if len(listed) == 1 else "")
    if model and listed and model not in listed:
        say(f"Note: {model} is not in the provider's list.")

    # A preset of the user's own for a model: named after the server, or the provider
    # and the model. The provider's table and the preset's are updated with --force only.
    written = []
    if model:
        preset = provider if new_server else name or _slug(provider, model)
        exists = preset in (doc.get("presets") or {}) and not force
        if exists and (scripted or not _yes(ask(f"Preset {preset} exists. Update it? [y/N] "))):
            say(f"Nothing changed ({preset} exists in {path}; --force updates it).")
            return 1
        entry: dict[str, Any] = {"provider": provider, "models": {"writer": model}}
        if judge:
            entry["models"]["judge"] = judge
        _put_table(doc, ["presets", preset], entry)
        written.append(f"[presets.{preset}]")
    if new_server:
        entry = {"url": url}
        if named:
            entry["api_key_env"] = variable
        _put_table(doc, ["providers", provider], entry)
        written.append(f"[providers.{provider}]")
    elif named and variable != table.get("api_key_env"):
        set_key(doc, ["providers", provider, "api_key_env"], variable)
        written.append(f"[providers.{provider}]")
    assert preset is not None

    active = (doc.get("llm") or {}).get("preset")
    use = True
    if active and active != preset and not scripted:
        use = not _no(ask(f"Use {preset} from now on, instead of {active}? [Y/n] "))
    if use:
        set_key(doc, ["llm", "preset"], preset)

    check(path, doc)
    secrets = path.parent / ".env"
    if store:
        save_secret(secrets, variable, store)
    write_document(path, doc)
    what = f" ({', '.join(written)})" if written else ""
    say(f"{preset} is set up{' and in use' if use else ''}{what}: {path}.")
    if store:
        say(f"Its key is in {secrets} as {variable}.")
    elif named:
        say(f"Its key comes from the variable {variable}.")
    if use and (other := overridden("llm.preset", path)):
        say(f"Note: {other} picks another preset and wins over the config file.")
    say("Check it with `leichtfacile check-llm`; start the app with `leichtfacile serve`.")
    return 0


def _provider_label(flat: config.Flat, name: str) -> str:
    return str(provider_table(flat, name).get("label") or name)


def _preset_label(flat: config.Flat, name: str) -> str:
    layer = preset_layer(flat, name)
    label = layer.get("label")
    return str(label.value) if label is not None else name


def _pick(
    ask: Callable[[str], str], say: Callable[[str], None], question: str, labels: list[str],
    what: str,
) -> int:  # fmt: skip
    """The index of the option asked for by its number; Enter takes the first."""
    say(question)
    for i, label in enumerate(labels, 1):
        say(f"  {i}. {label}")
    answer = ask(f"{what} [1-{len(labels)}, Enter: 1]: ").strip() or "1"
    while not (answer.isdigit() and 1 <= int(answer) <= len(labels)):
        answer = ask(f"A number from 1 to {len(labels)}: ").strip()
    return int(answer) - 1


def _required(ask: Callable[[str], str], label: str, default: str) -> str:
    prompt = f"{label} (Enter: {default}): " if default else f"{label}: "
    value = ask(prompt).strip() or default
    while not value:
        value = ask(f"{label} (required): ").strip()
    return value


def _ask_name(ask: Callable[[str], str], prompt: str, default: str, *, scripted: bool) -> str:
    name = default if scripted else (ask(prompt).strip() or default)
    while not NAME.fullmatch(name):
        if scripted:
            raise ConfigError(f"name {name!r}: use lowercase letters, digits, - and _")
        name = ask("Name (lowercase letters, digits, - and _): ").strip()
    return name


def _yes(answer: str) -> bool:
    return answer.strip().lower() in ("y", "yes")


def _no(answer: str) -> bool:
    return answer.strip().lower() in ("n", "no")


def _variable_for(name: str) -> str:
    """The variable a provider's key goes into: local-gpu -> LOCAL_GPU_API_KEY."""
    return f"{name.upper().replace('-', '_')}_API_KEY"


def _name_for(url: str) -> str:
    """A name from the server's host: api.example.org/v1 -> example, 127.0.0.1 -> local."""
    host = (urlsplit(url).hostname or "").lower()
    labels = [label for label in host.split(".") if label not in ("api", "www")]
    if not labels or host == "localhost" or host.replace(".", "").replace(":", "").isdigit():
        return "local"
    return re.sub(r"[^a-z0-9_-]", "-", labels[0]).strip("-") or "default"


def _slug(provider: str, model: str) -> str:
    """A preset's name from its provider and model: ollama, qwen3.5:9b -> ollama-qwen3-5-9b."""
    slug = re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-")
    return f"{provider}-{slug}" if slug else provider


def _put_table(doc: MutableMapping[str, Any], parts: list[str], values: dict[str, Any]) -> None:
    """Set the keys of a table (made when missing), its other keys kept."""
    for key, value in values.items():
        if isinstance(value, dict):
            for inner, item in value.items():
                set_key(doc, [*parts, key, inner], item)
        else:
            set_key(doc, [*parts, key], value)


# -- the helpers the model page and `preset` share -----------------------------------------


def save_preset(
    path: Path,
    name: str,
    table: dict[str, Any],
    *,
    use: bool = True,
    say: Callable[[str], None] = print,
) -> None:
    """Write a preset of the user's own, `[presets.<name>]` with the given keys (its
    provider, models, label, request settings), checked with every other source, and
    use it."""
    if not NAME.fullmatch(name):
        raise ConfigError(f"preset name {name!r}: use lowercase letters, digits, - and _")
    doc = read_document(path)
    _put_table(doc, ["presets", name], table)
    if use:
        set_key(doc, ["llm", "preset"], name)
    save(path, doc)
    say(f"{name} is saved{' and in use' if use else ''} ({path}).")


def use_preset(name: str, *, path: Path, say: Callable[[str], None] = print) -> int:
    doc = read_document(path)
    set_key(doc, ["llm", "preset"], name)
    save(path, doc)
    say(f"In use: {name} ({path}).")
    if other := overridden("llm.preset", path):
        say(f"Note: {other} picks another preset and wins over {path}.")
    return 0


# -- preset list | use | remove --------------------------------------------------------------


def list_presets(*, say: Callable[[str], None] = print) -> int:
    """Every preset, shipped or the user's own: its label, its provider, its writer
    model and whether it is ready (else what it lacks); the one in use marked `*`."""
    loaded = config.load(strict=False)
    active = loaded.settings.llm.preset
    rows = [
        (
            "*" if item.name == active else " ",
            item.name,
            item.label,
            item.provider_label,
            item.writer or "-",
            "ready" if item.ready else "; ".join(item.missing),
        )
        for item in config.available()
    ]
    widths = [max(len(row[i]) for row in rows) for i in (1, 2, 3, 4)]
    for mark, name, label, provider, writer, status in rows:
        say(
            f"{mark} {name:<{widths[0]}}  {label:<{widths[1]}}  {provider:<{widths[2]}}  "
            f"{writer:<{widths[3]}}  {status}"
        )
    say(f"In use: {active} ({_label(loaded.flat['llm.preset'].source)}).")
    return 0


def remove_preset(name: str, *, path: Path, say: Callable[[str], None] = print) -> int:
    """Remove a preset of the user's own, or the user's table that extends a shipped
    preset (the shipped one stays). One that was in use leaves the choice to the
    first preset whose key is set, else the shipped default."""
    doc = read_document(path)
    presets = doc.get("presets")
    if not isinstance(presets, MutableMapping) or name not in presets:
        if name in PRESETS:
            say(f"{name} is a preset that ships with the app; nothing to remove in {path}.")
        else:
            say(f"No preset {name} in {path}.")
        return 1
    del presets[name]
    if not len(presets):
        del doc["presets"]
    llm = doc.get("llm")
    if isinstance(llm, MutableMapping) and llm.get("preset") == name and name not in PRESETS:
        del llm["preset"]
    save(path, doc)
    what = "the saved settings of the preset" if name in PRESETS else "the preset"
    say(f"Removed {what} {name} from {path}.")
    say(f"In use now: {config.load(strict=False).settings.llm.preset}.")
    return 0


# -- config show | path | set | unset | edit ---------------------------------------------


def show(*, say: Callable[[str], None] = print) -> int:
    """Every setting in use, its value and its source."""
    loaded = config.load(strict=False)
    say(f"config file:  {config.config_file()}{_missing(config.config_file())}")
    say(f"this folder:  {config.PROJECT_FILE.resolve()}{_missing(config.PROJECT_FILE)}")
    say(f"keys (.env):  {', '.join(f'{p.resolve()}{_missing(p)}' for p in config.env_files())}")
    rows = []
    for section, model in IN_USE.items():
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
            if part == "models" and parts[0] == "presets":
                child = tomlkit.inline_table()  # models = { writer = ..., judge = ... }
            else:
                child = tomlkit.table(is_super_table=(i == 0 and part in ("providers", "presets")))
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
