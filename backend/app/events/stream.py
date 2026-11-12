"""Bounded polling of committed evidence; never owns or schedules execution."""
from collections.abc import AsyncIterator, Awaitable, Callable
import json
from time import monotonic
import anyio
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import Settings
from app.core.domain_errors import ServiceError
from app.events.public import monitoring_secrets, public_event
from app.events.store import sanitize
from app.execution.service import recover_expired
from app.models.assessment import Assessment, RunEvent
from app.schemas.assessments import AssessmentRead

TERMINAL_STATES = frozenset({"completed", "failed", "cancelled", "inconclusive"})
BATCH_SIZE = 100
MAX_FRAME_BYTES = 262144


def frame(kind: str, data: dict, event_id: str | None = None) -> str:
    content = json.dumps(data, separators=(",", ":"), ensure_ascii=True)
    result = (f"id: {event_id}\n" if event_id else "") + f"event: {kind}\ndata: {content}\n\n"
    if len(result.encode("utf-8")) > MAX_FRAME_BYTES:
        raise ServiceError(503, "monitor_event_too_large", "A persisted event exceeds the monitoring frame limit.")
    return result


class StreamLease:
    def __init__(self, owner: "AssessmentStreams") -> None:
        self.owner = owner
        self.closed = False

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self.owner.active -= 1


class AssessmentStreams:
    def __init__(self, factory: sessionmaker[Session], settings: Settings) -> None:
        self.factory = factory
        self.settings = settings
        self.active = 0
        self.poll_seconds = settings.monitor_poll_seconds
        self.heartbeat_seconds = settings.monitor_heartbeat_seconds

    def reserve(self) -> StreamLease:
        # Called on the event loop without an await between admission and reservation.
        if self.active >= self.settings.monitor_max_streams:
            raise ServiceError(503, "monitor_capacity_reached", "Monitoring capacity is busy. Reconnect later.")
        self.active += 1
        return StreamLease(self)

    def cursor(self, run_id: str, after: int, last_event_id: str | None) -> int:
        with self.factory() as session:
            run = session.get(Assessment, run_id)
            if run is None:
                raise ServiceError(404, "assessment_not_found", "Assessment not found.")
            if last_event_id:
                if len(last_event_id) > 128:
                    raise ServiceError(422, "invalid_event_cursor", "The event cursor does not belong to this assessment.")
                sequence = session.scalar(select(RunEvent.sequence).where(RunEvent.run_id == run_id, RunEvent.id == last_event_id))
                if sequence is None:
                    raise ServiceError(422, "invalid_event_cursor", "The event cursor does not belong to this assessment.")
                return sequence
            if after > run.event_sequence:
                raise ServiceError(422, "invalid_event_cursor", "The event cursor is ahead of persisted assessment history.")
            return after

    def read(self, run_id: str, after: int) -> tuple[dict, list[dict]]:
        # Reuse existing recovery authority, scoped to this run. Never replay POSTs.
        recover_expired(self.factory, run_id=run_id)
        with self.factory() as session:
            run = session.get(Assessment, run_id)
            if run is None:
                raise ServiceError(404, "assessment_not_found", "Assessment not found.")
            snapshot = sanitize(AssessmentRead.model_validate(run).model_dump(mode="json"), monitoring_secrets(self.settings))
            rows = session.scalars(select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.sequence > after,
                        RunEvent.sequence <= run.event_sequence).order_by(RunEvent.sequence).limit(BATCH_SIZE)).all()
            events = [public_event(row, self.settings).model_dump(mode="json") for row in rows]
        # Session/transaction is closed before any yield, sleep or response backpressure.
        return snapshot, events

    async def iterate(self, run_id: str, after: int, disconnected: Callable[[], Awaitable[bool]], lease: StreamLease) -> AsyncIterator[str]:
        cursor = after
        previous_snapshot = None
        heartbeat_at = monotonic()
        try:
            yield "retry: 1000\n\n"
            while not await disconnected():
                snapshot, events = await anyio.to_thread.run_sync(lambda: self.read(run_id, cursor), abandon_on_cancel=True)
                if snapshot != previous_snapshot:
                    yield frame("snapshot", {"run": snapshot})
                    previous_snapshot = snapshot
                if not events and cursor < snapshot["event_sequence"]:
                    raise ServiceError(503, "event_history_gap", "Persisted event history is not contiguous.")
                for event in events:
                    if event["sequence"] != cursor + 1:
                        raise ServiceError(503, "event_history_gap", "Persisted event history is not contiguous.")
                    if await disconnected():
                        return
                    yield frame("assessment_event", event, event["id"])
                    cursor = event["sequence"]
                if snapshot["status"] in TERMINAL_STATES and cursor >= snapshot["event_sequence"]:
                    yield frame("settled", {"run_id": run_id, "status": snapshot["status"], "last_sequence": cursor})
                    return
                if monotonic() - heartbeat_at >= self.heartbeat_seconds:
                    yield ": heartbeat\n\n"
                    heartbeat_at = monotonic()
                if len(events) < BATCH_SIZE:
                    await anyio.sleep(self.poll_seconds)
        except ServiceError as exc:
            yield frame("stream_error", {"code": exc.code, "message": "Monitoring stopped safely. Reconnect or inspect persisted history."})
        except SQLAlchemyError:
            yield frame("stream_error", {"code": "event_store_unavailable", "message": "Event storage is temporarily unavailable. Reconnect later."})
        finally:
            lease.close()
