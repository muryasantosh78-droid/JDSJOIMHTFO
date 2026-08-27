import hashlib
import hmac
import json
import time
import aiohttp
from config import (
    MEXC_API_KEY,
    MEXC_API_SECRET,
    REST_BASE,
    SYMBOL,
    EQUITY_USD,
    RISK_PER_TRADE_PCT,
    MAX_LEVERAGE,
    PRICE_PRECISION,
    QTY_PRECISION,
    CONTRACT_USD_VALUE,
)


class OrderExecutionEngine:
    """MEXC Futures order engine. Without API credentials it runs in
    telemetry-only simulated mode, exactly like the monitor-only bootstrap."""

    def __init__(self):
        self.api_key = MEXC_API_KEY
        self.api_secret = MEXC_API_SECRET
        self.has_credentials = bool(self.api_key and self.api_secret)

    def _auth_headers(self, signature_string: str) -> dict:
        # MEXC futures signing: HMAC-SHA256(secret, apiKey + requestTime + sigStr)
        req_time = str(int(time.time() * 1000))
        raw = self.api_key + req_time + signature_string
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            raw.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return {
            "ApiKey": self.api_key,
            "Request-Time": req_time,
            "Signature": signature,
            "Content-Type": "application/json",
        }

    def calculate_position_parameters(self, entry_price: float, sl_price: float):
        risk_usd = EQUITY_USD * RISK_PER_TRADE_PCT
        stop_dist = max(abs(entry_price - sl_price), entry_price * 0.001)
        # 1 contract ~= $1 face value on MEXC linear perps -> contracts = risk/dist
        size_contracts = risk_usd / (stop_dist * CONTRACT_USD_VALUE)
        max_size = (EQUITY_USD * MAX_LEVERAGE) / (entry_price * CONTRACT_USD_VALUE)
        final_size = round(min(size_contracts, max_size), QTY_PRECISION)
        if final_size < 1:
            final_size = 1  # MEXC minVol = 1 contract
        return final_size, stop_dist

    async def execute_bracket(self, side: str, qty: float, sl: float, tp1: float, tp2: float):
        if not self.has_credentials:
            return {
                "status": "SIMULATED_SUCCESS",
                "side": side,
                "qty": qty,
                "sl": sl,
                "tp1": tp1,
                "tp2": tp2,
            }

        # MEXC futures order submits over /private endpoints (live mode only).
        url = f"{REST_BASE}/api/v1/private/order/submit"
        open_type = 1 if side == "BUY" else 3  # 1=open long, 3=open short

        async with aiohttp.ClientSession() as session:
            # 1. Market entry
            body = {
                "symbol": SYMBOL,
                "side": open_type,
                "orderType": 1,
                "vol": int(qty),
                "pricePrecision": PRICE_PRECISION,
            }
            raw = json.dumps(body)
            async with session.post(url, data=raw, headers=self._auth_headers(raw)) as resp:
                entry_res = await resp.json()

            # 2. Stop-loss plan order (closePosition via triggerType 6 = stop)
            sl_body = {
                "symbol": SYMBOL,
                "side": 2 if open_type == 1 else 4,  # close direction
                "orderType": 1,
                "vol": int(qty),
                "triggerPrice": round(sl, PRICE_PRECISION),
                "triggerType": 6,
                "executCycle": 1,
            }
            raw = json.dumps(sl_body)
            async with session.post(
                f"{REST_BASE}/api/v1/private/plan/submit",
                data=raw,
                headers=self._auth_headers(raw),
            ):
                pass

            # 3. Take profit on 50% via triggerType 1 plan (take-profit)
            tp_body = {
                "symbol": SYMBOL,
                "side": 2 if open_type == 1 else 4,
                "orderType": 1,
                "vol": max(1, int(qty * 0.5)),
                "triggerPrice": round(tp1, PRICE_PRECISION),
                "triggerType": 1,
                "executCycle": 1,
            }
            raw = json.dumps(tp_body)
            async with session.post(
                f"{REST_BASE}/api/v1/private/plan/submit",
                data=raw,
                headers=self._auth_headers(raw),
            ):
                pass

            return entry_res


trade_executor = OrderExecutionEngine()
