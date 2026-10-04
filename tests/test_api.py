from typing import Any

import pytest
from httpx import AsyncClient

from app.services.scraper import ScrapedPage, WebsiteScraper


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "delivery_mode": "mock",
        "llm_configured": False,
    }


async def test_contact_creation(client: AsyncClient, contact_payload: dict[str, str]) -> None:
    response = await client.post("/contacts", json=contact_payload)
    assert response.status_code == 201
    assert response.json()["company_name"] == "Acme Health"
    assert (await client.get("/contacts/1")).status_code == 200
    assert len((await client.get("/contacts")).json()) == 1


@pytest.fixture
def mock_scrape(monkeypatch: pytest.MonkeyPatch) -> None:
    async def scrape(_: WebsiteScraper, website: str) -> list[ScrapedPage]:
        return [
            ScrapedPage(
                url=website,
                title="Acme Health",
                text=(
                    "Acme Health is an enterprise software platform for healthcare companies. "
                    "Request a demo to learn more. Join our team—we are hiring."
                ),
            )
        ]

    monkeypatch.setattr(WebsiteScraper, "scrape", scrape)


async def _create_researched_contact(
    client: AsyncClient, contact_payload: dict[str, str]
) -> tuple[int, dict[str, Any]]:
    contact_id = (await client.post("/contacts", json=contact_payload)).json()["id"]
    research_response = await client.post(f"/contacts/{contact_id}/research")
    assert research_response.status_code == 201
    return contact_id, research_response.json()


async def test_research_flow(
    client: AsyncClient, contact_payload: dict[str, str], mock_scrape: None
) -> None:
    contact_id, bundle = await _create_researched_contact(client, contact_payload)
    signals = bundle["research"]["detected_signals"]
    assert any(signal["name"] == "demo-led sales motion" for signal in signals)
    assert all(
        signal["source_url"].rstrip("/") == contact_payload["company_website"] for signal in signals
    )
    assert all(item["hypothesis"].startswith("Hypothesis:") for item in bundle["hypotheses"])
    assert (await client.get(f"/contacts/{contact_id}/research")).status_code == 200


async def test_draft_and_approval_flow(
    client: AsyncClient, contact_payload: dict[str, str], mock_scrape: None
) -> None:
    contact_id, _ = await _create_researched_contact(client, contact_payload)
    draft_response = await client.post(f"/contacts/{contact_id}/draft")
    assert draft_response.status_code == 201
    draft = draft_response.json()
    assert draft["status"] == "awaiting_approval"
    assert len(draft["body"].split()) <= 120

    blocked = await client.post(f"/drafts/{draft['id']}/send")
    assert blocked.status_code == 409

    approved = await client.post(f"/drafts/{draft['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    sent = await client.post(f"/drafts/{draft['id']}/send")
    assert sent.status_code == 200
    assert sent.json()["draft"]["status"] == "sent"
    assert sent.json()["delivery"]["mode"] == "mock"


async def test_rejected_draft_cannot_send(
    client: AsyncClient, contact_payload: dict[str, str], mock_scrape: None
) -> None:
    contact_id, _ = await _create_researched_contact(client, contact_payload)
    draft_id = (await client.post(f"/contacts/{contact_id}/draft")).json()["id"]
    rejected = await client.post(f"/drafts/{draft_id}/reject")
    assert rejected.json()["status"] == "rejected"
    response = await client.post(f"/drafts/{draft_id}/send")
    assert response.status_code == 409
    assert response.json()["detail"] == "Only an approved draft can be sent"


async def test_webhook_payload_validation(client: AsyncClient) -> None:
    response = await client.post(
        "/webhooks/outreach",
        json={"first_name": "Sarah", "email": "not-an-email"},
    )
    assert response.status_code == 422


async def test_webhook_safe_default(client: AsyncClient, contact_payload: dict[str, str]) -> None:
    response = await client.post("/webhooks/outreach", json=contact_payload)
    assert response.status_code == 201
    body = response.json()
    assert body["research"] is None
    assert body["draft"] is None
    assert body["next_action"] == "POST /contacts/1/research"
