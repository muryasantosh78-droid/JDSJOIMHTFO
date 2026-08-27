# KLODHIOJKOLOOP — MEXC XAU/USDT Bloomberg-Style Scalp Terminal

Real-time scaling terminal for **XAU/USDT** on **MEXC Futures** (XAU_USDT gold perpetual).
Bloomberg-style layout with live 1H trade signals, order book, tape, and indicators.
**100% real live data** from the MEXC public API — no dummy/backtest data.

## Features
- Live 1H scalping signal band (direction, entry, stop-loss, TP1/TP2/TP3 from ATR)
- L2 order book with bid/ask imbalance
- Real-time aggregated deal tape (BUY/SELL)
- RSI(14), ATR(14), EMA9/21, VWAP, micro-price, fair/index price
- Open interest, 24h turnover/high/low, funding rate
- Auto-reconnecting WebSocket streams with app-level ping
- Automatic failover + per-port watchdog (`watchdog.sh`)
- Optional real trading via MEXC API keys (HMAC-SHA256 signed); simulated without keys

## Setup
```bash
pip install -r requirements.txt
```

## Run (terminal UI)
```bash
python main.py
```

## Run (browser / web server, port 12000)
```bash
python web/server.py
# or with auto-restart watchdog:
setsid nohup ./watchdog.sh > watchdog.log 2>&1 &
setsid nohup env PORT=12001 ./watchdog.sh > watchdog2.log 2>&1 &
```

## Configuration
`config.py`:
- `KLINE_INTERVAL` = `Min60` (1H). Other options: Min1, Min5, Min15, Min30, Hour4, ...
- `MEXC_API_KEY` / `MEXC_API_SECRET` — set to enable live order execution (optional)
- `EQUITY_USD`, `RISK_PER_TRADE_PCT`, `MAX_LEVERAGE` — risk parameters

## Project structure
```
config.py                 # endpoints, timeframe, risk params
core/market_state.py      # shared state: book, tape, CVD, klines
core/indicators.py        # RSI, ATR, EMA, VWAP, micro-price, OFI
core/liquidation_engine.py# FSM (idle->armed->exhausting->triggered)
network/rest_client.py    # snapshot bootstrap (200x klines, OI, ticker)
network/streams.py        # live WS: deal, depth, kline, mark price
execution/trade_manager.py# HMAC-signed bracket orders (simulated w/o keys)
ui/terminal_ui.py         # Bloomberg layout renderer
web/server.py             # auto-refreshing web wrapper
main.py                   # orchestrator + live renderer
watchdog.sh               # per-port auto-restart watchdog
```

## Data source
MEXC Futures public API:
- REST: `https://contract.mexc.com/api/v1/contract/...`
- WebSocket: `wss://contract.mexc.com/edge`
- Symbol `XAU_USDT`, priceScale 2, min volume 1 contract, max leverage 1000

> Note: MEXC has no public liquidation feed; the liquidation metter is honest about that.
> Use this tool for education/research. Crypto/gold derivatives carry high risk.