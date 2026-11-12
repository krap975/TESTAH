"""Append evidence inside the same locked transaction as its state change."""
import re
from collections.abc import Iterable
from sqlalchemy.orm import Session
from app.models.assessment import Assessment, RunEvent


def sanitize(value: object, secrets: Iterable[str] = ()) -> object:
    if isinstance(value, dict):
        return {str(key): ("[redacted]" if any(word in str(key).lower() for word in
                ("secret", "authorization", "credential", "password", "endpoint", "header")) else sanitize(item, secrets))
                for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize(item, secrets) for item in value]
    if isinstance(value, str):
        for secret in sorted((s for s in secrets if s), key=len, reverse=True):
            value = value.replace(secret, "[redacted]")
        value = re.sub(r"https?://[^\s\"<>]+", "[url redacted]", value)
        value = re.sub(r"(?i)(authorization|x-api-key|bearer|password|secret)\s*[:= ]\s*[^\s,;]+", r"\1 [redacted]", value)
        return value[:16000]
    return value


def append_event(session: Session, run: Assessment, event_type: str, payload: dict,
                 secrets: Iterable[str] = (), correlation_id: str | None = None) -> None:
    run.event_sequence += 1
    session.add(RunEvent(run_id=run.id, sequence=run.event_sequence, event_type=event_type,
                         payload=sanitize(payload, secrets), correlation_id=sanitize(correlation_id, secrets)))
    if event_type == "assessment.finished" or (event_type.startswith("payment.") and run.status in {"completed", "failed", "cancelled", "inconclusive"}):
        from app.evaluation.service import enqueue
        enqueue(session, run)
