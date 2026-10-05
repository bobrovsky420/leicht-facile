.PHONY: run stop check-env check-llm test lint format smoke eval bundle

REQUIRED_VARS := LLM_BASE_URL LLM_API_KEY LLM_NAME

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

# Placeholders until the pipeline and the evaluation harness exist.
smoke: check-llm

eval:
	@echo "make eval: the evaluation harness is not implemented yet."; exit 1

bundle:
	@echo "make bundle: the air-gapped image bundle is not implemented yet."; exit 1
