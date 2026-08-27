import os

# ---------------------------------------------------------------------------
# MEXC Futures (contract) endpoints - the ONLY exchange venue where a real
# XAU/USDT gold perpetual exists on MEXC (spot lists GOLD(XAUT) which is
# Tether Gold, NOT the requested XAU instrument). 100% real MEXC data only.
# ---------------------------------------------------------------------------
REST_BASE = "https://contract.mexc.com"
WS_BASE = "wss://contract.mexc.com/edge"
SYMBOL = "XAU_USDT"          # MEXC Futures XAU/USDT perpetual contract
SYMBOL_DISPLAY = "XAU/USDT"  # UI label

# API Credentials (Optional: leave empty for live telemetry-only mode)
MEXC_API_KEY = os.getenv("MEXC_API_KEY", "")
MEXC_API_SECRET = os.getenv("MEXC_API_SECRET", "")

# Scalp timeframe: "Min1" | "Min5" | "Min15" | "Min30" | "Min60" (1h) | "Hour4" ...
KLINE_INTERVAL = "Min60"

# Risk & Strategy Constraints
EQUITY_USD = 10_000.0
RISK_PER_TRADE_PCT = 0.01    # 1% equity risk
MAX_LEVERAGE = 10            # venue allows up to 1000x; capped here for sanity
CASCADE_THRESHOLD_USD = 1_000_000   # $1M liquidations in 10s to arm
VELOCITY_THRESHOLD_USD_S = 100_000  # $100k/sec liquidation burst

# MEXC linear perp convention: 1 contract ~= 1 USD face value. Used for
# contracts -> USD conversions in risk sizing and HUD displays.
CONTRACT_USD_VALUE = 1.0

# Runtime feed mode: "FUTURES" (MEXC contract) or "OFFLINE" when unreachable.
# NOTE: MEXC has NO public liquidation/forceOrder feed (confirmed vs channel
# list captured by Tardis.dev - only public deal/depth/kline/ticker/index/
# fair/funding channels exist). The cascade FSM therefore stays dormant and
# is surfaced honestly in the HUD instead of being fed dummy data.
FEED_MODE = "FUTURES"
LIQUIDATION_FEED = False


def mark_feed_offline():
    global FEED_MODE
    FEED_MODE = "OFFLINE"


def futures_feeds_live() -> bool:
    """Futures streams (deal/depth/kline/ticker/funding) availability."""
    return FEED_MODE == "FUTURES"


def liquidation_feed_live() -> bool:
    """Public forced-liquidation feed availability (always False on MEXC)."""
    return LIQUIDATION_FEED


# Price / Qty formatting tuned for MEXC XAU_USDT (priceScale=2, volScale=0)
PRICE_PRECISION = 2
QTY_PRECISION = 0
