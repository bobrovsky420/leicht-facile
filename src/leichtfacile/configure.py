"""`leichtfacile setup`: asks for the model endpoint and writes the user's config file
(`config.config_file`), so that `leichtfacile serve` starts without a checkout or a
`.env`.

Any OpenAI-compatible endpoint works. A preset fills in what is known about one: its
address and, for Apertus, the model names and how the endpoint switches thinking
(.env.example has the same settings with their reasons). The model names otherwise come
from the endpoint's own list, so none are hard-coded here.
"""

from __future__ import annotations

import getpass
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from leichtfacile.config import config_file


@dataclass(frozen=True)
class Preset:
    label: str
    base_url: str = ""
    model: str = ""
    judge: str = ""
    api_key: str = ""  # a server of one's own takes any key
    settings: dict[str, str] = field(default_factory=dict)  # further variables


PRESETS: dict[str, Preset] = {
    "cscs": Preset(
        "Apertus on the CSCS inference API",
        "https://api.inference.cscs.ch/v1",
        "swiss-ai/Apertus-v1.5-8B",
        "swiss-ai/Apertus-v1.5-70B",
        settings={"LLM_THINKING_MODE": "model-suffix", "LLM_MAX_RETRIES": "8"},
    ),
    "publicai": Preset(
        "Apertus on the Public AI gateway (public documents only)",
        "https://api.publicai.co/v1",
        "swiss-ai/apertus-v1.5-8b",
        "swiss-ai/apertus-v1.5-70b",
        settings={
            "LLM_THINKING_MODE": "chat-template",
            "LLM_EXTRA_BODY": '{"cache": {"no-cache": true}}',
        },
    ),
    "local": Preset(
        "A server of your own (llama.cpp :8080, Ollama :11434, vLLM)",
        "http://127.0.0.1:8080/v1",
        api_key="local",
    ),
    "openai": Preset("OpenAI", "https://api.openai.com/v1"),
    "mistral": Preset("Mistral AI", "https://api.mistral.ai/v1"),
    "other": Preset("Another OpenAI-compatible endpoint"),
}
_PLAIN = re.compile(r"[\w.:/@+=,{}\[\]-]*")


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


def run_setup(
    *,
    preset: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    judge: str | None = None,
    force: bool = False,
    ask: Callable[[str], str] = input,
    ask_secret: Callable[[str], str] = getpass.getpass,
    models: Callable[[str, str], list[str]] = list_models,
    say: Callable[[str], None] = print,
) -> int:
    """Ask for what the arguments leave open and write the config file. With the
    address, the key and the model given, nothing is asked. 0 when the file is written."""
    path = config_file()
    scripted = bool(base_url and api_key and model)
    if path.exists() and not force:
        answer = "" if scripted else ask(f"{path} exists. Replace it? [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            say(f"Nothing changed ({path} exists; --force replaces it).")
            return 1

    chosen = PRESETS[preset] if preset else None
    if chosen is None and not scripted:
        say("Which model endpoint should Leicht·Facile use?")
        names = list(PRESETS)
        for i, name in enumerate(names, 1):
            say(f"  {i}. {PRESETS[name].label}")
        answer = ask(f"Endpoint [1-{len(names)}, Enter: 1]: ").strip() or "1"
        while not (answer.isdigit() and 1 <= int(answer) <= len(names)):
            answer = ask(f"A number from 1 to {len(names)}: ").strip()
        chosen = PRESETS[names[int(answer) - 1]]
    chosen = chosen or PRESETS["other"]

    base_url = base_url or _required(ask, "Address of the endpoint", chosen.base_url)
    if not api_key:
        hint = f" (Enter: {chosen.api_key})" if chosen.api_key else ""
        api_key = ask_secret(f"API key{hint}: ").strip() or chosen.api_key
        while not api_key:
            api_key = ask_secret("API key (required): ").strip()

    listed: list[str] = []
    if not model:
        try:
            listed = models(base_url, api_key)
        except Exception as exc:  # the address or the key may be wrong: ask anyway
            say(f"The endpoint's model list could not be read ({type(exc).__name__}).")
        if listed:
            say("The endpoint lists these models:")
            for name in listed[:40]:
                say(f"  - {name}")
            if len(listed) > 40:
                say(f"  ... and {len(listed) - 40} more")
        default = chosen.model or (listed[0] if len(listed) == 1 else "")
        model = _required(ask, "Model", default)
        if listed and model not in listed:
            say(f"Note: {model} is not in the endpoint's list.")
    if judge is None:
        judge = chosen.judge
        if not scripted:
            prompt = f"Judge model (Enter: {judge or 'the same model'}): "
            judge = ask(prompt).strip() or judge

    values = {"LLM_BASE_URL": base_url, "LLM_API_KEY": api_key, "LLM_NAME": model}
    if judge and judge != model:
        values["LLM_JUDGE_NAME"] = judge
    values.update(chosen.settings)
    _write(path, values)
    say(f"Saved to {path}.")
    say("Check it with `leichtfacile check-llm`; start the app with `leichtfacile serve`.")
    return 0


def _required(ask: Callable[[str], str], label: str, default: str) -> str:
    prompt = f"{label} (Enter: {default}): " if default else f"{label}: "
    value = ask(prompt).strip() or default
    while not value:
        value = ask(f"{label} (required): ").strip()
    return value


def _dotenv(value: str) -> str:
    """A value as .env reads it back unchanged: bare when plain, else in single quotes
    (taken literally), else in double quotes with the backslashes and quotes escaped."""
    if _PLAIN.fullmatch(value) or (value.startswith("{") and "#" not in value and "'" not in value):
        return value
    if "'" not in value:
        return f"'{value}'"
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _write(path: Path, values: dict[str, str]) -> None:
    """Write the file readable by its owner alone where the system supports it (the key
    is in it)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Leicht·Facile settings, written by `leichtfacile setup` on {date.today():%d.%m.%Y}.",
        "# Edit them here or run the command again; .env.example lists every setting.",
        *(f"{key}={_dotenv(value)}" for key, value in values.items()),
    ]
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    if os.name == "posix":  # a file that existed keeps its mode through O_TRUNC
        os.chmod(path, 0o600)
