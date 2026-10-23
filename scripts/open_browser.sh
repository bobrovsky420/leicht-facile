#!/bin/sh
# Waits until the web UI answers and opens it in the default browser.
#
# `make run` starts this in the background next to `docker compose up`. It never fails
# the run: without a desktop (a server, CI, a shell over SSH) it only prints the
# address. Usage: open_browser.sh [URL] [TIMEOUT_S]

url="${1:-http://localhost:8000}"
# The first build installs the dependencies and the spaCy models and can take minutes.
timeout_s="${2:-900}"

# /healthz answers 200 as soon as the service is up, even when the endpoint is not.
is_up() {
	if command -v curl >/dev/null 2>&1; then
		curl -fsS -o /dev/null --max-time 2 "$url/healthz" 2>/dev/null
	else
		id=$(docker compose ps -q app 2>/dev/null)
		[ -n "$id" ] && [ "$(docker inspect -f '{{.State.Health.Status}}' "$id" 2>/dev/null)" = healthy ]
	fi
}

open_url() {
	case "$(uname -s)" in
		MINGW* | MSYS* | CYGWIN*)
			rundll32.exe url.dll,FileProtocolHandler "$url"
			;;
		Darwin)
			open "$url"
			;;
		*)
			if grep -qi microsoft /proc/version 2>/dev/null; then
				# WSL: hand the address to the Windows browser.
				if command -v wslview >/dev/null 2>&1; then
					wslview "$url"
				else
					rundll32.exe url.dll,FileProtocolHandler "$url"
				fi
			elif [ -n "$DISPLAY$WAYLAND_DISPLAY" ] && command -v xdg-open >/dev/null 2>&1; then
				xdg-open "$url"
			else
				return 1
			fi
			;;
	esac
}

waited=0
until is_up; do
	if [ "$waited" -ge "$timeout_s" ]; then
		exit 0
	fi
	sleep 2
	waited=$((waited + 2))
done

echo
echo ">>> The web UI is up: $url"
if ! open_url >/dev/null 2>&1; then
	echo ">>> Open it in a browser."
fi
