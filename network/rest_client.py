import aiohttp
from config import REST_BASE, SYMBOL, futures_feeds_live, mark_feed_offline


async def detect_feed_mode():
    """Probe the MEXC futures REST endpoint to verify reachability."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{REST_BASE}/api/v1/contract/ping",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    return
    except Exception:
        pass
    mark_feed_offline()
    print("[ERROR] MEXC Futures REST unreachable. Terminal will run with stale bootstrap only.")


async def bootstrap_market_snapshot():
    await detect_feed_mode()
    if not futures_feeds_live():
        return

    async with aiohttp.ClientSession() as session:
        # 1. Fetch Min1 Klines (port the parallel-array payload to [t,o,h,l,c,v]).
        #    A single 2000-bar Min1 pull lets us resample all 60 timeframes
        #    (1m..60m) locally from the same real source. MEXC caps at 2000.
        try:
            kline_url = f"{REST_BASE}/api/v1/contract/kline/{SYMBOL}?interval=Min1&limit=2000"
            async with session.get(kline_url) as resp:
                if resp.status == 200:
                    payload = await resp.json()
                    data = payload.get("data") or {}
                    times = data.get("time", [])
                    opens = data.get("open", [])
                    highs = data.get("high", [])
                    lows = data.get("low", [])
                    closes = data.get("close", [])
                    vols = data.get("vol", [])
                    from core.market_state import market_state
                    candles = [
                        [float(times[i]) * 1000.0, float(opens[i]), float(highs[i]),
                         float(lows[i]), float(closes[i]), float(vols[i])]
                        for i in range(len(times))
                    ]
                    market_state.klines_1m.extend(candles)
        except Exception:
            pass

        # 2. Fetch Funding Rate (collectCycle=4h on MEXC XAU_USDT)
        try:
            async with session.get(f"{REST_BASE}/api/v1/contract/funding_rate/{SYMBOL}") as resp:
                if resp.status == 200:
                    data = (await resp.json()).get("data") or {}
                    from core.market_state import market_state
                    market_state.funding_rate = float(data.get("fundingRate", 0))
                    market_state.next_funding_time = int(data.get("nextSettleTime", 0))
        except Exception:
            pass

        # 3. Fetch Ticker: fairPrice (mark), indexPrice, holdVol (open interest)
        try:
            async with session.get(f"{REST_BASE}/api/v1/contract/ticker?symbol={SYMBOL}") as resp:
                if resp.status == 200:
                    data = (await resp.json()).get("data") or {}
                    from core.market_state import market_state
                    market_state.last_price = float(data.get("lastPrice", 0))
                    market_state.mark_price = float(data.get("fairPrice", 0))
                    market_state.index_price = float(data.get("indexPrice", 0))
                    market_state.open_interest = float(data.get("holdVol", 0))
                    market_state.volume_24_usdt = float(data.get("amount24", 0))
                    market_state.high_24 = float(data.get("high24Price", 0))
                    market_state.low_24 = float(data.get("lower24Price", 0))
                    if data.get("fundingRate") is not None:
                        market_state.funding_rate = float(data.get("fundingRate", 0))
        except Exception:
            pass
