from aiogram import Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    chat_id = message.chat.id
    await message.answer(
        f"👋 Привет! Я бот уведомлений о заявках.\n\n"
        f"Ваш chat_id: `{chat_id}`\n\n"
        "Для подключения нужен код приглашения — "
        "перейдите по ссылке, которую вам прислал администратор."
    )


def register_handlers(dp: Dispatcher):
    dp.include_router(router)
