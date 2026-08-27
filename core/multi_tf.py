"""Multi-timeframe scalp engine for KLODHIOJKOLOOP.

Resamples the real-time Min1 candle stream into period-aligned candles for all
60 timeframes (1m..60m), computes per-timeframe indicators + scalp signal
(entry / stop / TP1..TP3 from ATR), and runs a lightweight master-agent fusion
that weighs all 60 signals and emits a single IDEAL entry / stop / target.

Data source: market_state.klines_1m (real MEXC Min1 bars). No dummy data.
"""
import numpy as np

from core.indicators import QuantitativeEngine as QE
from core.market_state import market_state

TIMEFRAMES = list(range(1, 61))  # 1 minute .. 60 minutes -> 60 boxes


class TFResult:
    """Computed signal for one timeframe (scalp box)."""
    __slots__ = (
        "tf", "n_bars", "last", "direction", "rsi", "atr", "ema9", "ema21",
        "vwap", "entry", "sl", "tp1", "tp2", "tp3", "risk_dist", "closes",
        "conviction",
    )

    def __init__(self):
        self.tf = 0
        self.n_bars = 0
        self.last = 0.0
        self.direction = "NEUTRAL"
        self.rsi = 50.0
        self.atr = 0.0
        self.ema9 = 0.0
        self.ema21 = 0.0
        self.vwap = 0.0
        self.entry = 0.0
        self.sl = 0.0
        self.tp1 = 0.0
        self.tp2 = 0.0
        self.tp3 = 0.0
        self.risk_dist = 0.0
        self.closes = np.array([], dtype=float)
        self.conviction = 0.0


def resample(candles_1m, n):
    """Aggregate 1-minute candles into period-aligned n-minute OHLCV candles.

    Entries: [openMs, O, H, L, C, V]. Buckets align to the UTC clock
    (minute // n) like real exchange 1m/5m/60m bars.
    """
    if not candles_1m:
        return []
    buckets = {}
    order = []
    for c in candles_1m:
        minute = int(c[0] // 60000)
        key = minute // n
        if key not in buckets:
            buckets[key] = [c[1], c[2], c[3], c[4], c[5], c[0]]
            order.append(key)
        else:
            b = buckets[key]
            if c[2] > b[1]:
                b[1] = c[2]
            if c[3] < b[2]:
                b[2] = c[3]
            b[3] = c[4]
            b[4] += c[5]
    return [[buckets[key][5], buckets[key][0], buckets[key][1],
             buckets[key][2], buckets[key][3], buckets[key][4]] for key in order]


def analyze_timeframe(tf: int) -> TFResult:
    """Compute indicators + scalp signal for one timeframe (scalp box)."""
    r = TFResult()
    r.tf = tf
    base = market_state.klines_1m

    # Need full min1 coverage to build an n-minute series that has completed
    # at least a handful of bars (mature) for the indicators.
    if len(base) < tf:
        return r

    candles = resample(base, tf)
    if len(candles) < 3:
        return r

    closes = np.array([c[4] for c in candles], dtype=float)
    highs = np.array([c[2] for c in candles], dtype=float)
    lows = np.array([c[3] for c in candles], dtype=float)
    r.n_bars = len(candles)
    r.closes = closes

    r.rsi = QE.calculate_rsi(closes)
    r.atr = QE.calculate_atr(closes, highs, lows)
    r.ema9 = QE.calculate_ema(closes, 9)
    r.ema21 = QE.calculate_ema(closes, 21)
    r.vwap = QE.calculate_vwap(candles)

    last = market_state.last_price if market_state.last_price > 0 else closes[-1]
    r.last = last
    r.entry = last

    # Direction (per-timeframe variant of the original 1H rule)
    if last > r.ema9 and r.rsi < 66:
        r.direction = "LONG"
    elif last < r.ema9 and r.rsi > 34:
        r.direction = "SHORT"
    else:
        r.direction = "NEUTRAL"

    if r.atr <= 0.0:
        return r

    stop_dist = max(r.atr, last * 0.002)
    r.risk_dist = stop_dist
    if r.direction == "LONG":
        r.sl = last - stop_dist
        r.tp1 = last + stop_dist
        r.tp2 = last + stop_dist * 1.75
        r.tp3 = last + stop_dist * 2.5
    elif r.direction == "SHORT":
        r.sl = last + stop_dist
        r.tp1 = last - stop_dist
        r.tp2 = last - stop_dist * 1.75
        r.tp3 = last - stop_dist * 2.5
    else:
        r.sl = r.tp1 = r.tp2 = r.tp3 = 0.0

    # Conviction: trend strength + momentum + EMA alignment + candle maturity
    momentum = abs(last - r.ema9) / r.atr if r.atr else 0.0
    rsi_bias = abs(r.rsi - 50.0) / 50.0
    ema_align = 1.0 if r.ema9 >= r.ema21 else -1.0
    maturity = min(r.n_bars, 60) / 60.0
    score = (momentum * 0.5 + rsi_bias * 0.3) * maturity
    if r.direction == "LONG":
        score *= 1.0 if ema_align > 0 else 0.6
        r.conviction = score
    elif r.direction == "SHORT":
        score *= 1.0 if ema_align < 0 else 0.6
        r.conviction = -score
    else:
        r.conviction = 0.10 * ema_align * maturity
    return r


def analyze_all_timeframes():
    """Return ordered dict {tf: TFResult} for 1..60."""
    return {tf: analyze_timeframe(tf) for tf in TIMEFRAMES}


class MasterAgent:
    """Fuses all 60 scalp boxes into one IDEAL entry / stop / target.

    Bullish boxes vote LONG, bearish boxes vote SHORT, weighted by conviction.
    Master direction = side with larger conviction-weighted majority (needs a
    clear lead). IDEAL entry = live price; stop = entry +/- worst-case ATR
    distance from the confident set; targets = risk * R-multiples.
    """

    def __init__(self, results):
        self.results = results
        self.direction = "NEUTRAL"
        self.entry = market_state.last_price
        self.sl = 0.0
        self.tp1 = self.tp2 = self.tp3 = 0.0
        self.risk_dist = 0.0
        self.long_count = self.short_count = self.neutral_count = 0
        self.bull_weight = 0.0
        self.bear_weight = 0.0
        self.winner_tf = 0
        self.fuse()

    @staticmethod
    def _wmean(items):
        num = sum(w * v for w, v in items)
        den = sum(w for w, _ in items)
        return num / den if den else 0.0

    def fuse(self):
        bull = []  # (conviction>0, risk_dist, tf)
        bear = []  # (conviction_abs>0, risk_dist, tf)
        for r in self.results.values():
            if r.direction == "LONG":
                bull.append((max(r.conviction, 1e-4), r.risk_dist, r.tf))
                self.long_count += 1
            elif r.direction == "SHORT":
                bear.append((max(-r.conviction, 1e-4), r.risk_dist, r.tf))
                self.short_count += 1
            else:
                self.neutral_count += 1

        self.bull_weight = sum(w for w, _, _ in bull)
        self.bear_weight = sum(w for w, _, _ in bear)

        if self.bull_weight > self.bear_weight * 1.15 and self.long_count >= 3:
            self.direction = "LONG"
            pool = bull
        elif self.bear_weight > self.bull_weight * 1.15 and self.short_count >= 3:
            self.direction = "SHORT"
            pool = bear
        else:
            self.direction = "NEUTRAL"
            pool = []

        if pool:
            side = 1 if self.direction == "LONG" else -1
            confident = [risk for w, risk, _ in pool if w >= 0.05]
            avg_risk = self._wmean([(w, risk) for w, risk, _ in pool])
            self.risk_dist = max(confident) if confident else avg_risk
            self.winner_tf = max(pool, key=lambda x: x[0])[2]

            self.entry = market_state.last_price
            self.sl = self.entry - side * self.risk_dist
            self.tp1 = self.entry + side * self.risk_dist
            self.tp2 = self.entry + side * self.risk_dist * 1.75
            self.tp3 = self.entry + side * self.risk_dist * 2.5
        else:
            self.entry = market_state.last_price
            self.risk_dist = 0.0
            self.winner_tf = 0