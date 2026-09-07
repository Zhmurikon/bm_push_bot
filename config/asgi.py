import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_asgi_app = get_asgi_application()

from bot.app import telegram_webhook_app  # noqa: E402

application = telegram_webhook_app(django_asgi_app)
