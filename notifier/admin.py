from django.contrib import admin, messages
from django.utils.html import format_html

from .models import Delivery, Invite, Lead, Project, Recipient, Subscription, generate_token, hash_token


class InviteInline(admin.TabularInline):
    model = Invite
    extra = 0
    readonly_fields = ["code", "used_by", "used_at"]
    fields = ["code", "expires_at", "is_multi_use", "is_active"]


class SubscriptionInline(admin.TabularInline):
    model = Subscription
    extra = 0
    autocomplete_fields = ["recipient"]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "site_url", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [SubscriptionInline, InviteInline]
    readonly_fields = ["template_preview"]
    fieldsets = (
        (None, {"fields": ("name", "slug", "site_url", "is_active")}),
        ("Сообщения", {"fields": ("template", "template_preview", "buttons_enabled")}),
    )

    _created_tokens: dict[int, str] = {}

    @admin.display(description="предпросмотр")
    def template_preview(self, obj):
        from .services import render_lead_text
        sample_payload = {"fields": {"Имя": "Иван Иванов", "Телефон": "+7 999 123-45-67"}}
        try:
            text = render_lead_text(obj, sample_payload, "тестовая форма")
            return format_html("<pre style='white-space:pre-wrap'>{}</pre>", text)
        except Exception as e:
            return format_html("<span style='color:red'>Ошибка: {}</span>", e)

    def save_model(self, request, obj, form, change):
        if not change:
            token = generate_token()
            obj.token_hash = hash_token(token)
            super().save_model(request, obj, form, change)
            self._created_tokens[obj.pk] = token
        else:
            super().save_model(request, obj, form, change)

    def response_add(self, request, obj, post_url_continue=None):
        token = self._created_tokens.pop(obj.pk, None)
        if token:
            messages.success(
                request,
                format_html(
                    'Проект создан. <b>Сохраните токен — он показан только один раз:</b>'
                    "<br><code>{}</code>",
                    token,
                ),
            )
        return super().response_add(request, obj, post_url_continue)


@admin.register(Recipient)
class RecipientAdmin(admin.ModelAdmin):
    list_display = ["title", "chat_id", "kind", "is_active", "is_admin", "created_at"]
    list_filter = ["kind", "is_active", "is_admin"]
    search_fields = ["title", "chat_id"]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["project", "recipient", "is_active", "subscribed_at"]
    list_filter = ["is_active", "project"]
    autocomplete_fields = ["project", "recipient"]


class DeliveryInline(admin.TabularInline):
    model = Delivery
    extra = 0
    readonly_fields = ["recipient", "message_id", "ok", "error", "sent_at"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ["__str__", "project", "status", "delivered_count", "source", "created_at"]
    list_filter = ["status", "project"]
    search_fields = ["payload"]
    readonly_fields = ["project", "payload", "rendered_text", "source", "idempotency_key", "created_at"]
    date_hierarchy = "created_at"
    inlines = [DeliveryInline]

    def has_add_permission(self, request):
        return False

    @admin.display(description="доставлено")
    def delivered_count(self, obj):
        ok = obj.deliveries.filter(ok=True).count()
        total = obj.deliveries.count()
        return f"{ok}/{total}"


@admin.register(Invite)
class InviteAdmin(admin.ModelAdmin):
    list_display = ["code", "project", "invite_link_display", "is_multi_use", "is_valid", "used_by", "expires_at"]
    list_filter = ["is_active", "is_multi_use", "project"]
    search_fields = ["code"]
    readonly_fields = ["code", "used_by", "used_at", "invite_link_display", "group_link_display"]
    autocomplete_fields = ["project"]

    def invite_link_display(self, obj):
        return format_html('<a href="{}">{}</a>', obj.invite_link, obj.invite_link)

    invite_link_display.short_description = "ссылка (личный чат)"

    def group_link_display(self, obj):
        return format_html('<a href="{}">{}</a>', obj.group_invite_link, obj.group_invite_link)

    group_link_display.short_description = "ссылка (добавить в группу)"
