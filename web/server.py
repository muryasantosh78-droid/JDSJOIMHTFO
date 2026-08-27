import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiohttp import web
from rich.console import Console

from network.rest_client import bootstrap_market_snapshot
from network.streams import (
    ws_depth_stream,
    ws_kline_stream,
    ws_mark_price_stream,
    ws_trade_stream,
)
from ui.terminal_ui import render_bloomberg_dashboard

WIDTH = 180


async def index(request):
    console = Console(record=True, width=WIDTH)
    console.print(render_bloomberg_dashboard())
    doc = console.export_html(inline_styles=True)
    doc = doc.replace("</head>", '<meta http-equiv="refresh" content="1"></head>')
    return web.Response(text=doc, content_type="text/html")


async def on_startup(app):
    await bootstrap_market_snapshot()
    app["tasks"] = [
        asyncio.create_task(ws_trade_stream()),
        asyncio.create_task(ws_depth_stream()),
        asyncio.create_task(ws_kline_stream()),
        asyncio.create_task(ws_mark_price_stream()),
    ]


async def on_cleanup(app):
    for task in app.get("tasks", []):
        task.cancel()


def main():
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/health", lambda _: web.Response(text="ok"))
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    web.run_app(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "12000")),
        print=None,
    )


if __name__ == "__main__":
    main()
