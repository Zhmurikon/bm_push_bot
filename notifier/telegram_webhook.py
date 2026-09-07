import asyncio
import json
import logging
import os

from asgiref.sync import async_to_sync
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


def _get_bot_and_dp():
    from bot.app import create_bot
    from bot.handlers import register_handlers
    from aiogram import Bot, Dispatcher

    bot = create_bot()
    dp = Dispatcher()
    register_handlers(dp)
    return bot, dp


@csrf_exempt
@require_POST
def telegram_webhook(request, secret):
    if secret != settings.WEBHOOK_SECRET:
        return HttpResponse(status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    secret_header = request.META.get("HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN", "")
    if secret_header and secret_header != settings.WEBHOOK_SECRET:
        return HttpResponse(status=403)

    bot, dp = _get_bot_and_dp()
    _process_update = async_to_sync(_async_process_update)
    _process_update(bot, dp, data)
    return JsonResponse({"ok": True})


async def _async_process_update(bot, dp, data):
    from aiogram.types import Update

    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)
