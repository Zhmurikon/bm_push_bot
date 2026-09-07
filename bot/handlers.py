import os
import sys

from aiogram import Dispatcher, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import ChatMemberUpdated, Message
from asgiref.sync import sync_to_async

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

router = Router()


def _ensure_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()


@sync_to_async
def _process_invite(code: str, chat_id: int, chat_type: str, chat_title: str) -> dict:
    _ensure_django()
    from django.utils import timezone
    from notifier.models import Invite, Recipient, Subscription

    try:
        invite = Invite.objects.select_related("project").get(code=code)
    except Invite.DoesNotExist:
        return {"error": "invalid"}

    if not invite.is_valid:
        return {"error": "expired"}

    kind = Recipient.Kind.GROUP if chat_type in ("group", "supergroup") else Recipient.Kind.PRIVATE
    title = chat_title or str(chat_id)

    recipient, _ = Recipient.objects.get_or_create(
        chat_id=chat_id,
        defaults={"kind": kind, "title": title, "is_active": True},
    )
    if not recipient.is_active:
        recipient.is_active = True
        recipient.save(update_fields=["is_active"])

    sub, sub_created = Subscription.objects.get_or_create(
        project=invite.project,
        recipient=recipient,
        defaults={"is_active": True},
    )
    if not sub_created and not sub.is_active:
        sub.is_active = True
        sub.save(update_fields=["is_active"])

    if not invite.is_multi_use:
        invite.used_by = recipient
        invite.used_at = timezone.now()
        invite.save(update_fields=["used_by", "used_at"])

    return {"ok": True, "project": invite.project.name}


@sync_to_async
def _process_stop(chat_id: int) -> dict:
    _ensure_django()
    from notifier.models import Recipient, Subscription

    try:
        recipient = Recipient.objects.get(chat_id=chat_id)
    except Recipient.DoesNotExist:
        return {"error": "not_found"}

    count = Subscription.objects.filter(recipient=recipient, is_active=True).update(is_active=False)
    recipient.is_active = False
    recipient.save(update_fields=["is_active"])
    return {"ok": True, "count": count}


@sync_to_async
def _deactivate_chat(chat_id: int):
    _ensure_django()
    from notifier.models import Recipient
    try:
        recipient = Recipient.objects.get(chat_id=chat_id)
        recipient.is_active = False
        recipient.save(update_fields=["is_active"])
    except Recipient.DoesNotExist:
        pass


@router.message(CommandStart(deep_link=True))
async def cmd_start_with_code(message: Message, command=None):
    code = command.args if command else ""
    if not code:
        await message.answer("Для подключения нужен код приглашения.")
        return

    result = await _process_invite(
        code=code,
        chat_id=message.chat.id,
        chat_type=message.chat.type,
        chat_title=message.chat.title or message.chat.full_name or "",
    )

    if result.get("error") == "invalid":
        await message.answer("❌ Неверный код приглашения.")
    elif result.get("error") == "expired":
        await message.answer("❌ Код приглашения истёк или уже использован.")
    else:
        await message.answer(
            f"✅ Подключено!\n\n"
            f"Проект: <b>{result['project']}</b>\n"
            f"Теперь заявки будут приходить сюда.\n\n"
            f"Для отключения отправьте /stop",
            parse_mode="HTML",
        )


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Я бот уведомлений о заявках.\n\n"
        "Для подключения нужен код приглашения — "
        "перейдите по ссылке, которую вам прислал администратор."
    )


@router.message(Command("stop"))
async def cmd_stop(message: Message):
    result = await _process_stop(message.chat.id)
    if result.get("error") == "not_found":
        await message.answer("Вы не подключены ни к одному проекту.")
    elif result["count"]:
        await message.answer(f"🔕 Отключено. Вы больше не будете получать заявки ({result['count']} подписок).")
    else:
        await message.answer("У вас нет активных подписок.")


@router.my_chat_member()
async def on_bot_membership_change(event: ChatMemberUpdated):
    new_status = event.new_chat_member.status
    if new_status in ("kicked", "left"):
        await _deactivate_chat(event.chat.id)


def register_handlers(dp: Dispatcher):
    dp.include_router(router)
