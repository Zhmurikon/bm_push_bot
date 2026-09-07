import html
import os
import sys

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message
from asgiref.sync import sync_to_async

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

router = Router()


def _ensure_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()


# ---- helpers ----

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

    kind = "group" if chat_type in ("group", "supergroup") else "private"
    title = chat_title or str(chat_id)

    recipient, created = Recipient.objects.get_or_create(
        chat_id=chat_id,
        defaults={"kind": kind, "title": title, "is_active": True},
    )
    if not created:
        # чат мог быть переименован или превращён в супергруппу — обновляем карточку
        changed = []
        if recipient.kind != kind:
            recipient.kind = kind
            changed.append("kind")
        if title and recipient.title != title:
            recipient.title = title
            changed.append("title")
        if not recipient.is_active:
            recipient.is_active = True
            changed.append("is_active")
        if changed:
            recipient.save(update_fields=changed)

    sub, sub_created = Subscription.objects.get_or_create(
        project=invite.project, recipient=recipient, defaults={"is_active": True},
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


# ---- /start ----

@router.message(CommandStart(deep_link=True))
async def cmd_start_with_code(message: Message, command=None):
    code = command.args if command else ""
    if not code:
        await message.answer("Для подключения нужен код приглашения.")
        return

    result = await _process_invite(
        code=code, chat_id=message.chat.id,
        chat_type=message.chat.type,
        chat_title=message.chat.title or message.chat.full_name or "",
    )
    if result.get("error") == "invalid":
        await message.answer("❌ Неверный код приглашения.")
    elif result.get("error") == "expired":
        await message.answer("❌ Код приглашения истёк или уже использован.")
    else:
        await message.answer(
            f"✅ Подключено!\n\nПроект: <b>{html.escape(result['project'])}</b>\n"
            f"Теперь заявки будут приходить сюда.\n\nДля отключения отправьте /stop",
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
        await message.answer(f"🔕 Отключено ({result['count']} подписок).")
    else:
        await message.answer("У вас нет активных подписок.")


# ---- Кнопки статусов (Этап 5) ----

@sync_to_async
def _process_lead_callback(lead_id: int, action: str, user_name: str) -> dict:
    _ensure_django()
    from django.utils import timezone
    from notifier.models import Delivery, Lead
    from notifier.services import build_lead_keyboard

    try:
        lead = Lead.objects.select_related("project").get(pk=lead_id)
    except Lead.DoesNotExist:
        return {"error": "not_found"}

    status_labels = {"in_progress": "📋 Взял в работу", "done": "✅ Обработана"}
    if action not in status_labels:
        return {"error": "bad_action"}

    now = timezone.localtime().strftime("%H:%M")
    status_line = f"\n\n{status_labels[action]} — {user_name}, {now}"
    new_text = lead.rendered_text + status_line
    lead.status = action
    lead.save(update_fields=["status"])

    new_keyboard = build_lead_keyboard(lead.pk, lead.status)

    targets = list(
        Delivery.objects.filter(lead=lead, ok=True, message_id__isnull=False)
        .values_list("recipient__chat_id", "message_id")
    )
    return {"ok": True, "status": action, "text": new_text, "keyboard": new_keyboard, "targets": targets}


@router.callback_query(F.data.startswith("lead:"))
async def on_lead_callback(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Неверная команда", show_alert=True)
        return

    lead_id = int(parts[1])
    action = parts[2]
    user_name = callback.from_user.full_name

    result = await _process_lead_callback(lead_id, action, user_name)
    if result.get("error") == "not_found":
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    elif result.get("error") == "bad_action":
        await callback.answer("Неизвестное действие", show_alert=True)
        return

    from notifier.services import edit_telegram_message
    for chat_id, message_id in result["targets"]:
        try:
            await edit_telegram_message(chat_id, message_id, result["text"], result["keyboard"])
        except Exception:
            pass

    labels = {"in_progress": "📋 Взял в работу", "done": "✅ Обработана"}
    await callback.answer(labels.get(action, action))


# ---- Админ-команды (Этап 6) ----

@sync_to_async
def _is_admin_ids(chat_id: int, user_id: int | None) -> bool:
    _ensure_django()
    from notifier.models import Recipient
    ids = {chat_id} | ({user_id} if user_id else set())
    return Recipient.objects.filter(chat_id__in=ids, is_admin=True).exists()


async def _is_admin(message: Message) -> bool:
    """Админ определяется по автору команды, а не по чату.

    В группе message.chat.id — id группы, поэтому проверять только его нельзя:
    админ-команды переставали работать в групповых чатах.
    """
    user_id = message.from_user.id if message.from_user else None
    return await _is_admin_ids(message.chat.id, user_id)


@sync_to_async
def _get_projects_list() -> str:
    _ensure_django()
    from notifier.models import Project, Subscription
    projects = Project.objects.filter(is_active=True)
    if not projects:
        return "Нет активных проектов."
    lines = []
    for p in projects:
        count = Subscription.objects.filter(project=p, is_active=True).count()
        lines.append(f"• <b>{html.escape(p.name)}</b> ({p.slug}) — {count} получателей")
    return "\n".join(lines)


@sync_to_async
def _create_invite(slug: str) -> dict:
    _ensure_django()
    from notifier.models import Invite, Project
    try:
        project = Project.objects.get(slug=slug, is_active=True)
    except Project.DoesNotExist:
        return {"error": "not_found"}
    invite = Invite.objects.create(project=project, is_multi_use=True)
    return {
        "ok": True,
        "code": invite.code,
        "link": invite.invite_link,
        "group_link": invite.group_invite_link,
        "project": project.name,
    }


@sync_to_async
def _get_last_leads(slug: str, limit: int = 5) -> str:
    _ensure_django()
    from notifier.models import Lead, Project
    try:
        project = Project.objects.get(slug=slug)
    except Project.DoesNotExist:
        return "Проект не найден."
    leads = Lead.objects.filter(project=project).order_by("-created_at")[:limit]
    if not leads:
        return "Заявок пока нет."
    lines = []
    for l in leads:
        fields = l.payload.get("fields", {})
        name = fields.get("Имя", fields.get("имя", "—"))
        phone = fields.get("Телефон", fields.get("телефон", "—"))
        status_emoji = {"new": "🆕", "in_progress": "📋", "done": "✅"}.get(l.status, "")
        lines.append(
            f"{status_emoji} #{l.pk} {html.escape(str(name))} {html.escape(str(phone))} "
            f"({l.created_at.strftime('%d.%m %H:%M')})"
        )
    return f"<b>{html.escape(project.name)}</b> — последние заявки:\n\n" + "\n".join(lines)


@sync_to_async
def _manual_send(slug: str, text: str) -> dict:
    _ensure_django()
    from notifier.models import Project, Subscription
    from notifier.services import send_telegram_message
    import asyncio

    try:
        project = Project.objects.get(slug=slug, is_active=True)
    except Project.DoesNotExist:
        return {"error": "not_found"}

    subs = Subscription.objects.filter(
        project=project, is_active=True, recipient__is_active=True
    ).select_related("recipient")

    loop = asyncio.new_event_loop()
    delivered = 0
    for sub in subs:
        try:
            result = loop.run_until_complete(send_telegram_message(sub.recipient.chat_id, text))
            if result["ok"]:
                delivered += 1
        except Exception:
            pass
    loop.close()
    return {"ok": True, "delivered": delivered, "total": subs.count()}


@sync_to_async
def _off_recipient(slug: str, chat_id_str: str) -> dict:
    _ensure_django()
    from notifier.models import Project, Recipient, Subscription
    try:
        project = Project.objects.get(slug=slug)
    except Project.DoesNotExist:
        return {"error": "project_not_found"}
    try:
        recipient = Recipient.objects.get(chat_id=int(chat_id_str))
    except (Recipient.DoesNotExist, ValueError):
        return {"error": "recipient_not_found"}
    count = Subscription.objects.filter(project=project, recipient=recipient, is_active=True).update(is_active=False)
    return {"ok": True, "count": count, "project": project.name, "recipient": str(recipient)}


@router.message(Command("projects"))
async def cmd_projects(message: Message):
    if not await _is_admin(message):
        await message.answer("⛔ Команда доступна только администраторам.")
        return
    text = await _get_projects_list()
    await message.answer(text, parse_mode="HTML")


@router.message(Command("invite"))
async def cmd_invite(message: Message, command=None):
    if not await _is_admin(message):
        await message.answer("⛔ Команда доступна только администраторам.")
        return
    slug = (command.args or "").strip() if command else ""
    if not slug:
        await message.answer("Использование: /invite <slug проекта>")
        return
    result = await _create_invite(slug)
    if result.get("error") == "not_found":
        await message.answer("Проект не найден.")
    else:
        await message.answer(
            f"Код приглашения для <b>{html.escape(result['project'])}</b>:\n"
            f"<code>{result['code']}</code>\n\n"
            f"Личный чат: {result['link']}\n"
            f"Добавить в группу: {result['group_link']}\n\n"
            f"Если бот уже в группе — отправьте туда <code>/start {result['code']}</code>",
            parse_mode="HTML",
        )


@router.message(Command("last"))
async def cmd_last(message: Message, command=None):
    if not await _is_admin(message):
        await message.answer("⛔ Команда доступна только администраторам.")
        return
    slug = (command.args or "").strip() if command else ""
    if not slug:
        await message.answer("Использование: /last <slug проекта>")
        return
    text = await _get_last_leads(slug)
    await message.answer(text, parse_mode="HTML")


@router.message(Command("send"))
async def cmd_send(message: Message, command=None):
    if not await _is_admin(message):
        await message.answer("⛔ Команда доступна только администраторам.")
        return
    args = (command.args or "").strip() if command else ""
    parts = args.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /send <slug> <текст сообщения>")
        return
    slug, text = parts
    result = await _manual_send(slug, text)
    if result.get("error") == "not_found":
        await message.answer("Проект не найден.")
    else:
        await message.answer(f"Отправлено: {result['delivered']}/{result['total']}")


@router.message(Command("off"))
async def cmd_off(message: Message, command=None):
    if not await _is_admin(message):
        await message.answer("⛔ Команда доступна только администраторам.")
        return
    args = (command.args or "").strip() if command else ""
    parts = args.split()
    if len(parts) < 2:
        await message.answer("Использование: /off <slug> <chat_id>")
        return
    slug, chat_id_str = parts[0], parts[1]
    result = await _off_recipient(slug, chat_id_str)
    if result.get("error") == "project_not_found":
        await message.answer("Проект не найден.")
    elif result.get("error") == "recipient_not_found":
        await message.answer("Получатель не найден.")
    else:
        await message.answer(f"Отключено {result['count']} подписок: {result['recipient']} ← {result['project']}")


# ---- Групповые чаты: добавление, миграция, удаление ----

@sync_to_async
def _chat_projects(chat_id: int) -> list[str]:
    _ensure_django()
    from notifier.models import Subscription
    return list(
        Subscription.objects.filter(
            recipient__chat_id=chat_id, is_active=True, recipient__is_active=True
        ).values_list("project__name", flat=True)
    )


@sync_to_async
def _migrate_chat_id(old_chat_id: int, new_chat_id: int) -> bool:
    """Группа превратилась в супергруппу — у неё новый chat_id."""
    _ensure_django()
    from notifier.models import Recipient
    if Recipient.objects.filter(chat_id=new_chat_id).exists():
        Recipient.objects.filter(chat_id=old_chat_id).delete()
        return True
    return bool(
        Recipient.objects.filter(chat_id=old_chat_id).update(
            chat_id=new_chat_id, kind="group"
        )
    )


@router.message(F.migrate_to_chat_id)
async def on_chat_migrated(message: Message):
    await _migrate_chat_id(message.chat.id, message.migrate_to_chat_id)


@router.my_chat_member()
async def on_bot_membership_change(event: ChatMemberUpdated, bot: Bot):
    new_status = event.new_chat_member.status
    if new_status in ("kicked", "left"):
        await _deactivate_chat(event.chat.id)
        return

    if new_status not in ("member", "administrator"):
        return
    if event.chat.type not in ("group", "supergroup"):
        return

    projects = await _chat_projects(event.chat.id)
    if projects:
        text = "✅ Заявки уже приходят сюда: " + ", ".join(html.escape(p) for p in projects)
    else:
        text = (
            "👋 Я бот уведомлений о заявках.\n\n"
            "Чтобы заявки приходили в этот чат, отправьте сюда код приглашения:\n"
            "<code>/start INV-XXXXXX</code>"
        )
    try:
        await bot.send_message(event.chat.id, text, parse_mode="HTML")
    except Exception:
        pass


def register_handlers(dp: Dispatcher):
    dp.include_router(router)
