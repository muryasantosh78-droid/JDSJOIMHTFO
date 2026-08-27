# AGENTS.md — MEXC XAU/USDT Scalp Terminal

## Project
Bloomberg-style XAU/USD scalp terminal on **MEXC Futures XAU_USDT perpetual** (the only real XAU/USDT gold instrument on MEXC; spot only lists GOLD(XAUT) which is Tether Gold, NOT XAU. PAXG explicitly excluded).

## Verified MEXC Futures integration facts (empirically probed 2026-08-26)
- REST: `https://contract.mexc.com`
- WS: `wss://contract.mexc.com/edge`; subscribe w/ JSON `{"method":"sub.X","param":{...}}`; app-level ping `{"method":"ping"}` → `{"channel":"pong"}`; data arrives on `push.*` channels, acks on `rs.sub.*`.
- Public channels (verified vs Tardis.dev raw channel capture): `push.deal`, `push.depth`, `push.kline`, `push.ticker`, `push.index.price`, `push.fair.price`, `push.funding.rate`, `push.contract`.
- **No public liquidation/forceOrder channel exists on MEXC** (only private position liquidations). Cascade FSM stays dormant; HUD says so honestly. Never fake liq data.
- `push.deal` entries: `p`=price, `v`=contracts, `T`=1 taker buy / 2 taker sell, `t`=ms epoch.
- `push.depth` level tuple: `[price, contracts, unused]`; ticker's `holdVol`=open interest in contracts (~1 contract = 1 USD face), `amount24`=notional USDT.
- Kline REST `GET /api/v1/contract/kline/{sym}?interval=Min1` returns parallel arrays `time/open/high/low/close/vol/amount` (seconds epoch). Supported intervals: Min1, Min5, Min15, Min30, Min60 (1H), Hour4, Hour12, Day1, Week1, Month1. **Hour1 is INVALID** (error 600); use Min60 for 1H. Terminal timeframe set via `KLINE_INTERVAL` in config.py (currently Min60).
- `XAU_USDT` specs via `contract/detail`: priceScale=2, volScale=0 (integer contracts), minVol=1, maxLeverage=1000.
- Futures signing: headers `ApiKey`, `Request-Time` (ms), `Signature` = HMAC-SHA256(secret, apiKey + requestTime + signatureString). No credentials → SIMULATED mode.

## Run
`pip install -r requirements.txt && python main.py` (rich Live TUI; `_ws_loop` reconnects; UI render function safe to call standalone for tests).

## Web mode
`python web/server.py` serves the same dashboard as auto-refreshing HTML (1s meta refresh, rich `export_html(inline_styles=True)` — note: `export_html` has NO `title` kwarg in installed rich) on port 12000, exposed at https://work-1-pxmkgtdctetxvvfp.prod-runtime.all-hands.dev/ . Port 12001 → work-2 host. Launch detached: `setsid nohup python3 web/server.py > web_server.log 2>&1 &`. NOTE: terminal tool `reset` kills plain nohup children — always use setsid. web/server.py inserts project root into sys.path itself (run from anywhere).
