import time
from collections import deque


class MarketState:
    def __init__(self):
        # Ticker & Pricing
        self.last_price = 0.0
        self.mark_price = 0.0        # MEXC fairPrice (futures mark)
        self.index_price = 0.0       # MEXC indexPrice
        self.funding_rate = 0.0
        self.next_funding_time = 0
        self.open_interest = 0.0     # holdVol contracts -> USD for display
        self.volume_24_usdt = 0.0    # MEXC amount24 (notional USDT)
        self.high_24 = 0.0
        self.low_24 = 0.0

        # Order Book Top-20 (Price, Qty)
        self.bids = []
        self.asks = []
        self.ob_imbalance = 0.0

        # Flow & Microstructure
        self.cvd = 0.0
        self.trade_tape = deque(maxlen=20)
        self.trade_events_5s = deque()
        self.recent_cvd_5s = 0.0

        # Klines (1m: [OpenTimeMs, O, H, L, C, V])
        self.klines_1m = deque(maxlen=200)

        # Latency
        self.network_latency_ms = 0.0
        self.last_update_ts = time.time()


market_state = MarketState()
