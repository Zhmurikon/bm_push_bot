import hashlib
import secrets

from django.db import models
from django.utils import timezone


def generate_token() -> str:
    return f"bmp_live_{secrets.token_urlsafe(32)}"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Project(models.Model):
    name = models.CharField("название", max_length=200)
    slug = models.SlugField("слаг", unique=True)
    site_url = models.URLField("URL сайта", blank=True)
    token_hash = models.CharField("хеш токена", max_length=64, unique=True, editable=False)
    template = models.TextField(
        "шаблон сообщения",
        blank=True,
        help_text="Django-шаблон. Переменные: project, fields, created_at, source",
    )
    buttons_enabled = models.BooleanField("кнопки статусов", default=True)
    is_active = models.BooleanField("активен", default=True)
    created_at = models.DateTimeField("создан", auto_now_add=True)

    class Meta:
        verbose_name = "проект"
        verbose_name_plural = "проекты"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Recipient(models.Model):
    class Kind(models.TextChoices):
        PRIVATE = "private", "Личный чат"
        GROUP = "group", "Группа"

    chat_id = models.BigIntegerField("chat_id", unique=True)
    kind = models.CharField("тип", max_length=10, choices=Kind.choices, default=Kind.PRIVATE)
    title = models.CharField("название", max_length=255, blank=True)
    is_admin = models.BooleanField("администратор", default=False)
    is_active = models.BooleanField("активен", default=True)
    created_at = models.DateTimeField("создан", auto_now_add=True)

    class Meta:
        verbose_name = "получатель"
        verbose_name_plural = "получатели"
        ordering = ["title"]

    def __str__(self):
        return self.title or str(self.chat_id)


class Subscription(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="subscriptions", verbose_name="проект"
    )
    recipient = models.ForeignKey(
        Recipient, on_delete=models.CASCADE, related_name="subscriptions", verbose_name="получатель"
    )
    is_active = models.BooleanField("активна", default=True)
    subscribed_at = models.DateTimeField("подключён", auto_now_add=True)

    class Meta:
        verbose_name = "подписка"
        verbose_name_plural = "подписки"
        unique_together = [("project", "recipient")]

    def __str__(self):
        return f"{self.project} → {self.recipient}"


class Lead(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Новая"
        IN_PROGRESS = "in_progress", "В работе"
        DONE = "done", "Обработана"

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="leads", verbose_name="проект"
    )
    payload = models.JSONField("данные")
    rendered_text = models.TextField("отправленный текст")
    source = models.CharField("источник", max_length=200, blank=True)
    status = models.CharField("статус", max_length=20, choices=Status.choices, default=Status.NEW)
    idempotency_key = models.CharField(
        "ключ идемпотентности", max_length=255, blank=True, db_index=True
    )
    created_at = models.DateTimeField("создана", auto_now_add=True)

    class Meta:
        verbose_name = "заявка"
        verbose_name_plural = "заявки"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Заявка #{self.pk} — {self.project}"
