import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models import Contact, OutreachDraft, PainHypothesis, Research
from app.schemas import (
    ContactCreate,
    ContactRead,
    DeliveryResponse,
    DraftRead,
    HealthResponse,
    ResearchBundle,
    WebhookOutreachRequest,
    WebhookOutreachResponse,
)
from app.services.approval import InvalidTransition, approve, reject
from app.services.delivery import DeliveryError, deliver
from app.services.personalization import create_draft
from app.services.research import run_research
from app.services.scraper import ScrapeError
from app.services.url_safety import UnsafeURLError, validate_public_url

logger = logging.getLogger(__name__)
router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


async def get_app_settings() -> Settings:
    return get_settings()


AppSettings = Annotated[Settings, Depends(get_app_settings)]


def _get_contact(db: Session, contact_id: int) -> Contact:
    contact = db.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


def _get_draft(db: Session, draft_id: int) -> OutreachDraft:
    draft = db.get(OutreachDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


def _create_contact(db: Session, data: ContactCreate) -> Contact:
    try:
        validate_public_url(str(data.company_website))
    except UnsafeURLError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    contact = Contact(**data.model_dump(mode="json"))
    db.add(contact)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="A contact with this email already exists"
        ) from exc
    db.refresh(contact)
    return contact


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health(settings: AppSettings) -> HealthResponse:
    return HealthResponse(
        status="ok",
        delivery_mode=settings.delivery_mode,
        llm_configured=bool(settings.llm_api_key),
    )


@router.post(
    "/contacts", response_model=ContactRead, status_code=status.HTTP_201_CREATED, tags=["contacts"]
)
async def add_contact(payload: ContactCreate, db: DbSession) -> Contact:
    return _create_contact(db, payload)


@router.get("/contacts", response_model=list[ContactRead], tags=["contacts"])
async def list_contacts(db: DbSession) -> list[Contact]:
    return list(db.scalars(select(Contact).order_by(Contact.id)).all())


@router.get("/contacts/{contact_id}", response_model=ContactRead, tags=["contacts"])
async def get_contact(contact_id: int, db: DbSession) -> Contact:
    return _get_contact(db, contact_id)


@router.post(
    "/contacts/{contact_id}/research",
    response_model=ResearchBundle,
    status_code=status.HTTP_201_CREATED,
    tags=["research"],
)
async def research_contact(
    contact_id: int,
    db: DbSession,
    settings: AppSettings,
) -> ResearchBundle:
    try:
        return await run_research(db, _get_contact(db, contact_id), settings)
    except (ScrapeError, UnsafeURLError) as exc:
        raise HTTPException(status_code=422, detail=f"Research failed: {exc}") from exc


@router.get("/contacts/{contact_id}/research", response_model=ResearchBundle, tags=["research"])
async def get_research(contact_id: int, db: DbSession) -> ResearchBundle:
    _get_contact(db, contact_id)
    research = db.scalar(
        select(Research)
        .where(Research.contact_id == contact_id)
        .order_by(Research.created_at.desc(), Research.id.desc())
    )
    if research is None:
        raise HTTPException(status_code=404, detail="Research not found")
    hypotheses = list(
        db.scalars(
            select(PainHypothesis)
            .where(PainHypothesis.contact_id == contact_id)
            .order_by(PainHypothesis.id)
        ).all()
    )
    return ResearchBundle(research=research, hypotheses=hypotheses)


@router.post(
    "/contacts/{contact_id}/draft",
    response_model=DraftRead,
    status_code=status.HTTP_201_CREATED,
    tags=["outreach"],
)
async def draft_contact(
    contact_id: int,
    db: DbSession,
    settings: AppSettings,
) -> OutreachDraft:
    try:
        return await create_draft(db, _get_contact(db, contact_id), settings)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/contacts/{contact_id}/draft", response_model=DraftRead, tags=["outreach"])
async def get_draft_for_contact(contact_id: int, db: DbSession) -> OutreachDraft:
    _get_contact(db, contact_id)
    draft = db.scalar(
        select(OutreachDraft)
        .where(OutreachDraft.contact_id == contact_id)
        .order_by(OutreachDraft.created_at.desc(), OutreachDraft.id.desc())
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@router.post("/drafts/{draft_id}/approve", response_model=DraftRead, tags=["approval"])
async def approve_draft(draft_id: int, db: DbSession) -> OutreachDraft:
    draft = _get_draft(db, draft_id)
    try:
        approve(draft)
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    db.refresh(draft)
    return draft


@router.post("/drafts/{draft_id}/reject", response_model=DraftRead, tags=["approval"])
async def reject_draft(draft_id: int, db: DbSession) -> OutreachDraft:
    draft = _get_draft(db, draft_id)
    try:
        reject(draft)
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    db.refresh(draft)
    return draft


@router.post("/drafts/{draft_id}/send", response_model=DeliveryResponse, tags=["delivery"])
async def send_draft(
    draft_id: int,
    db: DbSession,
    settings: AppSettings,
) -> DeliveryResponse:
    draft = _get_draft(db, draft_id)
    contact = _get_contact(db, draft.contact_id)
    try:
        result = await deliver(draft, contact, settings)
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (DeliveryError, UnsafeURLError) as exc:
        db.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    db.commit()
    db.refresh(draft)
    return DeliveryResponse(draft=DraftRead.model_validate(draft), delivery=result)


@router.post(
    "/webhooks/outreach",
    response_model=WebhookOutreachResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["integrations"],
)
async def inbound_outreach_webhook(
    payload: WebhookOutreachRequest,
    db: DbSession,
    settings: AppSettings,
) -> WebhookOutreachResponse:
    contact_data = ContactCreate.model_validate(payload.model_dump(exclude={"trigger_processing"}))
    contact = _create_contact(db, contact_data)
    should_process = settings.webhook_auto_process and payload.trigger_processing is not False
    if not should_process:
        return WebhookOutreachResponse(
            contact=ContactRead.model_validate(contact),
            next_action=f"POST /contacts/{contact.id}/research",
        )
    try:
        research = await run_research(db, contact, settings)
        draft = await create_draft(db, contact, settings)
    except (ScrapeError, UnsafeURLError) as exc:
        logger.info("Webhook created contact %s but processing failed", contact.id)
        raise HTTPException(
            status_code=422,
            detail={"contact_id": contact.id, "processing_error": str(exc)},
        ) from exc
    return WebhookOutreachResponse(
        contact=ContactRead.model_validate(contact),
        research=research,
        draft=DraftRead.model_validate(draft),
        next_action=f"Human review required: POST /drafts/{draft.id}/approve or /reject",
    )
