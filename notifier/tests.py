"""Тесты API заявок — доставка в групповой чат."""

from unittest import mock

from django.test import TestCase

from notifier.models import Delivery, Lead, Project, Recipient, Subscription, hash_token

TOKEN = "bmp_live_testtoken"
GROUP_ID = -1001234567890
NEW_GROUP_ID = -1009876543210


class LeadApiTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(
            name="Сайт клиента", slug="test-site", token_hash=hash_token(TOKEN)
        )
        self.recipient = Recipient.objects.create(
            chat_id=GROUP_ID, kind="group", title="Отдел продаж"
        )
        Subscription.objects.create(project=self.project, recipient=self.recipient)

    def post_lead(self, **extra):
        return self.client.post(
            "/api/v1/leads/",
            data={"fields": {"Имя": "Иван", "Телефон": "+79999999999"}, "source": "форма"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
            **extra,
        )

    def test_lead_delivered_to_group_with_buttons(self):
        send = mock.Mock(return_value={"ok": True, "message_id": 100, "error": "", "parameters": {}})
        with mock.patch("notifier.views._send_message", send):
            response = self.post_lead()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["delivered"], 1)

        chat_id, text, markup = send.call_args[0]
        self.assertEqual(chat_id, GROUP_ID)
        self.assertIn("Иван", text)
        self.assertIn("lead:", markup[0][0]["callback_data"])

        delivery = Delivery.objects.get()
        self.assertTrue(delivery.ok)
        self.assertEqual(delivery.message_id, 100)

    def test_bad_token_rejected(self):
        response = self.client.post(
            "/api/v1/leads/",
            data={"fields": {"Имя": "Иван"}},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer bmp_live_wrong",
        )
        self.assertEqual(response.status_code, 401)

    def test_idempotency_key_prevents_duplicate(self):
        send = mock.Mock(return_value={"ok": True, "message_id": 1, "error": "", "parameters": {}})
        with mock.patch("notifier.views._send_message", send):
            first = self.post_lead(HTTP_IDEMPOTENCY_KEY="abc-123")
            second = self.post_lead(HTTP_IDEMPOTENCY_KEY="abc-123")

        self.assertEqual(Lead.objects.count(), 1)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertTrue(second.json()["duplicate"])

    def test_group_upgraded_to_supergroup_is_followed(self):
        """Группа стала супергруппой: chat_id меняется, отправка повторяется."""
        send = mock.Mock(
            side_effect=[
                {
                    "ok": False,
                    "message_id": None,
                    "error": "Bad Request: group chat was upgraded to a supergroup chat",
                    "parameters": {"migrate_to_chat_id": NEW_GROUP_ID},
                },
                {"ok": True, "message_id": 200, "error": "", "parameters": {}},
            ]
        )
        with mock.patch("notifier.views._send_message", send):
            response = self.post_lead()

        self.assertEqual(response.json()["delivered"], 1)
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.chat_id, NEW_GROUP_ID)
        self.assertTrue(self.recipient.is_active)
        self.assertEqual(send.call_args_list[1][0][0], NEW_GROUP_ID)

    def test_blocked_chat_is_deactivated(self):
        send = mock.Mock(
            return_value={
                "ok": False,
                "message_id": None,
                "error": "Forbidden: bot was blocked by the user",
                "parameters": {},
            }
        )
        with mock.patch("notifier.views._send_message", send):
            response = self.post_lead()

        self.assertEqual(response.json()["delivered"], 0)
        self.recipient.refresh_from_db()
        self.assertFalse(self.recipient.is_active)
