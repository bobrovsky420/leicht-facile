# The app in a container built from this checkout (docs/quickstart.md way 7). The app
# itself needs no make: `leichtfacile setup` and `leichtfacile serve`.
.PHONY: run stop logs check-docker

# compose.yaml publishes the port on this machine (LEICHTFACILE_PUBLISH, 127.0.0.1 by
# default); `make run OPEN_BROWSER=0` leaves the browser closed.
APP_URL ?= http://localhost:8000
OPEN_BROWSER ?= 1
# Seconds to wait for /healthz after the start.
WAIT_S ?= 120

# The recipes need a POSIX shell. On Windows, make falls back to cmd.exe unless
# sh.exe is on PATH, so use the one from Git for Windows (override GIT_SH_DIR if
# Git is installed elsewhere).
ifeq ($(OS),Windows_NT)
GIT_SH_DIR ?= C:/Program Files/Git/usr/bin
export PATH := $(GIT_SH_DIR);$(PATH)
SHELL := sh.exe
endif

# Build the image from the checkout, start it in the background with the settings and
# keys of .env, wait until it answers and open the web UI.
run: check-docker
	docker compose up --detach --build app
	@waited=0; \
	until curl -fsS -o /dev/null --max-time 2 "$(APP_URL)/healthz" 2>/dev/null; do \
		if [ -z "$$(docker compose ps --status running --quiet app)" ] || [ "$$waited" -ge $(WAIT_S) ]; then \
			echo "The app did not come up. Its log:"; \
			docker compose logs --tail 30 app; \
			exit 1; \
		fi; \
		sleep 1; waited=$$((waited + 1)); \
	done; \
	echo "The web UI is up: $(APP_URL) (make logs follows its log, make stop stops it)"; \
	if [ "$(OPEN_BROWSER)" != 0 ]; then \
		case "$$(uname -s)" in \
			MINGW* | MSYS* | CYGWIN*) rundll32.exe url.dll,FileProtocolHandler "$(APP_URL)" ;; \
			Darwin) open "$(APP_URL)" ;; \
			*) xdg-open "$(APP_URL)" >/dev/null 2>&1 || true ;; \
		esac; \
	fi

# Stop and remove the containers; the data stays in the volume leichtfacile_data.
stop: check-docker
	docker compose down

logs: check-docker
	docker compose logs --follow app

# Fail early with a helpful message instead of a connection error from Compose.
check-docker:
	@if ! command -v docker >/dev/null 2>&1; then \
		echo "Docker is not installed or not on PATH. Install Docker Desktop (Windows, macOS) or Docker Engine (Linux)."; \
		exit 1; \
	fi; \
	if ! err=$$(docker info 2>&1 >/dev/null); then \
		echo "Docker is not running. Start Docker Desktop (Windows, macOS) or the Docker service (Linux: sudo systemctl start docker) and try again."; \
		echo "$$err" | sed 's/^/  docker: /'; \
		exit 1; \
	fi; \
	if ! docker compose version >/dev/null 2>&1; then \
		echo "Docker Compose v2 is missing (the 'docker compose' command). Update Docker Desktop or install the Compose plugin."; \
		exit 1; \
	fi
