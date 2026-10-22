#!/bin/bash
# One-click launcher for Voicebox (voice cloning).
# Double-click it in Finder (or run it in Terminal) to start everything and open the page.
#   ./"Start Voice Studio.command"        start (safe to run again: already-running parts are reused)
#   ./"Start Voice Studio.command" stop   stop the backend and the page server

BACKEND_PORT="${BACKEND_PORT:-8000}"
PAGE_PORT="${PAGE_PORT:-5173}"
ROOT="$(cd "$(dirname "$0")" && pwd)/voicebox"
LOG_DIR="${TMPDIR:-/tmp}"

if [ "$1" = "stop" ]; then
  for port in "$BACKEND_PORT" "$PAGE_PORT"; do
    pids="$(lsof -ti "tcp:$port" -sTCP:LISTEN)"
    [ -n "$pids" ] && kill $pids && echo "Stopped whatever was listening on port $port"
  done
  exit 0
fi

cd "$ROOT" || { echo "Can't find the voicebox folder next to this script: $ROOT"; exit 1; }

wait_for() { # url, seconds
  for _ in $(seq 1 "$2"); do
    curl -s -m 2 -o /dev/null "$1" && return 0
    sleep 1
  done
  return 1
}

# 1. Backend (speech engine + model cache)
if curl -s -m 2 -o /dev/null "http://127.0.0.1:$BACKEND_PORT/health"; then
  echo "Backend already running on port $BACKEND_PORT"
else
  echo "Starting backend on port $BACKEND_PORT ..."
  VOICEBOX_CORS_ORIGINS="http://localhost:$PAGE_PORT,http://127.0.0.1:$PAGE_PORT" \
    nohup backend/venv/bin/python -m backend.main --port "$BACKEND_PORT" \
    > "$LOG_DIR/voicebox-backend.log" 2>&1 &
  disown
  wait_for "http://127.0.0.1:$BACKEND_PORT/health" 90 || {
    echo "Backend did not start. Last log lines ($LOG_DIR/voicebox-backend.log):"
    tail -n 15 "$LOG_DIR/voicebox-backend.log"
    exit 1
  }
fi

# 2. The interface. The full Voicebox UI is served by the backend itself once it has been
#    built (voicebox/frontend, see README); otherwise fall back to the standalone page.
if [ -f "$ROOT/frontend/index.html" ]; then
  URL="http://localhost:$BACKEND_PORT/"
else
  if curl -s -m 2 -o /dev/null "http://127.0.0.1:$PAGE_PORT/voice_clone.html"; then
    echo "Page server already running on port $PAGE_PORT"
  else
    echo "Starting page server on port $PAGE_PORT ..."
    nohup python3 -m http.server "$PAGE_PORT" --bind 127.0.0.1 > "$LOG_DIR/voicebox-page.log" 2>&1 &
    disown
    wait_for "http://127.0.0.1:$PAGE_PORT/voice_clone.html" 15 || {
      echo "Page server did not start (is port $PAGE_PORT used by something else?)"
      exit 1
    }
  fi
  URL="http://localhost:$PAGE_PORT/voice_clone.html"
  [ "$BACKEND_PORT" != "8000" ] && URL="$URL?api=http://127.0.0.1:$BACKEND_PORT"
fi

echo
echo "Voicebox is ready:  $URL"
echo "To stop it later:  ./\"Start Voice Studio.command\" stop"
command -v open >/dev/null && open "$URL"
