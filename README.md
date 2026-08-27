# KLODHIOJKOLOOP — MEXC XAU/USDT Bloomberg-Style Scalp Terminal

Real-time scaling terminal for **XAU/USDT** on **MEXC Futures** (XAU_USDT gold perpetual).
Bloomberg-style layout with **60 different scalp boxes (1m..60m)**, live trade signals,
order book, tape, and indicators.
**100% real live data** from the MEXC public API — no dummy/backtest data.

## Features
- **60 TIMEFRAME SCALP BOXES (1m, 2m, ..., 60m)** — each a real scalp signal
  (direction, entry, stop-loss, TP1/TP2/TP3 from ATR) computed by resampling the
  live Min1 candle stream into period-aligned candles for every window
- **MASTER AGENT (60-TIMEFRAME FUSION)** — weighs all 60 signals by conviction
  (trend strength + momentum + EMA alignment + candle maturity) and emits a single
  **IDEAL ENTRY / IDEAL STOP LOSS / IDEAL TARGET TP1..TP3** with the leading timeframe
- Mini candle sparkline chart in every scalp box
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
core/market_state.py      # shared state: forming, tape, CVD, Min1 klines
core/indicators.py        # RSI, ATR, EMA, VWAP, micro-price, OFI
core/multi_tf.py          # 60-TF resampler (1m..60m) + per-TF signals + MASTER AGENT
core/liquidation_engine.py# FSM (idle->armed->exhausting->triggered)
network/rest_client.py    # snapshot bootstrap (2000 Min1 klines, OI, ticker)
network/streams.py        # live WS: deal, depth, Min1 kline, mark price
execution/trade_manager.py# HMAC-signed bracket orders (simulated w/o keys)
ui/terminal_ui.py         # Bloomberg renderer (60 scalp boxes + IDEAL panel)
web/server.py             # auto-refreshing web wrapper
main.py                   # orchestrator + live renderer
watchdog.sh               # per-port auto-restart watchdog
```

## How the 60 timeframes work
One live **Min1** WebSocket stream is subscribed and a 2000-bar Min1 bootstrap is
fetched once. `core/multi_tf.py` resamples that single real feed into
period-aligned candles for every window from 1m to 60m (buckets align to the
UTC clock), then computes RSI/ATR/EMA9/21/VWAP and the scalp signal for each.
The **master agent** fuses all 60 by conviction weighting and reports the single
**IDEAL ENTRY / STOP LOSS / TARGET** plus the leading timeframe.

## Data source
MEXC Futures public API:
- REST: `https://contract.mexc.com/api/v1/contract/...`
- WebSocket: `wss://contract.mexc.com/edge`
- Symbol `XAU_USDT`, priceScale 2, min volume 1 contract, max leverage 1000

> Note: MEXC has no public liquidation feed; the liquidation metter is honest about that.
> Use this tool for education/research. Crypto/gold derivatives carry high risk.