# n8n workflow integration

OutreachPilot can sit behind an n8n Webhook Trigger or be called from any CRM workflow. The API does not depend on n8n.

Set an n8n environment variable such as `OUTREACHPILOT_BASE_URL=http://host.docker.internal:8000` (adjust for your network). JSON responses are directly consumable by later nodes.

## Recommended workflow

```text
Webhook Trigger
  → HTTP Request: create OutreachPilot contact
  → HTTP Request: research contact
  → HTTP Request: create draft
  → Slack/Form/Wait node: human review
  → IF approved?
      yes → HTTP Request: approve → HTTP Request: send
      no  → HTTP Request: reject
```

Keep the approval decision outside the model and pass it into the IF node from a trusted human action.

## Exact requests

### 1. Ingest a lead

HTTP Request node:

- Method: `POST`
- URL: `{{$env.OUTREACHPILOT_BASE_URL}}/webhooks/outreach`
- Send Body: JSON
- Body:

```json
{
  "first_name": "{{$json.first_name}}",
  "last_name": "{{$json.last_name}}",
  "email": "{{$json.email}}",
  "role": "{{$json.role}}",
  "company_name": "{{$json.company_name}}",
  "company_website": "{{$json.company_website}}"
}
```

With the default `WEBHOOK_AUTO_PROCESS=false`, the response includes `contact.id` and a `next_action`. Store `{{$json.contact.id}}` in later expressions.

### 2. Research

- Method: `POST`
- URL: `{{$env.OUTREACHPILOT_BASE_URL}}/contacts/{{$json.contact.id}}/research`
- Body: none

The response contains `research.detected_signals` and `hypotheses`. Present both alongside the draft during review.

### 3. Generate draft

- Method: `POST`
- URL: `{{$env.OUTREACHPILOT_BASE_URL}}/contacts/{{$('Ingest lead').item.json.contact.id}}/draft`
- Body: none

Save the returned `id` as the draft ID. Its status is `awaiting_approval`.

### 4. Human review

Use an n8n Form, Slack interactive step, or Wait node. Display subject, body, evidence, and hypothesis. Produce a boolean field named `approved`. The included example workflow uses a Set node as a visible placeholder; it defaults to `false` so importing it cannot approve outreach accidentally.

### 5a. Approved branch

First mark the reviewed draft approved:

- Method: `POST`
- URL: `{{$env.OUTREACHPILOT_BASE_URL}}/drafts/{{$('Generate draft').item.json.id}}/approve`

Then deliver it:

- Method: `POST`
- URL: `{{$env.OUTREACHPILOT_BASE_URL}}/drafts/{{$('Generate draft').item.json.id}}/send`

In default mock mode, this records the send without contacting an email system. With `DELIVERY_MODE=webhook`, the same call posts the approved message to `OUTBOUND_WEBHOOK_URL`.

### 5b. Rejected branch

- Method: `POST`
- URL: `{{$env.OUTREACHPILOT_BASE_URL}}/drafts/{{$('Generate draft').item.json.id}}/reject`

A rejected draft cannot subsequently be sent.

## Safe one-call preprocessing

Setting `WEBHOOK_AUTO_PROCESS=true` and sending `"trigger_processing": true` can combine contact creation, research, and draft generation. The response still stops at `awaiting_approval`; the flag never approves or sends.

## Importable example

Import `examples/outreachpilot-n8n-workflow.json`, configure the base URL environment variable, and replace the “Human approval placeholder” Set node with your actual human review mechanism before activation.

