import json

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Contact, DraftStatus, OutreachDraft, PainHypothesis, Research
from app.services.llm import LLMError, OpenAICompatibleLLM


class DraftOutput(BaseModel):
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1)


def _fallback_draft(
    contact: Contact,
    research: Research,
    hypothesis: PainHypothesis | None,
    settings: Settings,
) -> DraftOutput:
    signals = research.detected_signals
    observation = (
        f"I noticed {contact.company_name}'s website highlights {signals[0]['name']}."
        if signals
        else f"I was looking at {contact.company_name}'s public website."
    )
    pain = (
        hypothesis.hypothesis.removeprefix("Hypothesis:").strip().capitalize()
        if hypothesis
        else "Your team may be exploring ways to make account research more consistent."
    )
    body = (
        f"Hi {contact.first_name},\n\n{observation}\n\n"
        f"Given your role as {contact.role}, I thought this might be relevant: {pain}\n\n"
        f"{settings.value_proposition}\n\n"
        f"Would it be useful if I sent over a short example?\n\nBest,\n{settings.sender_name}"
    )
    return DraftOutput(subject=f"A research workflow for {contact.company_name}", body=body)


async def create_draft(db: Session, contact: Contact, settings: Settings) -> OutreachDraft:
    research = db.scalar(
        select(Research)
        .where(Research.contact_id == contact.id)
        .order_by(Research.created_at.desc(), Research.id.desc())
    )
    if research is None:
        raise ValueError("Research must be completed before creating a draft")
    hypothesis = db.scalar(
        select(PainHypothesis)
        .where(PainHypothesis.contact_id == contact.id)
        .order_by(PainHypothesis.id.desc())
    )
    fallback = _fallback_draft(contact, research, hypothesis, settings)
    llm = OpenAICompatibleLLM(settings)
    output = fallback
    if llm.configured:
        inputs = {
            "contact": {
                "first_name": contact.first_name,
                "role": contact.role,
                "company_name": contact.company_name,
            },
            "signals": research.detected_signals,
            "pain_hypothesis": (
                {"hypothesis": hypothesis.hypothesis, "evidence": hypothesis.evidence}
                if hypothesis
                else None
            ),
            "value_proposition": settings.value_proposition,
            "sender_name": settings.sender_name,
        }
        try:
            candidate = await llm.structured_completion(
                system=(
                    "Write a natural outbound email under 120 words. Use only supplied evidence, "
                    "call speculation a possibility, avoid hype and fake familiarity, and include "
                    "one clear low-pressure CTA. Return JSON with subject and body."
                ),
                prompt=json.dumps(inputs),
                output_model=DraftOutput,
            )
            if len(candidate.body.split()) <= 120:
                output = candidate
        except LLMError:
            pass
    draft = OutreachDraft(
        contact_id=contact.id,
        subject=output.subject,
        body=output.body,
        status=DraftStatus.AWAITING_APPROVAL,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft
