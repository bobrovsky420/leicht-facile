# Development tasks in a checkout (docs/quickstart.md, "Development"). The app itself
# needs no make: `leichtfacile setup` and `leichtfacile serve`.
.PHONY: test lint format check-llm smoke calibrate eval eval-70b

# Results of one endpoint stay together: `make eval RESULTS=eval/results-cscs`.
RESULTS ?= eval/results

# The recipes need a POSIX shell. On Windows, make falls back to cmd.exe unless
# sh.exe is on PATH, so use the one from Git for Windows (override GIT_SH_DIR if
# Git is installed elsewhere).
ifeq ($(OS),Windows_NT)
GIT_SH_DIR ?= C:/Program Files/Git/usr/bin
export PATH := $(GIT_SH_DIR);$(PATH)
SHELL := sh.exe
endif

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .

# List the endpoint's models and make one short call.
check-llm:
	uv run leichtfacile check-llm

# One document through the full pipeline against the live endpoint. Succeeds when the
# job reaches review; the artifacts land in out/smoke.
smoke:
	uv run leichtfacile simplify src/leichtfacile/letters/praemienverbilligung-brief.txt --out out/smoke

# Rule checker on the official easy-language pages (no model needed).
calibrate:
	uv run python -m leichtfacile eval fetch --role all
	uv run python -m leichtfacile eval calibrate --role all --lang de
	uv run python -m leichtfacile eval calibrate --role all --lang fr

# Evaluation: conditions P0, P0-ZH (the Canton of Zurich's prompt, German only), P1 and
# P2 on the held-out pairs, then the report tables.
# Responses are cached (LLM_CACHE=1), so an interrupted run resumes cheaply.
eval:
	uv run python -m leichtfacile eval fetch --role all
	uv run python -m leichtfacile eval reference --role all --results $(RESULTS)
	LLM_CACHE=1 uv run python -m leichtfacile eval run --condition P0 --results $(RESULTS)
	LLM_CACHE=1 uv run python -m leichtfacile eval run --condition P0-ZH-complete --lang de --results $(RESULTS)
	LLM_CACHE=1 uv run python -m leichtfacile eval run --condition P0-ZH-condensed --lang de --results $(RESULTS)
	LLM_CACHE=1 uv run python -m leichtfacile eval run --condition P1 --results $(RESULTS)
	LLM_CACHE=1 uv run python -m leichtfacile eval run --condition P2 --results $(RESULTS)
	uv run python -m leichtfacile eval report --results $(RESULTS) --out docs/evaluation.md

# The 70B comparison: P2 with the 70B writer (every stage on the 70B) and the hybrid
# (the 70B reads, the 8B writes), then the report tables again.
eval-70b:
	LLM_CACHE=1 uv run python -m leichtfacile eval run --condition P2 --writer swiss-ai/Apertus-v1.5-70B --results $(RESULTS)
	LLM_CACHE=1 uv run python -m leichtfacile eval run --condition P2 --understand swiss-ai/Apertus-v1.5-70B --results $(RESULTS)
	uv run python -m leichtfacile eval report --results $(RESULTS) --out docs/evaluation.md
