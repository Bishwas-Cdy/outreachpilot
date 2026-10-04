import re

from app.schemas import Signal
from app.services.scraper import ScrapedPage


def _snippet(text: str, match: re.Match[str], radius: int = 100) -> str:
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    return text[start:end].strip(" ,.-")


SIGNAL_PATTERNS: tuple[tuple[str, re.Pattern[str], float], ...] = (
    ("demo-led sales motion", re.compile(r"\b(book|request|schedule) (a )?demo\b", re.I), 0.9),
    (
        "B2B or enterprise focus",
        re.compile(r"\b(B2B|enterprise|businesses|companies)\b", re.I),
        0.72,
    ),
    (
        "hiring or growth",
        re.compile(r"\b(we('| a)re hiring|join our team|open roles|careers)\b", re.I),
        0.85,
    ),
    ("software product", re.compile(r"\b(platform|software|SaaS|API)\b", re.I), 0.72),
    ("services business", re.compile(r"\b(consulting|agency|professional services)\b", re.I), 0.78),
)


def extract_signals(pages: list[ScrapedPage]) -> list[Signal]:
    signals: list[Signal] = []
    seen: set[str] = set()
    for page in pages:
        for name, pattern, confidence in SIGNAL_PATTERNS:
            if name in seen:
                continue
            match = pattern.search(page.text)
            if match:
                signals.append(
                    Signal(
                        name=name,
                        evidence=_snippet(page.text, match),
                        source_url=page.url,
                        confidence=confidence,
                    )
                )
                seen.add(name)
    return signals


def summarize_company(company_name: str, pages: list[ScrapedPage], signals: list[Signal]) -> str:
    if not pages or not pages[0].text:
        return f"No usable public website content was found for {company_name}."
    signal_names = ", ".join(signal.name for signal in signals[:3])
    if signal_names:
        return f"{company_name}'s public website indicates: {signal_names}."
    return (
        f"{company_name} has a public website, but no supported structured signals were detected."
    )


def infer_business_model(signals: list[Signal]) -> str:
    names = {signal.name for signal in signals}
    if "software product" in names:
        return "Software or platform business (website-derived classification)"
    if "services business" in names:
        return "Services business (website-derived classification)"
    return "Not determined from available website evidence"


def infer_target_market(signals: list[Signal]) -> str:
    if any(signal.name == "B2B or enterprise focus" for signal in signals):
        return "Businesses or enterprise buyers (website-derived classification)"
    return "Not determined from available website evidence"
