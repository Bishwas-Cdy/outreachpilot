from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import Settings
from app.models import Contact, DraftStatus, OutreachDraft
from app.services.approval import assert_sendable
from app.services.url_safety import validate_public_url


class DeliveryError(RuntimeError):
    pass


async def deliver(draft: OutreachDraft, contact: Contact, settings: Settings) -> dict[str, Any]:
    assert_sendable(draft)
    if settings.delivery_mode == "mock":
        result: dict[str, Any] = {
            "mode": "mock",
            "accepted": True,
            "recipient": contact.email,
            "message": "Approved draft recorded as sent; no email provider was contacted.",
        }
    else:
        if not settings.outbound_webhook_url:
            raise DeliveryError("OUTBOUND_WEBHOOK_URL is required in webhook delivery mode")
        url = validate_public_url(settings.outbound_webhook_url, require_https=True)
        payload = {
            "draft_id": draft.id,
            "contact": {
                "email": contact.email,
                "name": f"{contact.first_name} {contact.last_name}",
            },
            "message": {"subject": draft.subject, "body": draft.body},
            "approved_at": draft.approved_at.isoformat() if draft.approved_at else None,
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
            result = {"mode": "webhook", "accepted": True, "status_code": response.status_code}
        except httpx.HTTPError as exc:
            draft.status = DraftStatus.FAILED
            raise DeliveryError("Outbound webhook delivery failed") from exc
    draft.status = DraftStatus.SENT
    draft.sent_at = datetime.now(UTC)
    return result
