import asyncio
import sys
from rich.console import Console
from rich.live import Live

from config import futures_feeds_live, liquidation_feed_live
from core.liquidation_engine import liquidation_engine
from core.market_state import market_state
from execution.trade_manager import trade_executor
from network.rest_client import bootstrap_market_snapshot
from network.streams import (
    ws_depth_stream,
    ws_force_order_stream,
    ws_kline_stream,
    ws_mark_price_stream,
    ws_trade_stream,
)
from ui.terminal_ui import render_bloomberg_dashboard


async def strategy_execution_loop():
    while True:
        # Cascade FSM only fires when a public liquidation feed exists.
        if liquidation_feed_live() and futures_feeds_live() and market_state.last_price > 0:
            liq_stats = liquidation_engine.update(market_state.last_price, market_state.recent_cvd_5s)
            action = liq_stats["action"]

            if action in ["BUY_CAPITULATION", "SELL_SQUEEZE"]:
                side = "BUY" if action == "BUY_CAPITULATION" else "SELL"
                wick = liq_stats["wick_extreme"]
                entry = market_state.last_price

                if side == "BUY":
                    sl = wick - 2.0
                    qty, dist = trade_executor.calculate_position_parameters(entry, sl)
                    tp1 = entry + (dist * 1.5)
                    tp2 = entry + (dist * 3.0)
                else:
                    sl = wick + 2.0
                    qty, dist = trade_executor.calculate_position_parameters(entry, sl)
                    tp1 = entry - (dist * 1.5)
                    tp2 = entry - (dist * 3.0)

                await trade_executor.execute_bracket(side, qty, sl, tp1, tp2)

        await asyncio.sleep(0.05)


async def main():
    console = Console()
    console.print("[bold yellow]Bootstrapping historical market snapshot from MEXC Futures (XAU/USDT)...[/bold yellow]")
    await bootstrap_market_snapshot()

    # Launch background WebSocket tasks
    asyncio.create_task(ws_trade_stream())
    asyncio.create_task(ws_depth_stream())
    asyncio.create_task(ws_mark_price_stream())
    asyncio.create_task(ws_force_order_stream())
    asyncio.create_task(ws_kline_stream())
    asyncio.create_task(strategy_execution_loop())

    # Start live UI renderer (20fps target; MEXC pushes depth @ real-time)
    with Live(render_bloomberg_dashboard(), console=console, refresh_per_second=20, screen=True) as live:
        while True:
            live.update(render_bloomberg_dashboard())
            await asyncio.sleep(0.05)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[TERMINAL SHUT DOWN CLEANLY]")
        sys.exit(0)
