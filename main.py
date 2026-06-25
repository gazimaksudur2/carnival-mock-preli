"""FastAPI server exposing the rule-based ticket classifier.

Endpoints:
  GET  /health        -> liveness probe
  POST /sort-ticket   -> classify a support ticket

Run locally:
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from classifier import classify

app = FastAPI(
    title="Ticket Classifier",
    version="1.0.0",
    description="Rule-based finance support ticket classifier.",
)


class Ticket(BaseModel):
    ticket_id: str = Field(..., description="Unique ticket identifier")
    message: str = Field(..., description="Free-text customer message")
    channel: Optional[str] = Field(None, description="e.g. email, sms, in-app")
    locale: Optional[str] = Field(None, description="e.g. en-US, bn-BD")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ticket-classifier"}


@app.post("/sort-ticket")
def sort_ticket(ticket: Ticket) -> dict:
    result = classify(ticket.message)
    return {"ticket_id": ticket.ticket_id, **result}
