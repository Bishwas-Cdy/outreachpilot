# OutreachPilot implementation plan

- [x] Create project configuration, environment settings, database session, and application lifecycle.
- [x] Define SQLAlchemy models and Pydantic request/response schemas.
- [x] Implement URL safety, bounded website scraping, deterministic extraction, and research orchestration.
- [x] Implement OpenAI-compatible LLM abstraction with safe deterministic fallbacks.
- [x] Implement evidence-grounded pain hypotheses and personalized draft generation.
- [x] Enforce human approval state transitions and approved-only delivery.
- [x] Add mock delivery and validated outbound webhook delivery.
- [x] Implement contacts, research, draft, approval, send, webhook, and health APIs.
- [x] Add representative example leads and n8n workflow JSON.
- [x] Write README, architecture, n8n, and interview-demo documentation.
- [x] Add API, workflow, SSRF, validation, and anti-fabrication tests.
- [x] Run pytest, Ruff, Ruff format check, and strict mypy; fix all findings.
