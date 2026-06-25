# Ticket Classifier (Rule-Based)

A small FastAPI service that classifies finance support messages into one of
five categories using a pure keyword-scoring approach. No ML, no external API —
fully deterministic, fast, and free.

## Categories

| case_type                          | severity | department            |
|------------------------------------|----------|-----------------------|
| `wrong_transfer`                   | high     | dispute_resolution    |
| `payment_failed`                   | high     | payments_ops          |
| `phishing_or_social_engineering`   | critical | fraud_risk            |
| `refund_request`                   | low      | customer_support      |
| `other`                            | low      | customer_support      |

Severity is bumped up one level (`low → medium → high → critical`) when any
urgency word appears (`urgent`, `immediately`, `emergency`, `all my money`,
Bengali `জরুরি`, etc.) — unless it's already `critical`.

The `agent_summary` is always taken from a fixed template; the raw user
message is never echoed back, so PIN/OTP/password tokens can't leak.

## Project layout

```
.
├── classifier.py     # keyword patterns, scoring, severity, safe summaries
├── main.py           # FastAPI app: GET /health, POST /sort-ticket
├── test_api.py       # pytest cases for the 5 spec samples + edge cases
├── requirements.txt
├── .env.example
└── .gitignore
```

## Setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Run the API

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive docs: <http://localhost:8000/docs>

## API

### `GET /health`

```json
{ "status": "ok", "service": "ticket-classifier" }
```

### `POST /sort-ticket`

Request:

```json
{
  "ticket_id": "T-1001",
  "message": "Payment failed but balance deducted",
  "channel": "in-app",
  "locale": "en-US"
}
```

Response:

```json
{
  "ticket_id": "T-1001",
  "case_type": "payment_failed",
  "severity": "high",
  "department": "payments_ops",
  "agent_summary": "Customer reports a failed transaction and is concerned their balance may have been affected.",
  "human_review_required": false,
  "confidence": 0.65
}
```

### curl example

```bash
curl -X POST http://localhost:8000/sort-ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket_id":"T-1001","message":"Someone called asking my OTP"}'
```

## Tests

```bash
pytest -v
```

## Deploy

Any host that runs Python + uvicorn works. For free HTTPS:

- **Railway** — `npm i -g @railway/cli && railway init && railway up`
- **Render** — connect the repo, it auto-builds and gives a `https://…onrender.com` URL.

Set `PORT` in the environment; uvicorn reads it automatically.