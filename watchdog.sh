#!/usr/bin/env bash
# Per-port watchdog for the MEXC XAU/USDT web terminal.
# Manages its OWN port only via a pidfile (never pkill's other ports), so
# multiple watchdogs can run side by side on 12000 / 12001 / ...
# Run detached:  setsid nohup ./watchdog.sh > watchdog.log 2>&1 &
# With a port:   setsid nohup env PORT=12001 ./watchdog.sh > watchdog2.log 2>&1 &
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-12000}"
LOG="$DIR/web_server_$PORT.log"
PIDFILE="/tmp/mexc_web_$PORT.pid"
HEALTH_URL="http://localhost:$PORT/health"

server_alive() {
  [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null
}

deps_ok() {
  python3 -c "import aiohttp, websockets, rich, numpy" >/dev/null 2>&1
}

start_server() {
  setsid nohup python3 "$DIR/web/server.py" > "$LOG" 2>&1 &
  echo $! > "$PIDFILE"
}

while true; do
  if ! deps_ok; then
    echo "$(date -u +'%F %T') deps missing -> pip install" >> "$DIR/watchdog_$PORT.log"
    pip install -q -r "$DIR/requirements.txt" >> "$DIR/watchdog_$PORT.log" 2>&1
  fi

  if server_alive && curl -fsS --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then
    sleep 15
    continue
  fi

  echo "$(date -u +'%F %T') (re)starting server on $PORT" >> "$DIR/watchdog_$PORT.log"
  if server_alive; then
    kill "$(cat "$PIDFILE")" 2>/dev/null
    rm -f "$PIDFILE"
    sleep 1
  fi
  start_server
  sleep 3
done