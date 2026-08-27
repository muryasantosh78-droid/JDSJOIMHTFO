import time
from collections import deque
from config import CASCADE_THRESHOLD_USD, VELOCITY_THRESHOLD_USD_S


class LiquidationEngine:
    """IDLE -> ARMED -> EXHAUSTING -> TRIGGERED cascade FSM for XAU_USDT.

    Fed by a public forced-liquidation stream when one exists. MEXC Futures
    exposes no public liquidation channel (only private position-liq warnings),
    so on this venue the engine receives no events and stays IDLE - displayed
    honestly in the HUD rather than fed dummy data.
    """

    def __init__(self, window_sec=60):
        self.window_sec = window_sec
        self.events = deque()
        self.recent_tape = deque(maxlen=8)
        self.state = "IDLE"
        self.armed_timestamp = 0
        self.peak_velocity = 0.0
        self.cascade_side = None
        self.wick_extreme = 0.0

    def register_event(self, side: str, qty: float, price: float):
        now = time.time()
        usd = qty * price
        self.events.append((now, side, qty, price, usd))
        self.recent_tape.appendleft((now, side, qty, price, usd))
        self._prune(now)

    def _prune(self, now: float):
        cutoff = now - self.window_sec
        while self.events and self.events[0][0] < cutoff:
            self.events.popleft()

    def update(self, current_price: float, recent_cvd_delta: float) -> dict:
        now = time.time()
        self._prune(now)

        cutoff_10s = now - 10.0
        long_10s = sum(e[4] for e in self.events if e[0] >= cutoff_10s and e[1] == "SELL")
        short_10s = sum(e[4] for e in self.events if e[0] >= cutoff_10s and e[1] == "BUY")
        velocity = (long_10s + short_10s) / 10.0

        action = None

        if self.state == "IDLE":
            if long_10s >= CASCADE_THRESHOLD_USD and velocity >= VELOCITY_THRESHOLD_USD_S:
                self.state = "ARMED"
                self.cascade_side = "LONG_LIQ"
                self.armed_timestamp = now
                self.peak_velocity = velocity
                self.wick_extreme = current_price
            elif short_10s >= CASCADE_THRESHOLD_USD and velocity >= VELOCITY_THRESHOLD_USD_S:
                self.state = "ARMED"
                self.cascade_side = "SHORT_LIQ"
                self.armed_timestamp = now
                self.peak_velocity = velocity
                self.wick_extreme = current_price

        elif self.state == "ARMED":
            self.peak_velocity = max(self.peak_velocity, velocity)
            if self.cascade_side == "LONG_LIQ":
                self.wick_extreme = min(self.wick_extreme, current_price)
            else:
                self.wick_extreme = max(self.wick_extreme, current_price)

            if velocity < (self.peak_velocity * 0.5):
                self.state = "EXHAUSTING"

            if now - self.armed_timestamp > 20.0:
                self.state = "IDLE"

        elif self.state == "EXHAUSTING":
            if self.cascade_side == "LONG_LIQ" and recent_cvd_delta > 0.5:
                action = "BUY_CAPITULATION"
                self.state = "TRIGGERED"
            elif self.cascade_side == "SHORT_LIQ" and recent_cvd_delta < -0.5:
                action = "SELL_SQUEEZE"
                self.state = "TRIGGERED"

            if now - self.armed_timestamp > 25.0:
                self.state = "IDLE"

        elif self.state == "TRIGGERED":
            if now - self.armed_timestamp > 30.0:
                self.state = "IDLE"

        return {
            "state": self.state,
            "side": self.cascade_side,
            "velocity": velocity,
            "peak_velocity": self.peak_velocity,
            "long_10s": long_10s,
            "short_10s": short_10s,
            "wick_extreme": self.wick_extreme,
            "action": action,
            "tape": list(self.recent_tape)
        }


liquidation_engine = LiquidationEngine()
