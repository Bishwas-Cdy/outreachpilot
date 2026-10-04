# 2–3 minute interview demo

## Before the interview

Run `uvicorn app.main:app --reload` and open `http://localhost:8000/docs`. Keep `DELIVERY_MODE=mock` and `LLM_API_KEY` empty to demonstrate the fully local deterministic path. Choose a public company website that permits this use.

## Script

**0:00–0:30 — Frame the problem**

“OutreachPilot automates repetitive account research and first-draft writing without turning into a spam sender. Website evidence stays attached to each signal, inferred pains are labeled as hypotheses, and a human approval gate is mandatory.”

Show `GET /health`, noting mock delivery and whether an LLM is configured.

**0:30–1:15 — Create and research**

Use `POST /contacts` with a lead from `examples/leads.json`, then call `POST /contacts/{id}/research`. Point out:

- evidence excerpts and source URLs;
- confidence values;
- business model and target market classifications;
- “Hypothesis:” wording rather than factual claims.

**1:15–1:50 — Draft and safety control**

Call `POST /contacts/{id}/draft`. Read the concise message and show its `awaiting_approval` status. Immediately call `POST /drafts/{id}/send`; the expected HTTP 409 proves the rule is enforced server-side.

**1:50–2:20 — Human decision and delivery**

Call `POST /drafts/{id}/approve`, then `/send`. Show `sent_at` and the response stating that mock mode contacted no email provider. Mention that rejecting instead is terminal and also blocks sending.

**2:20–2:50 — Automation fit**

Open `docs/N8N_WORKFLOW.md` or the n8n JSON. Explain that n8n can ingest a CRM/webhook lead and orchestrate research and review, while it cannot bypass the API’s approval check. In webhook delivery mode, only an approved payload is forwarded to a validated public HTTPS endpoint.

## Useful follow-up points

- Why deterministic fallback? The demo remains reliable without paid services and provides a safe failure mode.
- Why not crawl broadly? A bounded set of public pages is easier to reason about, faster, and more respectful.
- What would production need? Auth/RBAC, audit events, rate limits, background jobs, robots handling, stronger DNS-rebinding protection, and CRM idempotency.

