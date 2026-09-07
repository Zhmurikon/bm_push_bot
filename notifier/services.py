import json
import os

from aiohttp import ClientSession
from aiohttp_socks import ProxyConnector
from django.template import Context, Template
from django.utils import timezone

DEFAULT_TEMPLATE = (
    "🔔 Новая заявка — {{ project }}\n"
    "{% for label, value in fields %}"
    "{{ label }}: {{ value }}\n"
    "{% endfor %}"
    "🕓 {{ created_at }}"
)


def _get_session():
    proxy_url = os.getenv("PROXY_URL", "")
    connector = ProxyConnector.from_url(proxy_url) if proxy_url else None
    return ClientSession(connector=connector)


def _bot_url(method: str) -> str:
    token = os.getenv("BOT_TOKEN", "")
    return f"https://api.telegram.org/bot{token}/{method}"


def build_lead_keyboard(lead_id: int, status: str) -> list | None:
    if status == "new":
        return [[{"text": "📋 Взял в работу", "callback_data": f"lead:{lead_id}:in_progress"}]]
    if status == "in_progress":
        return [[{"text": "✅ Обработана", "callback_data": f"lead:{lead_id}:done"}]]
    return None


def render_lead_text(project, payload: dict, source: str = "") -> str:
    template_str = project.template or DEFAULT_TEMPLATE
    template = Template(template_str)
    context = Context(
        {
            "project": project.name,
            "fields": payload.get("fields", {}).items(),
            "created_at": timezone.localtime().strftime("%d.%m.%Y, %H:%M"),
            "source": source,
        }
    )
    return template.render(context).strip()


async def send_telegram_message(chat_id: int, text: str, reply_markup: list | None = None) -> dict:
    async with _get_session() as session:
        data = {"chat_id": chat_id, "text": text}
        if reply_markup:
            data["reply_markup"] = json.dumps({"inline_keyboard": reply_markup})

        async with session.post(_bot_url("sendMessage"), json=data, timeout=10) as resp:
            body = await resp.json()
            result = body.get("result", {})
            message_id = result.get("message_id") if isinstance(result, dict) else None
            return {
                "ok": body.get("ok", False),
                "message_id": message_id,
                "error": body.get("description", ""),
            }


async def edit_telegram_message(chat_id: int, message_id: int, text: str, reply_markup: list | None = None) -> dict:
    async with _get_session() as session:
        data = {"chat_id": chat_id, "message_id": message_id, "text": text}
        if reply_markup:
            data["reply_markup"] = json.dumps({"inline_keyboard": reply_markup})
        else:
            data["reply_markup"] = json.dumps({"inline_keyboard": []})

        async with session.post(_bot_url("editMessageText"), json=data, timeout=10) as resp:
            body = await resp.json()
            return {
                "ok": body.get("ok", False),
                "error": body.get("description", ""),
            }
