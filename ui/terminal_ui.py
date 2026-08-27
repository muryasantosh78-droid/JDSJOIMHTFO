from datetime import datetime, timezone
import numpy as np
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import config
from config import futures_feeds_live, liquidation_feed_live, PRICE_PRECISION, QTY_PRECISION, CONTRACT_USD_VALUE, SYMBOL_DISPLAY
from core.indicators import QuantitativeEngine
from core.liquidation_engine import liquidation_engine
from core.market_state import market_state


def render_bloomberg_dashboard() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="signal_band", size=7),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=3)
    )
    layout["main"].split_row(
        Layout(name="left", ratio=1),
        Layout(name="right", ratio=1)
    )
    layout["left"].split_column(
        Layout(name="orderbook", ratio=1),
        Layout(name="tape", ratio=1)
    )
    layout["right"].split_column(
        Layout(name="signal_hud", ratio=1),
        Layout(name="liquidation_hud", ratio=1)
    )

    # 1. Header
    utc_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    feed_tag = "MEXC FUTURES" if futures_feeds_live() else "STALE (OFFLINE)"
    header_panel = Panel(
        Text(f" 🥇 BLOOMBERG {SYMBOL_DISPLAY} SCALP TERMINAL | LIVE {feed_tag} | UTC: {utc_str} | LATENCY: {market_state.network_latency_ms:.1f}ms ", style="bold white on dark_blue"),
        style="dark_blue"
    )
    layout["header"].update(header_panel)

    # Calculate indicators
    closes = np.array([k[4] for k in market_state.klines_1m]) if len(market_state.klines_1m) > 1 else np.array([market_state.last_price])
    highs = np.array([k[2] for k in market_state.klines_1m]) if len(market_state.klines_1m) > 1 else np.array([market_state.last_price])
    lows = np.array([k[3] for k in market_state.klines_1m]) if len(market_state.klines_1m) > 1 else np.array([market_state.last_price])

    rsi = QuantitativeEngine.calculate_rsi(closes)
    atr = QuantitativeEngine.calculate_atr(closes, highs, lows)
    vwap = QuantitativeEngine.calculate_vwap(market_state.klines_1m)
    ema_9 = QuantitativeEngine.calculate_ema(closes, 9)
    ema_21 = QuantitativeEngine.calculate_ema(closes, 21)
    micro_price = QuantitativeEngine.calculate_micro_price(market_state.bids, market_state.asks)

    # Scalp signal (1h timeframe): direction + entry/stop/tps from real ATR
    last = market_state.last_price
    direction = "LONG" if last > ema_9 and rsi < 60 else "SHORT" if last < ema_9 and rsi > 40 else "NEUTRAL"
    sig_color = "green" if direction == "LONG" else "red" if direction == "SHORT" else "yellow"

    # 1h ATR-based stop, $2 floor (1h ATR ~ 5-15 on gold)
    stop_dist = max(atr, last * 0.002)
    entry = last
    if direction == "LONG":
        sl = entry - stop_dist
        tp1 = entry + stop_dist
        tp2 = entry + stop_dist * 1.75
        tp3 = entry + stop_dist * 2.5
    elif direction == "SHORT":
        sl = entry + stop_dist
        tp1 = entry - stop_dist
        tp2 = entry - stop_dist * 1.75
        tp3 = entry - stop_dist * 2.5
    else:
        sl = tp1 = tp2 = tp3 = 0.0

    # 2. Horizontal scalp-trade signal band
    sig_box = Table(expand=True, box=None, padding=(0, 1))
    sig_box.add_column("SIGNAL", justify="left", style="bold")
    sig_box.add_column("TIMEFRAME", justify="center", style="bold magenta")
    sig_box.add_column("DIRECTION", justify="center", style="bold")
    sig_box.add_column("ENTRY", justify="right", style="bold cyan")
    sig_box.add_column("STOP LOSS", justify="right", style="bold red")
    sig_box.add_column("TP1", justify="right", style="bold green")
    sig_box.add_column("TP2", justify="right", style="bold green")
    sig_box.add_column("TP3", justify="right", style="bold green")
    sig_box.add_column("RISK DIST", justify="right", style="dim")
    sig_box.add_column("TIMESTAMP", justify="right", style="dim")

    arrow = "▲" if direction == "LONG" else "▼" if direction == "SHORT" else "●"
    tf_label = "1H"
    entry_txt = f"{entry:,.{PRICE_PRECISION}f}" if direction != "NEUTRAL" else "STAND BY"
    sl_txt = f"{sl:,.{PRICE_PRECISION}f}" if direction != "NEUTRAL" else "—"
    tp1_txt = f"{tp1:,.{PRICE_PRECISION}f}" if direction != "NEUTRAL" else "—"
    tp2_txt = f"{tp2:,.{PRICE_PRECISION}f}" if direction != "NEUTRAL" else "—"
    tp3_txt = f"{tp3:,.{PRICE_PRECISION}f}" if direction != "NEUTRAL" else "—"
    risk_txt = f"{stop_dist:,.{PRICE_PRECISION}f} (ATR {atr:,.{PRICE_PRECISION}f})" if direction != "NEUTRAL" else f"ATR {atr:,.{PRICE_PRECISION}f}"
    ts_txt = utc_str.split(" ")[1]

    sig_box.add_row(
        "SCALP", tf_label,
        f"[bold {sig_color}]{arrow} {direction}[/bold {sig_color}]",
        entry_txt, sl_txt, tp1_txt, tp2_txt, tp3_txt,
        risk_txt, ts_txt,
    )

    layout["signal_band"].update(Panel(
        sig_box,
        title=f"[bold {sig_color}]SCALP TRADE SIGNAL[/bold {sig_color}]",
        border_style=sig_color,
    ))

    # 2. L2 Order Book
    ob_table = Table(expand=True, box=None, padding=(0, 1))
    ob_table.add_column("Bid Contracts", justify="right", style="green")
    ob_table.add_column("Bid Price", justify="right", style="bold green")
    ob_table.add_column("Ask Price", justify="left", style="bold red")
    ob_table.add_column("Ask Contracts", justify="left", style="red")

    b_sub = market_state.bids[:6]
    a_sub = market_state.asks[:6]
    for i in range(max(len(b_sub), len(a_sub))):
        bq = f"{b_sub[i][1]:,.{QTY_PRECISION}f}" if i < len(b_sub) else ""
        bp = f"{b_sub[i][0]:,.{PRICE_PRECISION}f}" if i < len(b_sub) else ""
        ap = f"{a_sub[i][0]:,.{PRICE_PRECISION}f}" if i < len(a_sub) else ""
        aq = f"{a_sub[i][1]:.{QTY_PRECISION}f}" if i < len(a_sub) else ""
        ob_table.add_row(bq, bp, ap, aq)

    layout["orderbook"].update(Panel(ob_table, title=f"[bold cyan]MEXC L2 ORDER BOOK (Imbalance: {market_state.ob_imbalance:+.1f}%)[/bold cyan]", border_style="cyan"))

    # 3. Trade Tape
    tape_table = Table(expand=True, box=None, padding=(0, 1))
    tape_table.add_column("Time", style="dim")
    tape_table.add_column("Side")
    tape_table.add_column("Price", justify="right")
    tape_table.add_column("Contracts", justify="right")

    for ts, px, qty, is_buy in list(market_state.trade_tape)[:6]:
        side_lbl = "[bold green]BUY[/bold green]" if is_buy else "[bold red]SELL[/bold red]"
        tape_table.add_row(
            datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S"),
            side_lbl,
            f"{px:,.{PRICE_PRECISION}f}",
            f"{qty:.{QTY_PRECISION}f}",
        )

    layout["tape"].update(Panel(tape_table, title="[bold white]AGGREGATED DEAL STREAM (MEXC push.deal)[/bold white]", border_style="white"))

    # 4. Signal HUD
    sig_table = Table(expand=True, box=None, padding=(0, 1))
    sig_table.add_column("Metric", style="bold")
    sig_table.add_column("Value", justify="right")

    sig_table.add_row(f"{SYMBOL_DISPLAY} Price / Micro", f"{market_state.last_price:,.{PRICE_PRECISION}f} / {micro_price:,.{PRICE_PRECISION}f}")
    sig_table.add_row("RSI (14) / ATR (14) [1H]", f"{rsi:.1f} / {atr:,.{PRICE_PRECISION}f}")
    sig_table.add_row("Fair / Index Price", f"{market_state.mark_price:,.{PRICE_PRECISION}f} / {market_state.index_price:,.{PRICE_PRECISION}f}")
    sig_table.add_row("VWAP / EMA 9 / EMA 21 [1H]", f"{vwap:,.{PRICE_PRECISION}f} | {ema_9:,.{PRICE_PRECISION}f} | {ema_21:,.{PRICE_PRECISION}f}")
    sig_table.add_row("5s CVD / Total CVD (contracts)", f"{market_state.recent_cvd_5s:+.0f} / {market_state.cvd:+.0f}")
    sig_table.add_row("Open Interest (holdVol)", f"{market_state.open_interest * CONTRACT_USD_VALUE:,.0f}")
    sig_table.add_row("24h Turnover", f"{market_state.volume_24_usdt:,.0f} USDT")
    sig_table.add_row("24h High / Low", f"{market_state.high_24:,.{PRICE_PRECISION}f} / {market_state.low_24:,.{PRICE_PRECISION}f}")

    if futures_feeds_live():
        funding_next = datetime.fromtimestamp(market_state.next_funding_time / 1000, tz=timezone.utc).strftime("%H:%M") if market_state.next_funding_time else "--:--"
        sig_table.add_row("Funding (4h cycle)", f"{market_state.funding_rate * 100:+.6f}% @ {funding_next}")
    else:
        sig_table.add_row("Funding (4h cycle)", "[dim]N/A (OFFLINE)[/dim]")

    direction = "LONG" if market_state.last_price > ema_9 and rsi < 60 else "SHORT" if market_state.last_price < ema_9 and rsi > 40 else "NEUTRAL"
    sig_color = "green" if direction == "LONG" else "red" if direction == "SHORT" else "yellow"

    layout["signal_hud"].update(Panel(sig_table, title=f"[bold {sig_color}]SCALP RADAR: {direction}[/bold {sig_color}]", border_style=sig_color))

    # 5. Liquidation Cascade HUD
    liq_stats = liquidation_engine.update(market_state.last_price, market_state.recent_cvd_5s)
    liq_table = Table(expand=True, box=None, padding=(0, 1))
    liq_table.add_column("Window", style="dim")
    liq_table.add_column("Forced Sells", justify="right", style="bold red")
    liq_table.add_column("Forced Buys", justify="right", style="bold green")

    if liquidation_feed_live():
        liq_table.add_row("10s Burst", f"${liq_stats['long_10s']:,.0f}", f"${liq_stats['short_10s']:,.0f}")
        liq_table.add_row("Liq Velocity", f"${liq_stats['velocity']:,.0f}/s", f"Peak: ${liq_stats['peak_velocity']:,.0f}/s")
        liq_table.add_row("Engine State", f"[bold yellow]{liq_stats['state']}[/bold yellow]", f"Wick: {liq_stats['wick_extreme']:,.{PRICE_PRECISION}f}")
    else:
        liq_table.add_row("10s Burst", "[dim]NO PUBLIC FEED[/dim]", "[dim]NO PUBLIC FEED[/dim]")
        liq_table.add_row("Liq Velocity", "[dim]MEXC HAS NONE[/dim]", "[dim]0 liq events recvd[/dim]")
        liq_table.add_row("Engine State", "[bold yellow]IDLE / DORMANT[/bold yellow]", "[dim]auto-arm on any vendor w/ liq feed[/dim]")

    layout["liquidation_hud"].update(Panel(liq_table, title="[bold magenta]⚡ LIQUIDATION CASCADE MONITOR[/bold magenta]", border_style="magenta"))

    # 6. Footer
    feed_status = "MEXC FUTURES ACTIVE" if futures_feeds_live() else "OFFLINE - CHECK NETWORK"
    footer_style = "black on green" if futures_feeds_live() else "black on red"
    layout["footer"].update(Panel(
        Text(f" MEXC WEBSOCKETS {feed_status} | 100% REAL-TIME MEXC XAU/USDT FEEDS | ZERO POLLING JITTER | PRESS CTRL+C TO EXIT ", style=footer_style),
        style="green" if futures_feeds_live() else "red"
    ))

    return layout
