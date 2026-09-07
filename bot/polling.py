"""Локальный запуск бота в режиме polling (без webhook).

Использование:
    python -m bot.polling
"""

import asyncio
import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from bot.app import create_bot  # noqa: E402
from bot.handlers import register_handlers  # noqa: E402
from aiogram import Dispatcher  # noqa: E402


async def main():
    bot = create_bot()
    dp = Dispatcher()
    register_handlers(dp)

    print("🤖 Бот запущен в режиме polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
