"""Bot Framework aiohttp entry point.

Registers the CloudAdapter and a single POST route at /api/messages.
Starts the APScheduler nightly sync job on server startup.

Run as a module:
  python -m bot.app
"""

import logging

from aiohttp import web
from botbuilder.integration.aiohttp import CloudAdapter, ConfigurationBotFrameworkAuthentication
from botbuilder.schema import Activity

from bot.bot_handler import OpenClawBot
from config.settings import get_settings
from scheduler.sync_job import start_scheduler

logger = logging.getLogger(__name__)


class _BotConfig:
    """Minimal config object expected by ConfigurationBotFrameworkAuthentication."""

    def __init__(self) -> None:
        settings = get_settings()
        self.APP_ID: str = settings.microsoft_app_id
        self.APP_PASSWORD: str = settings.microsoft_app_password


async def messages(request: web.Request) -> web.Response:
    """Handle incoming Bot Framework activity POSTs."""
    adapter: CloudAdapter = request.app["adapter"]
    bot: OpenClawBot = request.app["bot"]

    if "application/json" not in request.content_type:
        return web.Response(status=415, text="Unsupported Media Type")

    body = await request.json()
    activity = request.app["activity_class"].from_dict(body)
    auth_header = request.headers.get("Authorization", "")

    response = await adapter.process_activity(auth_header, activity, bot.on_turn)
    if response:
        return web.json_response(response.body, status=response.status)
    return web.Response(status=201)


def create_app() -> web.Application:
    """Create and configure the aiohttp web application."""
    settings = get_settings()
    bot_config = _BotConfig()
    adapter = CloudAdapter(ConfigurationBotFrameworkAuthentication(bot_config))
    bot = OpenClawBot()

    app = web.Application()
    app["adapter"] = adapter
    app["bot"] = bot
    app["activity_class"] = Activity

    app.router.add_post("/api/messages", messages)

    # Start the nightly ingestion scheduler
    start_scheduler()
    logger.info("Nightly ingestion scheduler started")

    return app


if __name__ == "__main__":
    import logging as _logging

    _logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    _settings = get_settings()
    logger.info("Starting OpenClaw bot on port %d", _settings.bot_port)
    web.run_app(create_app(), host="0.0.0.0", port=_settings.bot_port)
