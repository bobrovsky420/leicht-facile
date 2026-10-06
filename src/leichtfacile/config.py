"""Settings from environment variables (and a local `.env` file during development).

The three variables required by the hackathon template are `LLM_BASE_URL`,
`LLM_API_KEY` and `LLM_NAME`. Everything else has a default.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ThinkingMode = Literal["model-suffix", "chat-template", "off"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Model endpoint (OpenAI-compatible). See .env.example for the supported profiles.
    llm_base_url: str
    llm_api_key: SecretStr
    llm_name: str
    llm_judge_name: str | None = None
    llm_thinking_mode: ThinkingMode = "model-suffix"
    llm_thinking_suffix: str = "-thinking"
    # Stages that use the thinking model. Writing without thinking was faster and closer
    # to easy language in the first local tests (docs/prompts.md); the day-1 checks
    # on the CSCS endpoint decide the final setting.
    llm_thinking_stages: str = "understand,judge"
    llm_timeout_s: float = Field(default=300.0, gt=0)
    llm_max_retries: int = Field(default=4, ge=0)
    llm_cache: bool = False

    # Pipeline
    max_repair_rounds: int = Field(default=3, ge=0)

    # Runtime
    data_dir: Path = Path("data")
    log_level: str = "INFO"

    @model_validator(mode="after")
    def _default_judge(self) -> Settings:
        if not self.llm_judge_name:
            self.llm_judge_name = self.llm_name
        return self

    @property
    def judge_name(self) -> str:
        return self.llm_judge_name or self.llm_name

    @property
    def thinking_stages(self) -> set[str]:
        return {s.strip() for s in self.llm_thinking_stages.split(",") if s.strip()}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
