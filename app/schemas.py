from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl

from app.models import DraftStatus


class ContactCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    role: str = Field(min_length=1, max_length=200)
    company_name: str = Field(min_length=1, max_length=200)
    company_website: HttpUrl


class ContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str
    role: str
    company_name: str
    company_website: str


class Signal(BaseModel):
    name: str
    evidence: str
    source_url: str
    confidence: float = Field(ge=0, le=1)


class ResearchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contact_id: int
    company_summary: str
    business_model: str
    target_market: str
    detected_signals: list[dict[str, Any]]
    source_urls: list[str]
    created_at: datetime


class PainHypothesisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contact_id: int
    hypothesis: str
    evidence: str
    confidence: float


class ResearchBundle(BaseModel):
    research: ResearchRead
    hypotheses: list[PainHypothesisRead]


class DraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contact_id: int
    subject: str
    body: str
    status: DraftStatus
    approved_at: datetime | None
    sent_at: datetime | None
    created_at: datetime


class WebhookOutreachRequest(ContactCreate):
    trigger_processing: bool | None = None


class WebhookOutreachResponse(BaseModel):
    contact: ContactRead
    research: ResearchBundle | None = None
    draft: DraftRead | None = None
    next_action: str


class HealthResponse(BaseModel):
    status: str
    delivery_mode: str
    llm_configured: bool


class DeliveryResponse(BaseModel):
    draft: DraftRead
    delivery: dict[str, Any]
