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


async def send_telegram_message(chat_id: int, text: str) -> dict:
    """Отправить сообщение через Telegram Bot API напрямую (без aiogram)."""
    token = os.getenv("BOT_TOKEN", "")
    proxy_url = os.getenv("PROXY_URL", "")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "",
    }

    connector = None
    if proxy_url:
        connector = ProxyConnector.from_url(proxy_url)

    async with ClientSession(connector=connector) as session:
        async with session.post(url, json=data, timeout=10) as resp:
            body = await resp.json()
            return {"ok": body.get("ok", False), "result": body.get("result"), "error": body.get("description")}
