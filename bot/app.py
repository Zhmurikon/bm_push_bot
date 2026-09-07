import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application


def _create_bot_session():
    proxy_url = os.getenv("PROXY_URL", "")
    if proxy_url:
        return AiohttpSession(proxy=proxy_url)
    return AiohttpSession()


def create_bot():
    token = os.getenv("BOT_TOKEN", "")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")
    return Bot(token=token, session=_create_bot_session())


def telegram_webhook_app(django_asgi_app):
    """Wrap Django ASGI app, mounting aiogram webhook handler at /tg/<secret>/."""

    bot = create_bot()
    dp = Dispatcher()

    from bot.handlers import register_handlers

    register_handlers(dp)

    webhook_secret = os.getenv("WEBHOOK_SECRET", "webhook")
    webhook_path = f"/tg/{webhook_secret}/"

    async def on_startup(bot: Bot, **kwargs):
        webhook_url = os.getenv("WEBHOOK_URL", "")
        if webhook_url:
            full_url = f"{webhook_url.rstrip('/')}{webhook_path}"
            await bot.set_webhook(
                url=full_url,
                secret_token=webhook_secret,
                drop_pending_updates=True,
            )

    dp.startup.register(on_startup)

    aiohttp_app = web.Application()
    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=webhook_secret,
    ).register(aiohttp_app, path=webhook_path)
    setup_application(aiohttp_app, dp, bot=bot)

    async def combined_app(scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith("/tg/"):
            return await aiohttp_app(scope, receive, send)
        return await django_asgi_app(scope, receive, send)

    return combined_app
