import asyncio
import json
import time
import websockets
from config import WS_BASE, SYMBOL, KLINE_INTERVAL, futures_feeds_live, liquidation_feed_live
from core.market_state import market_state


async def _ws_loop(subscriptions, channel_handler):
    """Reconnect-safe MEXC futures WS: subscribes on connect, app-level ping
    every 15s (server requires {"method":"ping"}), routes push.* to handler."""
    while True:
        if not futures_feeds_live():
            return
        try:
            async with websockets.connect(
                WS_BASE, ping_interval=20, ping_timeout=10, open_timeout=15
            ) as ws:
                async def pinger():
                    while True:
                        await asyncio.sleep(15)
                        await ws.send(json.dumps({"method": "ping"}))

                ping_task = asyncio.create_task(pinger())
                for sub in subscriptions:
                    await ws.send(json.dumps(sub))
                    await asyncio.sleep(0.15)
                try:
                    async for msg in ws:
                        data = json.loads(msg)
                        channel = data.get("channel", "")
                        if channel.startswith("push."):
                            channel_handler(data)
                finally:
                    ping_task.cancel()
        except Exception:
            await asyncio.sleep(1)


def _on_deal(data):
    for trade in data.get("data", []):
        price = float(trade["p"])
        qty = float(trade["v"])
        # MEXC T side: 1 = taker buy, 2 = taker sell
        is_buy = trade["T"] == 1
        recv_ms = time.time() * 1000

        market_state.network_latency_ms = max(0.0, recv_ms - float(trade.get("t", data.get("ts", 0))))
        market_state.last_price = price
        market_state.last_update_ts = time.time()

        delta = qty if is_buy else -qty
        market_state.cvd += delta

        now = time.time()
        market_state.trade_events_5s.append((now, delta))
        cutoff = now - 5.0
        while market_state.trade_events_5s and market_state.trade_events_5s[0][0] < cutoff:
            market_state.trade_events_5s.popleft()
        market_state.recent_cvd_5s = sum(t[1] for t in market_state.trade_events_5s)

        market_state.trade_tape.appendleft((now, price, qty, is_buy))


def _on_depth(data):
    book = data.get("data", {})
    # MEXC depth levels: [price, contracts, ?]
    market_state.bids = [(float(x[0]), float(x[1])) for x in book.get("bids", [])]
    market_state.asks = [(float(x[0]), float(x[1])) for x in book.get("asks", [])]

    top10_bid = sum(q for _, q in market_state.bids[:10])
    top10_ask = sum(q for _, q in market_state.asks[:10])
    if top10_bid + top10_ask > 0:
        market_state.ob_imbalance = ((top10_bid - top10_ask) / (top10_bid + top10_ask)) * 100.0


def _on_kline(data):
    k = data.get("data", {})
    candle_ms = float(k["t"]) * 1000.0
    candle = [candle_ms, float(k["o"]), float(k["h"]), float(k["l"]), float(k["c"]), float(k["q"])]
    if market_state.klines_1m and market_state.klines_1m[-1][0] != candle_ms:
        market_state.klines_1m.append(candle)
    elif market_state.klines_1m:
        market_state.klines_1m[-1] = candle
    else:
        market_state.klines_1m.append(candle)


def _on_ticker(data):
    d = data.get("data", {})
    if d.get("lastPrice") is not None:
        market_state.last_price = float(d["lastPrice"])
    if d.get("fairPrice") is not None:
        market_state.mark_price = float(d["fairPrice"])
    if d.get("indexPrice") is not None:
        market_state.index_price = float(d["indexPrice"])
    if d.get("fundingRate") is not None:
        market_state.funding_rate = float(d["fundingRate"])
    if d.get("holdVol") is not None:
        market_state.open_interest = float(d["holdVol"])  # contracts
    if d.get("amount24") is not None:
        market_state.volume_24_usdt = float(d["amount24"])
    if d.get("high24Price") is not None:
        market_state.high_24 = float(d["high24Price"])
    if d.get("lower24Price") is not None:
        market_state.low_24 = float(d["lower24Price"])


async def ws_trade_stream():
    await _ws_loop([{"method": "sub.deal", "param": {"symbol": SYMBOL}}], _on_deal)


async def ws_depth_stream():
    await _ws_loop(
        [{"method": "sub.depth", "param": {"symbol": SYMBOL, "depth": 20}}],
        _on_depth,
    )


async def ws_kline_stream():
    await _ws_loop(
        [{"method": "sub.kline", "param": {"symbol": SYMBOL, "interval": KLINE_INTERVAL}}],
        _on_kline,
    )


async def ws_mark_price_stream():
    await _ws_loop(
        [{"method": "sub.ticker", "param": {"symbol": SYMBOL}}], _on_ticker
    )


async def ws_force_order_stream():
    """MEXC Futures exposes no public forced-liquidation channel (verified
    against the full raw channel inventory captured by Tardis.dev: deal,
    depth, kline, ticker, index.price, fair.price, funding.rate, contract).
    The cascade FSM therefore stays dormant; the HUD shows that honestly."""
    if not liquidation_feed_live():
        return
