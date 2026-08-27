from datetime import datetime, timezone
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from config import futures_feeds_live, PRICE_PRECISION, SYMBOL_DISPLAY
from core.market_state import market_state
from core.multi_tf import analyze_all_timeframes, MasterAgent


def _spark(closes, width=16, last=None):
    """Single-line sparkline from a close series (last `width` samples)."""
    if closes is None or len(closes) < 2:
        return ""
    series = closes[-width:] if len(closes) > width else closes
    cmin, cmax = float(series.min()), float(series.max())
    if cmin == cmax:
        cmin -= 1e-9
        cmax += 1e-9
    mid = last if last else (cmin + cmax) / 2
    out = []
    for v in series:
        v = float(v)
        if v > mid:
            out.append("[bold green]█[/bold green]")
        elif v < mid:
            out.append("[bold red]▄[/bold red]")
        else:
            out.append("[dim]─[/dim]")
    return "".join(out)


def _tf_box(tf, r):
    """Compose the per-timeframe scalp box rows (markup strings)."""
    if r.direction == "LONG":
        arrow, color = "▲", "green"
    elif r.direction == "SHORT":
        arrow, color = "▼", "red"
    else:
        arrow, color = "●", "yellow"

    price = f"{r.last:,.{PRICE_PRECISION}f}" if r.last else "—"
    entry = f"{r.entry:,.{PRICE_PRECISION}f}" if r.direction != "NEUTRAL" else "—"
    sl = f"{r.sl:,.{PRICE_PRECISION}f}" if r.direction != "NEUTRAL" else "—"
    tp1 = f"{r.tp1:,.{PRICE_PRECISION}f}" if r.direction != "NEUTRAL" else "—"
    return [
        f"[bold {color}]{tf:>2}m {arrow} {r.direction:<7}[/bold {color}]",
        f" P [bold]{price}[/bold]",
        f" RSI {r.rsi:5.1f}  ATR {r.atr:,.{PRICE_PRECISION}f}",
        f" E9 {r.ema9:,.{PRICE_PRECISION}f}  E21 {r.ema21:,.{PRICE_PRECISION}f}",
        f" ENT {entry}  SL {sl}",
        f" TP1 {tp1}",
    ]


def _render_master(m):
    color = "green" if m.direction == "LONG" else "red" if m.direction == "SHORT" else "yellow"
    arrow = "▲" if m.direction == "LONG" else "▼" if m.direction == "SHORT" else "●"
    t = Table(expand=True, box=None, padding=(0, 2))
    t.add_column("Metric", style="bold", justify="left")
    t.add_column("Value", justify="right")
    t.add_row("MASTER SIGNAL (ALL 60)", f"[bold {color}]{arrow} {m.direction}[/bold {color}]")
    t.add_row("Votes LONG/SHORT/NEUTRAL", f"{m.long_count} / {m.short_count} / {m.neutral_count}")
    t.add_row("Conviction BUY / SELL", f"{m.bull_weight:.3f} / {m.bear_weight:.3f}")
    t.add_row("IDEAL ENTRY", f"[bold cyan]{m.entry:,.{PRICE_PRECISION}f}[/bold cyan]")
    t.add_row("IDEAL STOP LOSS", f"[bold red]{m.sl:,.{PRICE_PRECISION}f}[/bold red]" if m.direction != "NEUTRAL" else "—")
    t.add_row("IDEAL TARGET TP1", f"[bold green]{m.tp1:,.{PRICE_PRECISION}f}[/bold green]" if m.direction != "NEUTRAL" else "—")
    t.add_row("IDEAL TARGET TP2", f"[bold green]{m.tp2:,.{PRICE_PRECISION}f}[/bold green]" if m.direction != "NEUTRAL" else "—")
    t.add_row("IDEAL TARGET TP3", f"[bold green]{m.tp3:,.{PRICE_PRECISION}f}[/bold green]" if m.direction != "NEUTRAL" else "—")
    t.add_row("RISK DIST (ATR)", f"{m.risk_dist:,.{PRICE_PRECISION}f}")
    t.add_row("LEADING TIMEFRAME", f"{m.winner_tf} min")
    return Panel(t, title=f"[bold {color}]⚖ MASTER AGENT → IDEAL ENTRY (60-TIMEFRAME FUSION)[/bold {color}]", border_style=color)


def _render_grid(results):
    """60 scalp boxes in a bordered grid (6 columns x 10 rows)."""
    spans = []
    ORDERED = list(results.items())           # [(tf, r), ...] 1..60

    # Each box -> 9 *markup* lines. Build a wide Table with one column per box,
    # 6 boxes per row-group so it wraps to ~6 columns in terminal and web.
    table = Table.grid(padding=(0, 2))
    table.title = "SCALP BOXES"
    for i in range(6):
        table.add_column(ratio=1)

    for row_start in range(0, 60, 6):
        cells = []
        for tf, r in ORDERED[row_start:row_start + 6]:
            lines = _tf_box(tf, r)
            chart = _spark(r.closes, width=16, last=r.last)
            box = "\n".join(lines) + ("\n" + chart if chart else "")
            cells.append(box)
        table.add_row(*cells)
    return Panel(
        table,
        title="[bold cyan]60 TIMEFRAME SCALP BOXES (1m..60m) — REAL MEXC DATA[/bold cyan]",
        border_style="cyan",
    )


def render_bloomberg_dashboard() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="master", size=15),
        Layout(name="boxes", ratio=1),
        Layout(name="footer", size=3),
    )

    # Recompute the whole multi-timeframe picture each refresh (fast, real data)
    results = analyze_all_timeframes()
    master = MasterAgent(results)

    utc_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    feed_tag = "MEXC FUTURES" if futures_feeds_live() else "STALE (OFFLINE)"
    header_panel = Panel(
        Text(f" 🥇 BLOOMBERG {SYMBOL_DISPLAY} 60-TIMEFRAME SCALP TERMINAL | LIVE {feed_tag} | UTC: {utc_str} | LATENCY: {market_state.network_latency_ms:.1f}ms | Min1 BARS: {len(market_state.klines_1m)} ", style="bold white on dark_blue"),
        style="dark_blue"
    )
    layout["header"].update(header_panel)

    layout["master"].update(_render_master(master))
    layout["boxes"].update(_render_grid(results))

    feed_status = "MEXC FUTURES ACTIVE (60 REAL TIMEFRAMES FROM ONE Min1 STREAM)" if futures_feeds_live() else "OFFLINE - CHECK NETWORK"
    footer_style = "black on green" if futures_feeds_live() else "black on red"
    layout["footer"].update(Panel(
        Text(f" ◉ {feed_status} | 100% REAL MEXC XAU/USDT | MASTER AGENT FUSES ALL 60 SCALP BOXES INTO ONE IDEAL ENTRY | CTRL+C TO EXIT ", style=footer_style),
        style="green" if futures_feeds_live() else "red",
    ))
    return layout