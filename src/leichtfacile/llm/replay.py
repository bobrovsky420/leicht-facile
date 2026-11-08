"""Recorded runs of the sample letters (samples/README.md): a sample letter sent from the
New draft form ends in seconds instead of minutes, and at no cost.

`scripts/record_samples.py` sends each letter through the pipeline on a preset with a
`Recorder` as the response cache. Unlike the cache it never forgets an answer, not even
one the pipeline threw away and asked again for (`LLMClient.forget`), so that a replay
takes the same path as the run it replays. A clean run is written to
recordings/<preset>/<letter>.json in the package leichtfacile-samples.

The web app loads them into a `Replay` (web/app.py). The client answers from it inside
`LLMClient.replaying`, which the orchestrator turns on for a job's first run, and only a
prompt that is byte for byte a recorded one (the key of llm/cache.py): an edited letter,
another preset, level or setting, a changed prompt and every rerun go to the endpoint.
The command line and the evaluation never load it.

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

from leichtfacile_samples import RECORDINGS

if TYPE_CHECKING:
    from leichtfacile.llm.client import Usage

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Recording:
    """One sample letter's recorded run on one preset, without its answers."""

    letter: str  # the letter's file name without suffix
    preset: str
    models: dict[str, str]  # by role: writer, judge, and understand when it differs
    recorded_at: datetime
    version: str  # of the app that recorded it
    endpoint: str  # scheme and host
    seconds: float  # model time of the recorded run
    calls: int
    result: dict[str, Any]  # final version, errors, warnings, blocking, facts

    @property
    def path(self) -> str:
        """Where it is written in the recordings folder."""
        return f"{self.preset}/{self.letter}.json"


class Replay:
    """The recorded answers of every sample letter, by key. Read-only: a replayed job's
    deletion and a forgotten answer leave it as it is."""

    def __init__(self, recordings: Iterable[tuple[Recording, list[dict[str, Any]]]] = ()) -> None:
        self._answers: dict[str, dict[str, Any]] = {}
        self._recording: dict[str, Recording] = {}  # key -> the recording it belongs to
        for recording, answers in recordings:
            for answer in answers:
                self._answers[answer["key"]] = answer
                self._recording[answer["key"]] = recording

    @classmethod
    def load(cls, folder: Path = RECORDINGS) -> Replay:
        """Every recording in `folder` (<preset>/<letter>.json); none when it does not
        exist. A broken file is left out with a warning: the letter then runs live."""
        loaded = []
        for path in sorted(folder.glob("*/*.json")) if folder.is_dir() else []:
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

    def recording_for(self, keys: Iterable[str]) -> Recording | None:
        """The recording a job's calls were answered from (`Store.cache_keys`), if any."""
        for key in keys:
            recording = self._recording.get(key)
            if recording is not None:
                return recording
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


def write_recording(folder: Path, recording: Recording, answers: list[dict[str, Any]]) -> Path:
    """The recording as `folder`/<preset>/<letter>.json; returns the path."""
    data = {
        "letter": recording.letter,
        "preset": recording.preset,
        "models": recording.models,
        "recorded_at": recording.recorded_at.isoformat(timespec="seconds"),
        "version": recording.version,
        "endpoint": recording.endpoint,
        "seconds": round(recording.seconds, 1),
        "calls": recording.calls,
        "result": recording.result,
        "answers": answers,
    }
    path = folder / recording.path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def read_recording(path: Path) -> tuple[Recording, list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    recording = Recording(
        letter=data["letter"],
        preset=data["preset"],
        models=dict(data["models"]),
        recorded_at=datetime.fromisoformat(data["recorded_at"]),
        version=data["version"],
        endpoint=data["endpoint"],
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
