import json

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Contact, PainHypothesis, Research
from app.schemas import ResearchBundle, Signal
from app.services.extraction import (
    extract_signals,
    infer_business_model,
    infer_target_market,
    summarize_company,
)
from app.services.llm import LLMError, OpenAICompatibleLLM
from app.services.scraper import ScrapedPage, WebsiteScraper


class HypothesisOutput(BaseModel):
    hypothesis: str
    evidence: str
    confidence: float = Field(ge=0, le=1)


class HypothesesOutput(BaseModel):
    hypotheses: list[HypothesisOutput] = Field(max_length=3)


def fallback_hypotheses(signals: list[Signal]) -> list[HypothesisOutput]:
    """Produce only hypotheses directly mapped to extracted, cited signals."""
    by_name = {signal.name: signal for signal in signals}
    results: list[HypothesisOutput] = []
    if signal := by_name.get("demo-led sales motion"):
        results.append(
            HypothesisOutput(
                hypothesis=(
                    "Hypothesis: the revenue team may spend meaningful time researching and "
                    "qualifying accounts before sales conversations."
                ),
                evidence=f"Website evidence: {signal.evidence} (source: {signal.source_url})",
                confidence=0.68,
            )
        )
    if signal := by_name.get("hiring or growth"):
        results.append(
            HypothesisOutput(
                hypothesis=(
                    "Hypothesis: growth may be increasing the need for a repeatable account "
                    "research workflow."
                ),
                evidence=f"Website evidence: {signal.evidence} (source: {signal.source_url})",
                confidence=0.62,
            )
        )
    return results


async def _generate_hypotheses(
    llm: OpenAICompatibleLLM, signals: list[Signal]
) -> list[HypothesisOutput]:
    fallback = fallback_hypotheses(signals)
    if not llm.configured or not signals:
        return fallback
    prompt = json.dumps([signal.model_dump() for signal in signals])
    try:
        result = await llm.structured_completion(
            system=(
                "Generate at most three cautious B2B pain hypotheses using only the supplied "
                "website signals. Prefix every hypothesis with 'Hypothesis:'. Evidence must quote "
                "or paraphrase supplied evidence and include its source URL. Return JSON with a "
                "hypotheses array. Never claim speculation as fact."
            ),
            prompt=prompt,
            output_model=HypothesesOutput,
        )
    except LLMError:
        return fallback
    source_urls = {signal.source_url for signal in signals}
    evidence_text = " ".join(signal.evidence.lower() for signal in signals)
    validated: list[HypothesisOutput] = []
    for item in result.hypotheses:
        has_source = any(url in item.evidence for url in source_urls)
        has_overlap = any(
            word in evidence_text for word in item.evidence.lower().split() if len(word) > 5
        )
        if item.hypothesis.startswith("Hypothesis:") and has_source and has_overlap:
            validated.append(item)
    return validated or fallback


async def run_research(db: Session, contact: Contact, settings: Settings) -> ResearchBundle:
    pages: list[ScrapedPage] = await WebsiteScraper(settings).scrape(contact.company_website)
    signals = extract_signals(pages)
    research = Research(
        contact_id=contact.id,
        company_summary=summarize_company(contact.company_name, pages, signals),
        business_model=infer_business_model(signals),
        target_market=infer_target_market(signals),
        detected_signals=[signal.model_dump() for signal in signals],
        source_urls=list(dict.fromkeys(page.url for page in pages)),
    )
    db.add(research)
    db.flush()
    hypotheses = await _generate_hypotheses(OpenAICompatibleLLM(settings), signals)
    hypothesis_models = [
        PainHypothesis(contact_id=contact.id, **item.model_dump()) for item in hypotheses
    ]
    db.add_all(hypothesis_models)
    db.commit()
    db.refresh(research)
    for hypothesis in hypothesis_models:
        db.refresh(hypothesis)
    return ResearchBundle(research=research, hypotheses=hypothesis_models)
