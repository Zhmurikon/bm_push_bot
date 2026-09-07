"""Тесты бота в групповых чатах.

Апдейты прогоняются через настоящий aiogram Dispatcher с поддельной сессией,
поэтому проверяются и фильтры (команды с @упоминанием, deep link), и хендлеры.
"""

import asyncio
from unittest import mock

from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.methods import SendMessage
from aiogram.types import Chat, Message, Update, User
from django.test import TransactionTestCase
from django.utils import timezone

from bot.handlers import register_handlers
from notifier.models import Invite, Project, Recipient, Subscription, hash_token

# router — модуль-синглтон, поэтому Dispatcher один на весь прогон
_dp = Dispatcher()
register_handlers(_dp)

GROUP_ID = -1001234567890
ADMIN_ID = 555
MEMBER_ID = 777


class FakeSession(BaseSession):
    """Ничего не отправляет наружу, только записывает вызовы."""

    def __init__(self):
        super().__init__()
        self.calls = []

    async def close(self):
        pass

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if isinstance(method, SendMessage):
            return Message(
                message_id=1,
                date=timezone.now(),
                chat=Chat(id=method.chat_id, type="group", title="Чат"),
                text=method.text,
            )
        return True

    async def stream_content(self, url, headers=None, timeout=30, chunk_size=65536, raise_for_status=True):
        yield b""

    @property
    def texts(self):
        return [c.text for c in self.calls if isinstance(c, SendMessage)]


def group_message(text: str, user_id: int = MEMBER_ID, chat_id: int = GROUP_ID) -> Update:
    return Update(
        update_id=1,
        message=Message(
            message_id=10,
            date=timezone.now(),
            chat=Chat(id=chat_id, type="supergroup", title="Отдел продаж"),
            from_user=User(id=user_id, is_bot=False, first_name="Тест"),
            text=text,
            entities=[{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}],
        ),
    )


class GroupChatTests(TransactionTestCase):
    def setUp(self):
        self.session = FakeSession()
        self.bot = Bot(token="42:TEST", session=self.session)
        self.dp = _dp

        self.project = Project.objects.create(
            name="Сайт клиента", slug="test-site", token_hash=hash_token("t")
        )
        self.invite = Invite.objects.create(project=self.project, is_multi_use=True)
        Recipient.objects.create(chat_id=ADMIN_ID, kind="private", title="Админ", is_admin=True)

    def feed(self, update: Update):
        async def run():
            with mock.patch.object(
                Bot, "me", mock.AsyncMock(return_value=User(id=42, is_bot=True, first_name="Bot", username="bm_push_bot"))
            ):
                await self.dp.feed_update(self.bot, update)

        asyncio.run(run())

    # ---- подключение группы ----

    def test_start_with_code_in_group_subscribes_chat(self):
        self.feed(group_message(f"/start {self.invite.code}"))

        recipient = Recipient.objects.get(chat_id=GROUP_ID)
        self.assertEqual(recipient.kind, "group")
        self.assertEqual(recipient.title, "Отдел продаж")
        self.assertTrue(
            Subscription.objects.filter(
                project=self.project, recipient=recipient, is_active=True
            ).exists()
        )
        self.assertIn("Подключено", self.session.texts[0])

    def test_start_with_mention_in_group(self):
        """В группе клиент часто присылает /start@bm_push_bot CODE."""
        self.feed(group_message(f"/start@bm_push_bot {self.invite.code}"))
        self.assertTrue(Subscription.objects.filter(project=self.project, is_active=True).exists())

    def test_invalid_code_in_group(self):
        self.feed(group_message("/start INV-NOPE1"))
        self.assertFalse(Recipient.objects.filter(chat_id=GROUP_ID).exists())
        self.assertIn("Неверный код", self.session.texts[0])

    # ---- админ-команды из группы ----

    def test_admin_command_works_in_group_for_admin_user(self):
        self.feed(group_message("/projects", user_id=ADMIN_ID))
        self.assertIn("Сайт клиента", self.session.texts[0])

    def test_admin_command_denied_for_ordinary_group_member(self):
        self.feed(group_message("/projects", user_id=MEMBER_ID))
        self.assertIn("только администраторам", self.session.texts[0])

    def test_invite_command_returns_group_link(self):
        self.feed(group_message("/invite test-site", user_id=ADMIN_ID))
        text = self.session.texts[0]
        self.assertIn("?startgroup=", text)
        self.assertIn("?start=", text)


class SupergroupMigrationTests(TransactionTestCase):
    def test_migrate_updates_chat_id(self):
        from bot.handlers import _migrate_chat_id

        project = Project.objects.create(name="P", slug="p", token_hash=hash_token("x"))
        recipient = Recipient.objects.create(chat_id=-100, kind="group", title="Группа")
        Subscription.objects.create(project=project, recipient=recipient)

        asyncio.run(_migrate_chat_id(-100, GROUP_ID))

        recipient.refresh_from_db()
        self.assertEqual(recipient.chat_id, GROUP_ID)
        self.assertEqual(
            Subscription.objects.filter(recipient__chat_id=GROUP_ID, is_active=True).count(), 1
        )
