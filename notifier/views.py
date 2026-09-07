import logging

from asgiref.sync import async_to_sync
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from .models import Delivery, Lead, Project, Subscription, hash_token
from .serializers import LeadSerializer
from .services import build_lead_keyboard, render_lead_text, send_telegram_message

logger = logging.getLogger(__name__)

_send_message = async_to_sync(send_telegram_message)


def _get_project_by_token(auth_header: str) -> Project | None:
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    token_hash = hash_token(token)
    try:
        return Project.objects.get(token_hash=token_hash, is_active=True)
    except Project.DoesNotExist:
        return None


@api_view(["POST"])
def create_lead(request: Request):
    auth = request.META.get("HTTP_AUTHORIZATION", "")
    project = _get_project_by_token(auth)
    if not project:
        return Response({"detail": "Неверный токен"}, status=status.HTTP_401_UNAUTHORIZED)

    idempotency_key = request.META.get("HTTP_IDEMPOTENCY_KEY", "")
    if idempotency_key:
        existing = Lead.objects.filter(project=project, idempotency_key=idempotency_key).first()
        if existing:
            return Response({"id": existing.pk, "delivered": 0, "duplicate": True}, status=status.HTTP_201_CREATED)

    serializer = LeadSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    payload = {"fields": data.get("fields", {}), "text": data.get("text", "")}
    source = data.get("source", "")

    if payload.get("text"):
        rendered_text = payload["text"]
    else:
        rendered_text = render_lead_text(project, payload, source)

    lead = Lead.objects.create(
        project=project,
        payload=payload,
        rendered_text=rendered_text,
        source=source,
        idempotency_key=idempotency_key,
    )

    subscriptions = Subscription.objects.filter(
        project=project, is_active=True, recipient__is_active=True
    ).select_related("recipient")

    reply_markup = build_lead_keyboard(lead.pk, lead.status) if project.buttons_enabled else None

    delivered = 0
    for sub in subscriptions:
        try:
            result = _send_message(sub.recipient.chat_id, rendered_text, reply_markup)
            delivery = Delivery.objects.create(
                lead=lead,
                recipient=sub.recipient,
                message_id=result.get("message_id"),
                ok=result["ok"],
                error=result.get("error", ""),
            )
            if result["ok"]:
                delivered += 1
            else:
                logger.warning("Telegram error for chat %s: %s", sub.recipient.chat_id, result.get("error"))
                error_str = str(result.get("error", ""))
                if "bot was blocked" in error_str or "chat not found" in error_str:
                    sub.recipient.is_active = False
                    sub.recipient.save(update_fields=["is_active"])
        except TimeoutError:
            Delivery.objects.create(lead=lead, recipient=sub.recipient, error="timeout")
            logger.warning("Telegram timeout for chat %s", sub.recipient.chat_id)
        except Exception as exc:
            Delivery.objects.create(lead=lead, recipient=sub.recipient, error=str(exc))
            logger.exception("Failed to send to chat %s", sub.recipient.chat_id)

    return Response({"id": lead.pk, "delivered": delivered}, status=status.HTTP_201_CREATED)
