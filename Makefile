.PHONY: run stop check-env check-llm test lint format smoke calibrate day1 eval bundle

REQUIRED_VARS := LLM_BASE_URL LLM_API_KEY LLM_NAME

# The recipes need a POSIX shell. On Windows, make falls back to cmd.exe unless
# sh.exe is on PATH, so use the one from Git for Windows (override GIT_SH_DIR if
# Git is installed elsewhere).
ifeq ($(OS),Windows_NT)
GIT_SH_DIR ?= C:/Program Files/Git/usr/bin
export PATH := $(GIT_SH_DIR);$(PATH)
SHELL := sh.exe
endif

# Start the application in Docker. Open http://localhost:8000 when it is up.
run: check-env
	docker compose up --build

stop:
	docker compose down

# Fail early with a helpful message instead of a crashing container.
check-env:
	@if [ ! -f .env ]; then \
		echo "Missing .env. Copy .env.example to .env and set $(REQUIRED_VARS)."; \
		exit 1; \
	fi
	@for v in $(REQUIRED_VARS); do \
		if ! grep -Eq "^$$v=.+" .env; then \
			echo "Variable $$v is missing or empty in .env (see .env.example)."; \
			exit 1; \
		fi; \
	done

# List the endpoint's models and make one short call, inside the container.
check-llm: check-env
	docker compose run --rm --build app python -m leichtfacile check-llm

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .

# One document through the full pipeline in the container, against the live endpoint.
# Succeeds when the job reaches review; the artifacts land in the volume under /data/out.
smoke: check-env
	docker compose run --rm --build app python -m leichtfacile simplify data/examples/sources/praemienverbilligung-brief.txt --out /data/out

# Rule checker on the official easy-language pages (no model needed).
calibrate:
	uv run python -m leichtfacile eval fetch --role all
	uv run python -m leichtfacile eval calibrate --role all --lang de
	uv run python -m leichtfacile eval calibrate --role all --lang fr

# Day-1 questions about the endpoint (docs/architecture.md §12).
day1: check-env
	uv run python scripts/day1_checks.py

# Evaluation: conditions C0, C1, C2 on the held-out pairs, then the report tables.
# Responses are cached (LLM_CACHE=1), so an interrupted run resumes cheaply.
eval: check-env
	uv run python -m leichtfacile eval fetch --role all
	uv run python -m leichtfacile eval reference --role all
	LLM_CACHE=1 uv run python -m leichtfacile eval run --condition C0
	LLM_CACHE=1 uv run python -m leichtfacile eval run --condition C1
	LLM_CACHE=1 uv run python -m leichtfacile eval run --condition C2
	uv run python -m leichtfacile eval report --out eval/report.md

bundle:
	@echo "make bundle: the air-gapped image bundle is not implemented yet."; exit 1
