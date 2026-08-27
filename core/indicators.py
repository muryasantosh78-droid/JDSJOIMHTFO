import numpy as np


class QuantitativeEngine:
    @staticmethod
    def calculate_atr(closes, highs, lows, period=14):
        if len(closes) < period + 1:
            return 0.0
        trs = [
            max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
            for i in range(1, len(closes))
        ]
        atr = trs[0]
        for tr in trs[1:]:
            atr = (atr * (period - 1) + tr) / period
        return atr

    @staticmethod
    def calculate_rsi(closes, period=14):
        if len(closes) < period + 1:
            return 50.0
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def calculate_ema(data, period):
        if len(data) < period:
            return data[-1] if len(data) > 0 else 0.0
        alpha = 2 / (period + 1)
        ema = data[0]
        for val in data[1:]:
            ema = alpha * val + (1 - alpha) * ema
        return ema

    @staticmethod
    def calculate_vwap(klines):
        if not klines:
            return 0.0
        cum_pv = sum(((float(k[2]) + float(k[3]) + float(k[4])) / 3.0) * float(k[5]) for k in klines)
        cum_vol = sum(float(k[5]) for k in klines)
        return cum_pv / cum_vol if cum_vol > 0 else 0.0

    @staticmethod
    def calculate_micro_price(bids, asks):
        if not bids or not asks:
            return 0.0
        best_bid, bid_qty = bids[0]
        best_ask, ask_qty = asks[0]
        total_qty = bid_qty + ask_qty
        if total_qty == 0:
            return (best_bid + best_ask) / 2.0
        return (best_bid * (ask_qty / total_qty)) + (best_ask * (bid_qty / total_qty))

    @staticmethod
    def calculate_ofi(current_bids, current_asks, prev_bids, prev_asks, levels=5):
        if not prev_bids or not prev_asks or not current_bids or not current_asks:
            return 0.0
        ofi = 0.0
        for i in range(min(levels, len(current_bids), len(prev_bids))):
            curr_p, curr_q = current_bids[i]
            prev_p, prev_q = prev_bids[i]
            if curr_p > prev_p:
                ofi += curr_q
            elif curr_p == prev_p:
                ofi += (curr_q - prev_q)
            else:
                ofi -= prev_q

        for i in range(min(levels, len(current_asks), len(prev_asks))):
            curr_p, curr_q = current_asks[i]
            prev_p, prev_q = prev_asks[i]
            if curr_p < prev_p:
                ofi -= curr_q
            elif curr_p == prev_p:
                ofi -= (curr_q - prev_q)
            else:
                ofi += prev_q
        return ofi
