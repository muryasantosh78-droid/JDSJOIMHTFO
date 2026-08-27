#!/usr/bin/env bash
# Scalp terminal entrypoint: starts MEXC XAU/USDT TUI on the real
# XAU_USDT futures perpetual. Usage:
#   ./run_terminal.sh            # attach (needs a TTY; use via `bash` in a terminal)
#   ./run_terminal.sh --status   # check if background instance is up
#   ./run_terminal.sh --stop     # stop background instance
#   ./run_terminal.sh --snapshot # dump one rendered frame headlessly
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$DIR/terminal.log"
PIDFILE="/tmp/mexc_xau_terminal.pid"

case "${1:-}" in
  --status)
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "MEXC XAU/USDT terminal RUNNING (pid $(cat "$PIDFILE"))"
    else echo "not running"; fi ;;
  --stop)
    if [ -f "$PIDFILE" ]; then kill "$(cat "$PIDFILE")" 2>/dev/null && rm -f "$PIDFILE"; echo stopped; fi ;;
  --snapshot)
    cd "$DIR"
    exec python3 - <<'PYEOF'
import asyncio, io
from rich.console import Console
from network.rest_client import bootstrap_market_snapshot
from network.streams import ws_depth_stream, ws_kline_stream, ws_mark_price_stream, ws_trade_stream
from ui.terminal_ui import render_bloomberg_dashboard
async def main():
    await bootstrap_market_snapshot()
    tasks = [asyncio.create_task(t()) for t in (ws_trade_stream, ws_depth_stream, ws_kline_stream, ws_mark_price_stream)]
    await asyncio.sleep(10)
    buf = io.StringIO()
    c = Console(file=buf, width=160, height=50)
    c.print(render_bloomberg_dashboard())
    for t in tasks: t.cancel()
    print(buf.getvalue())
asyncio.run(main())
PYEOF
    ;;
  --start-bg|--start)
    cd "$DIR"
    nohup python main.py >"$LOG" 2>&1 &
    echo $! >"$PIDFILE"
    echo "started bg pid $(cat "$PIDFILE") log=$LOG" ;;
  *)
    cd "$DIR"
    exec python main.py ;;
esac
