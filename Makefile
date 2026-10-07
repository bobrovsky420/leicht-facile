.PHONY: run stop check-env check-llm test lint format smoke calibrate day1 eval eval-70b bundle

REQUIRED_VARS := LLM_BASE_URL LLM_API_KEY LLM_NAME
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

# Start the application in Docker. A helper opens APP_URL in the default browser as
# soon as the service answers (`make run OPEN_BROWSER=0` turns that off). The helper
# is stopped with the containers, also when the start fails.
APP_URL ?= http://localhost:8000
OPEN_BROWSER ?= 1

run: check-env
	@opener=; \
	if [ "$(OPEN_BROWSER)" != 0 ]; then sh scripts/open_browser.sh "$(APP_URL)" & opener=$$!; fi; \
	trap '[ -n "$$opener" ] && kill $$opener 2>/dev/null' EXIT INT TERM; \
	docker compose up --build

stop:
	docker compose down

# Fail early with a helpful message instead of a crashing container. Each required
# variable comes from the shell or from .env (docker-compose.yml passes both on).
check-env:
	@for v in $(REQUIRED_VARS); do \
		if [ -z "$$(printenv $$v)" ] && ! { [ -f .env ] && grep -Eq "^$$v=.+" .env; }; then \
			echo "Variable $$v is not set. Export it in the shell, or copy .env.example to .env and set it there."; \
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
# MSYS_NO_PATHCONV keeps Git Bash on Windows from turning /data/out into a C: path.
smoke: check-env
	MSYS_NO_PATHCONV=1 docker compose run --rm --build app python -m leichtfacile simplify data/examples/sources/praemienverbilligung-brief.txt --out /data/out

# Rule checker on the official easy-language pages (no model needed).
calibrate:
	uv run python -m leichtfacile eval fetch --role all
	uv run python -m leichtfacile eval calibrate --role all --lang de
	uv run python -m leichtfacile eval calibrate --role all --lang fr

# Day-1 questions about the endpoint (docs/architecture.md §12).
day1: check-env
	uv run python scripts/day1_checks.py

# Evaluation: conditions P0, P0-ZH (the Canton of Zurich's prompt, German only), P1 and
# P2 on the held-out pairs, then the report tables.
# Responses are cached (LLM_CACHE=1), so an interrupted run resumes cheaply.
eval: check-env
	uv run python -m leichtfacile eval fetch --role all
	uv run python -m leichtfacile eval reference --role all --results $(RESULTS)
	LLM_CACHE=1 uv run python -m leichtfacile eval run --condition P0 --results $(RESULTS)
	LLM_CACHE=1 uv run python -m leichtfacile eval run --condition P0-ZH-complete --lang de --results $(RESULTS)
	LLM_CACHE=1 uv run python -m leichtfacile eval run --condition P0-ZH-condensed --lang de --results $(RESULTS)
	LLM_CACHE=1 uv run python -m leichtfacile eval run --condition P1 --results $(RESULTS)
	LLM_CACHE=1 uv run python -m leichtfacile eval run --condition P2 --results $(RESULTS)
	uv run python -m leichtfacile eval report --results $(RESULTS) --out eval/report.md

# The 70B comparison: P2 with the 70B writer (every stage on the 70B) and the hybrid
# (the 70B reads, the 8B writes), then the report tables again.
eval-70b: check-env
	LLM_CACHE=1 uv run python -m leichtfacile eval run --condition P2 --writer swiss-ai/Apertus-v1.5-70B --results $(RESULTS)
	LLM_CACHE=1 uv run python -m leichtfacile eval run --condition P2 --understand swiss-ai/Apertus-v1.5-70B --results $(RESULTS)
	uv run python -m leichtfacile eval report --results $(RESULTS) --out eval/report.md

bundle:
	@echo "make bundle: the air-gapped image bundle is not implemented yet."; exit 1
