from django.contrib import admin
from django.urls import include, path

from notifier.telegram_webhook import telegram_webhook

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("notifier.urls")),
    path("tg/<str:secret>/", telegram_webhook, name="telegram-webhook"),
]
