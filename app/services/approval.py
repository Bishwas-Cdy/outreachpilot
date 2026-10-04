from datetime import UTC, datetime

from app.models import DraftStatus, OutreachDraft


class InvalidTransition(ValueError):
    pass


def approve(draft: OutreachDraft) -> None:
    if draft.status != DraftStatus.AWAITING_APPROVAL:
        raise InvalidTransition(f"Cannot approve a draft with status '{draft.status.value}'")
    draft.status = DraftStatus.APPROVED
    draft.approved_at = datetime.now(UTC)


def reject(draft: OutreachDraft) -> None:
    if draft.status != DraftStatus.AWAITING_APPROVAL:
        raise InvalidTransition(f"Cannot reject a draft with status '{draft.status.value}'")
    draft.status = DraftStatus.REJECTED


def assert_sendable(draft: OutreachDraft) -> None:
    if draft.status != DraftStatus.APPROVED:
        raise InvalidTransition("Only an approved draft can be sent")
