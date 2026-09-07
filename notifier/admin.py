from django.contrib import admin, messages
from django.utils.html import format_html

from .models import Lead, Project, Recipient, Subscription, generate_token, hash_token


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
    inlines = [SubscriptionInline]

    _created_tokens: dict[int, str] = {}

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


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ["__str__", "project", "status", "source", "created_at"]
    list_filter = ["status", "project"]
    search_fields = ["payload"]
    readonly_fields = ["project", "payload", "rendered_text", "source", "idempotency_key", "created_at"]
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False
