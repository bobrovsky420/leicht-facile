"""Settings from environment variables (and a local `.env` file during development).

The three variables required by the hackathon template are `LLM_BASE_URL`,
`LLM_API_KEY` and `LLM_NAME`. Everything else has a default.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ThinkingMode = Literal["model-suffix", "chat-template", "off"]

# The 8B of an Apertus family (swiss-ai/Apertus-v1.5-8B, swiss-ai/apertus-v1.5-8b), whose
# 70B judges by default when the endpoint serves it.
_APERTUS_8B = re.compile(r"(apertus\S*-)8(b)$", re.IGNORECASE)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Model endpoint (OpenAI-compatible). See .env.example for the supported profiles.
    llm_base_url: str
    llm_api_key: SecretStr
    llm_name: str
    llm_judge_name: str | None = None
    # The Understand stage's model, when it should differ from the writer (the hybrid:
    # the 70B reads, the 8B writes; docs/prompts.md compares the tiers). Empty: the
    # writer's model.
    llm_understand_name: str | None = None
    llm_thinking_mode: ThinkingMode = "model-suffix"
    llm_thinking_suffix: str = "-thinking"
    # Stages that use the thinking model. Writing without thinking was faster and closer
    # to easy language in the first local tests (docs/prompts.md); the day-1 checks
    # on the CSCS endpoint decide the final setting.
    llm_thinking_stages: str = "understand,judge"
    # Streamed responses: the endpoint sends the answer as it is generated, so a proxy in
    # front of it cannot time out a long answer (Cloudflare in front of the Public AI
    # gateway does so after about 100 seconds). Off only for a server without streaming.
    llm_stream: bool = True
    llm_timeout_s: float = Field(default=300.0, gt=0)
    # CSCS closes about one long thinking stream in four midway; 8 retries make a hard
    # failure rare (6 October 2026). The backoff stops growing at 30 seconds.
    llm_max_retries: int = Field(default=8, ge=0)
    llm_cache: bool = False
    # Extra JSON fields sent with every request, for gateway-specific switches such as
    # Public AI's `{"cache": {"no-cache": true}}` (its response cache ignores the
    # thinking switch). Set as JSON in the environment.
    llm_extra_body: dict[str, Any] = Field(default_factory=dict)

    # Pipeline
    max_repair_rounds: int = Field(default=3, ge=0)
    # Rounds that ask only for the must-keep facts still missing after the repair loop
    # has stopped (docs/architecture.md §4.6). 0 switches them off.
    max_facts_rounds: int = Field(default=1, ge=0, le=5)

    # Runtime
    data_dir: Path = Path("data")
    log_level: str = "INFO"
    # Interface language for visitors who have not picked one: a code with a catalog in
    # web/locales/ (en, de), or "auto" for the browser's preference. The switcher in the
    # header overrides it per browser.
    ui_lang: str = "auto"

    @property
    def judge_name(self) -> str:
        """LLM_JUDGE_NAME, else the writer's model. What the endpoint serves can change
        that default: `judge_for`."""
        return self.llm_judge_name or self.llm_name

    @property
    def larger_name(self) -> str | None:
        """The 70B of the writer's Apertus family, None for any other writer."""
        larger = _APERTUS_8B.sub(r"\g<1>70\g<2>", self.llm_name)
        return larger if larger != self.llm_name else None

    def judge_for(self, models: Iterable[str]) -> str:
        """The judge's model: LLM_JUDGE_NAME when set; else the 70B of the writer's
        family when the endpoint lists it (the setup the evaluation measured, also when
        only the three required variables are set); else the writer's model (a local
        server with one model)."""
        if self.llm_judge_name:
            return self.llm_judge_name
        larger = self.larger_name
        return larger if larger and larger in set(models) else self.llm_name

    @property
    def understand_name(self) -> str:
        return self.llm_understand_name or self.llm_name

    @property
    def thinking_stages(self) -> set[str]:
        return {s.strip() for s in self.llm_thinking_stages.split(",") if s.strip()}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
