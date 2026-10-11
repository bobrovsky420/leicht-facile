"""Recorded runs of the prepared letters: a visitor starts one with a click and it ends
in seconds instead of minutes (track_2b/data/examples/README.md).

`python -m leichtfacile examples record` sends each prepared letter through the
pipeline on the endpoint with a `Recorder` as the response cache. Unlike the cache it
never forgets an answer, not even one the pipeline threw away and asked again for
(`LLMClient.forget`), so that a replay takes the same path as the run it replays. A
clean run is written to `replay/<letter>.json` in EXAMPLES_DIR.

The web app loads these files into a `Replay`. The client answers from it inside
`LLMClient.replaying`, which the orchestrator turns on for a job's first run, and only
a prompt that is byte for byte a recorded one (the key of llm/cache.py): an edited
letter, other models or settings, and every rerun go to the endpoint.

A recording keeps the answers, not the prompts (the key is their hash), and not the
reasoning, which no stage reads.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from leichtfacile.config import Settings
    from leichtfacile.llm.client import Usage

log = logging.getLogger(__name__)
FOLDER = "replay"  # in EXAMPLES_DIR, next to sources/ and jobs/


def replay_settings(settings: Settings, judge: str | None = None) -> dict[str, Any]:
    """What a run's prompts depend on besides the letter and the code: the models, the
    thinking switch and the rounds. A recording replays under the same values only.
    `judge` is the judge a run used; without it, the one `Settings.judge_for` picks
    when the endpoint serves the 70B."""
    return {
        "writer": settings.llm_name,
        "understand": settings.understand_name,
        "judge": judge or settings.llm_judge_name or settings.larger_name or settings.llm_name,
        "thinking_mode": settings.llm_thinking_mode,
        "thinking_suffix": settings.llm_thinking_suffix,
        "thinking_stages": sorted(settings.thinking_stages),
        "extra_body": settings.llm_extra_body,
        "max_repair_rounds": settings.max_repair_rounds,
        "max_facts_rounds": settings.max_facts_rounds,
        "max_missing_per_facts_round": settings.max_missing_per_facts_round,
        "max_recover_facts": settings.max_recover_facts,
        "max_polish_rounds": settings.max_polish_rounds,
        "use_vocabulary": settings.use_vocabulary,
    }


@dataclass(frozen=True)
class Recording:
    """One prepared letter's recorded run, without its answers."""

    letter: str  # the source's file name without suffix
    recorded_at: datetime
    version: str  # of the application that recorded it
    endpoint: str  # scheme and host
    settings: dict[str, Any]  # `replay_settings` of the run
    seconds: float  # model time of the recorded run
    calls: int
    result: dict[str, Any]  # final version, errors, warnings, facts present and total

    def applies(self, settings: Settings) -> bool:
        """Whether a run under `settings` sends the recorded prompts."""
        return _plain(self.settings) == _plain(replay_settings(settings))


class Replay:
    """The recorded answers of every prepared letter, by key. Read-only: a replayed
    job's deletion and a forgotten answer leave it as it is."""

    def __init__(self, recordings: Iterable[tuple[Recording, list[dict[str, Any]]]] = ()) -> None:
        self._recordings: dict[str, Recording] = {}
        self._answers: dict[str, dict[str, Any]] = {}
        self._letter: dict[str, str] = {}  # key -> letter
        for recording, answers in recordings:
            self._recordings[recording.letter] = recording
            for answer in answers:
                self._answers[answer["key"]] = answer
                self._letter[answer["key"]] = recording.letter

    @classmethod
    def load(cls, folder: Path) -> Replay:
        """Every recording in `folder`; none when it does not exist. A broken file is
        left out with a warning: the letter then runs live."""
        loaded = []
        for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
            try:
                loaded.append(read_recording(path))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                log.warning("recording %s not loaded: %s", path.name, exc)
        replay = cls(loaded)
        if loaded:
            log.info("loaded %d recorded runs (%d answers)", len(loaded), len(replay))
        return replay

    def __len__(self) -> int:
        return len(self._answers)

    def get(self, key: str) -> dict[str, Any] | None:
        """The answer recorded for this prompt, as the response cache gives it."""
        answer = self._answers.get(key)
        return None if answer is None else _as_cached(answer)

    def recording(self, letter: str) -> Recording | None:
        return self._recordings.get(letter)

    def recording_for(self, keys: Iterable[str]) -> Recording | None:
        """The recording a job's calls were answered from (`Store.cache_keys`), if any."""
        for key in keys:
            letter = self._letter.get(key)
            if letter is not None:
                return self._recordings[letter]
        return None


class Recorder:
    """The response cache of a recorded run: it answers a prompt it has seen, as the
    cache does, and never forgets an answer, so the recording holds every answer the
    run used, in the order they came. `observe` is the client's usage sink; it gives
    each answer its stage and latency."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._answers: dict[str, dict[str, Any]] = {}
        self._calls: dict[str, Usage] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            answer = self._answers.get(key)
        return None if answer is None else _as_cached(answer)

    def put(self, key: str, model: str, response: dict[str, Any]) -> None:
        with self._lock:
            usage = self._calls.get(key)
            self._answers[key] = {
                "key": key,
                "stage": usage.stage if usage else "",
                "model": model,
                "latency_ms": usage.latency_ms if usage else 0,
                "tokens_in": response["tokens_in"],
                "tokens_out": response["tokens_out"],
                "finish_reason": response["finish_reason"],
                "text": response["text"],
            }

    def delete(self, key: str) -> None:
        """Nothing: the replay must meet the answer the run threw away to take its path."""

    def observe(self, usage: Usage) -> None:
        if usage.cache_key and not usage.cached:
            with self._lock:
                self._calls[usage.cache_key] = usage

    @property
    def answers(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._answers.values())


def write_recording(path: Path, recording: Recording, answers: list[dict[str, Any]]) -> None:
    data = {
        "letter": recording.letter,
        "recorded_at": recording.recorded_at.isoformat(timespec="seconds"),
        "version": recording.version,
        "endpoint": recording.endpoint,
        "settings": recording.settings,
        "seconds": round(recording.seconds, 1),
        "calls": recording.calls,
        "result": recording.result,
        "answers": answers,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def read_recording(path: Path) -> tuple[Recording, list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    recording = Recording(
        letter=data["letter"],
        recorded_at=datetime.fromisoformat(data["recorded_at"]),
        version=data["version"],
        endpoint=data["endpoint"],
        settings=data["settings"],
        seconds=float(data["seconds"]),
        calls=int(data["calls"]),
        result=data["result"],
    )
    return recording, list(data["answers"])


def _as_cached(answer: dict[str, Any]) -> dict[str, Any]:
    """A recorded answer as the response cache holds one (llm/cache.py)."""
    return {
        "text": answer["text"],
        "reasoning": None,
        "finish_reason": answer["finish_reason"],
        "tokens_in": answer["tokens_in"],
        "tokens_out": answer["tokens_out"],
    }


def _plain(value: Any) -> Any:
    """The value as JSON reads it back: tuples become lists, so stored and computed
    settings compare equal."""
    return json.loads(json.dumps(value, sort_keys=True))
