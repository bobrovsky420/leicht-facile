"""The clients of the presets (docs/configuration.md): the one in use and the other ready
ones a draft may pick in the New draft form.

A registry built from the settings makes a preset's client on first use and drops every
client when the settings change (`reload`: the model page of the web app saved a choice
or a key), so that the next draft runs on the new preset while a job already running
keeps the client it started with. One response cache serves them all (`llm.cache`). A
registry given its clients (the tests, a command with one client) keeps them as they
are. A local provider's models are listed on request (`discover`), with the answer kept
for a short while, since the model page and the New draft form ask on every visit.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Mapping

from leichtfacile import config
from leichtfacile.config import LLM, Available, ConfigError, Loaded, Settings
from leichtfacile.llm.cache import ResponseCache
from leichtfacile.llm.client import LLMClient

log = logging.getLogger(__name__)
DISCOVER_CACHE_S = 30.0
DISCOVER_TIMEOUT_S = 3.0


class Registry:
    def __init__(
        self,
        settings: Settings,
        *,
        llm: LLMClient | None = None,
        clients: Mapping[str, LLMClient] | None = None,
        loader: Callable[..., Loaded] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """`llm` is the client of the preset in use and `clients` the other ready ones
        by preset name, both kept as given; without them `loader` (config.load) makes
        the clients from the settings."""
        self.settings = settings
        self._fixed: dict[str, LLMClient] = {}
        if llm is not None:
            self._fixed[settings.llm.preset or ""] = llm
        self._fixed.update(clients or {})
        self._loader = loader
        self._clock = clock
        self._lock = threading.Lock()
        self._built: dict[str, LLMClient] = {}
        self._ready: dict[str, bool] = {}
        self._cache: ResponseCache | None = None
        self._listed: dict[str, tuple[float, list[str] | None]] = {}
        # How a preset's client is made (the tests put one on a fake endpoint here).
        self.make_client: Callable[[Settings, ResponseCache | None], LLMClient] = _make_client

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> Registry:
        """A registry on the settings as they are now, the clients made on first use."""
        return cls(settings or config.load(strict=False).settings, loader=config.load)

    # -- the preset in use and the others -------------------------------------------------

    @property
    def in_use(self) -> str:
        return self.settings.llm.preset or ""

    @property
    def llm(self) -> LLMClient | None:
        """The client of the preset in use; None while it is not ready (no key)."""
        try:
            return self.client_for(None)
        except KeyError:
            return None

    def client_for(self, name: str | None) -> LLMClient:
        """The client of a preset: the one in use for None or its name. KeyError when
        the preset is not offered or not ready."""
        name = name or self.in_use
        with self._lock:
            if name in self._fixed:
                return self._fixed[name]
            if self._loader is None or not self._is_ready(name):
                raise KeyError(name)
            if name not in self._built:
                settings = self._loader(preset=name).settings
                self._built[name] = self.make_client(settings, self._shared_cache())
            return self._built[name]

    def is_ready(self, name: str | None = None) -> bool:
        name = name or self.in_use
        with self._lock:
            return name in self._fixed or (self._loader is not None and self._is_ready(name))

    def _is_ready(self, name: str) -> bool:
        assert self._loader is not None
        if name not in self._ready:
            try:
                self._ready[name] = not self._loader(strict=False, preset=name).problems
            except ConfigError:
                self._ready[name] = False
        return self._ready[name]

    def _shared_cache(self) -> ResponseCache | None:
        if self._cache is None and self.settings.llm.cache:
            self._cache = ResponseCache(self.settings.data.dir / "llm_cache.sqlite")
        return self._cache

    def available(self) -> list[Available]:
        """Every preset with what it lacks, the shipped ones first (config.available);
        a registry given its clients offers those alone."""
        if self._loader is None:
            return [
                _available_fixed(name or self.in_use, client.settings.llm)
                for name, client in self._fixed.items()
            ]
        return config.available()

    def ready(self) -> list[tuple[str, LLM]]:
        """The ready presets a draft may pick, the one in use first: name and settings;
        the one in use alone when it is the only one."""
        found: list[tuple[str, LLM]] = []
        if self._loader is None:
            for name, client in self._fixed.items():
                found.append((name or self.in_use, client.settings.llm))
        else:
            for item in self.available():
                if not item.ready:
                    continue
                in_use = item.name == self.in_use
                found.append(
                    (item.name, self.settings.llm if in_use else self._settings_of(item.name))
                )
        found.sort(key=lambda pair: pair[0] != self.in_use)
        return found

    def _settings_of(self, name: str) -> LLM:
        assert self._loader is not None
        return self._loader(preset=name).settings.llm

    def reload(self) -> None:
        """Read the settings again and drop the clients made from the old ones (the
        given ones stay); the next call makes them anew."""
        if self._loader is None:
            return
        settings = self._loader(strict=False).settings
        with self._lock:
            self.settings = settings
            self._built.clear()
            self._ready.clear()
            self._listed.clear()

    # -- local servers ----------------------------------------------------------------

    def discover(self, provider: str) -> list[str] | None:
        """The models a provider with `discover = true` lists, None while it does not
        answer; asked at most once per `DISCOVER_CACHE_S` seconds, within
        `DISCOVER_TIMEOUT_S`, so that a page never waits long for a server that is off."""
        from leichtfacile.configure import list_models

        now = self._clock()
        with self._lock:
            cached = self._listed.get(provider)
            if cached is not None and now - cached[0] < DISCOVER_CACHE_S:
                return cached[1]
        found: list[str] | None
        try:
            table = config.provider_table(config.collect(), provider)
            key = table.get("api_key") or table.get("api_key_env") or "none"
            if table.get("api_key_env") and (secret := config.secret_value(table["api_key_env"])):
                key = secret[0]
            found = list_models(
                str(table.get("url", "")),
                str(key),
                table.get("headers"),
                timeout_s=DISCOVER_TIMEOUT_S,
            )
        except Exception as exc:  # the server is off, or refuses: the page says so
            log.debug("discovering %s failed: %s", provider, type(exc).__name__)
            found = None
        with self._lock:
            self._listed[provider] = (now, found)
        return found


def _make_client(settings: Settings, cache: ResponseCache | None) -> LLMClient:
    return LLMClient.from_settings(settings, **({"cache": cache} if cache else {}))


def _available_fixed(name: str, llm: LLM) -> Available:
    """A given client's preset as the pages list it."""
    return Available(
        name,
        label=llm.title,
        provider=llm.provider or "",
        provider_label=llm.provider_label or llm.provider or "",
        location=llm.location,
        documents=llm.documents,
        key_url=llm.key_url,
        key_variable=llm.api_key_env,
        url=llm.url,
        writer=llm.models.writer,
        judge=llm.models.judge,
        has_key=True,
        missing=(),
        cost_per_page=config.cost_per_page(llm),
    )
