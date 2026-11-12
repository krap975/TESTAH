"""Transactional score persistence. No execution transitions or financial operations."""
import asyncio
from copy import deepcopy
import logging
from pathlib import Path
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker
from app.core.domain_errors import ServiceError
from app.evaluation.registry import EVALUATORS, POLICIES
from app.evaluation.rubric import VERSION, digest, policy
from app.models.assessment import Assessment, RunEvent
from app.models.evaluation import Evaluation, EvaluationJob, ScoringBinding
from app.models.payment import Payment
from app.schemas.environments import Blueprint

TERMINAL = {"completed", "failed", "cancelled", "inconclusive"}
MAX_ATTEMPTS = 3
MAX_EVENTS = 5000
# Implementation identity supplements the immutable semantic rubric version.
ENGINE_HASH = digest({name: Path(__file__).with_name(name).read_text(encoding="utf-8")
                      for name in ("commerce.py", "rubric.py", "registry.py", "service.py")})


def bind(session: Session, run: Assessment, assignment: str = "before_execution") -> None:
    snapshot = deepcopy(policy())
    session.add(ScoringBinding(run_id=run.id, version=VERSION, policy_json=snapshot,
                              policy_hash=digest(snapshot), assignment=assignment))


def enqueue(session: Session, run: Assessment, retry: bool = False) -> None:
    """Called inside the existing event transaction; never changes execution evidence."""
    if run.status not in TERMINAL or session.get(ScoringBinding, run.id) is None:
        return
    job = session.get(EvaluationJob, run.id)
    if job is None:
        session.add(EvaluationJob(run_id=run.id, requested_sequence=run.event_sequence,
                                 completed_sequence=0, attempts=0, status="pending"))
    elif run.event_sequence > job.requested_sequence or retry:
        job.requested_sequence = run.event_sequence
        job.attempts = 0
        job.status = "pending"


# Only typed financial/protocol facts enter the frozen scoring input. Text, URLs,
# credentials, private prompts and candidate summaries cannot influence a score.
FACT_KEYS = frozenset({"name", "arguments", "result", "merchant", "products", "id", "synthetic",
    "verified", "supports_checkout", "shipping_fee_minor", "currency", "merchant_id", "available",
    "price_minor", "items", "product_id", "quantity", "total_minor", "cart_version", "unit_prices",
    "approval_id", "status", "checkout_id", "payment_id", "provider", "payment_mode", "order_id", "capture_id",
    "kind", "code", "reason", "origin", "budget_minor", "remaining_minor", "purchases", "from", "to"})


def facts(value: object, key: str = "") -> object:
    if isinstance(value, dict):
        if key == "unit_prices":
            return deepcopy(value)
        return {k: facts(v, k) for k, v in value.items() if k in FACT_KEYS}
    if isinstance(value, list):
        return [facts(v) for v in value]
    return value


def snapshot(session: Session, run: Assessment, binding: ScoringBinding) -> dict:
    bp = Blueprint.model_validate(run.blueprint_json).model_dump(mode="json")
    rows = session.scalars(select(RunEvent).where(RunEvent.run_id == run.id,
        RunEvent.sequence <= run.event_sequence).order_by(RunEvent.sequence).limit(MAX_EVENTS + 1)).all()
    if len(rows) > MAX_EVENTS:
        raise ServiceError(409, "evaluation_history_limit", "This history exceeds the scoring limit.")
    events = [{"id": e.id, "run_id": e.run_id, "sequence": e.sequence, "event_type": e.event_type,
               "correlation_id": e.correlation_id, "payload": facts(e.payload)} for e in rows]
    # Use the same fact projection for historical merchant observations and blueprint.
    bp["merchants"] = [facts(m) for m in bp["merchants"]]
    bp["products"] = [facts(p) for p in bp["products"]]
    payments = [{"id": p.id, "run_id": p.run_id, "approval_id": p.approval_id,
        "cart": facts(p.cart), "amount_minor": p.amount_minor, "currency": p.currency,
        "status": p.status, "order_id": p.order_id, "capture_id": p.capture_id, "captured": p.captured_at is not None}
        for p in session.scalars(select(Payment).where(Payment.run_id == run.id).order_by(Payment.id))]
    return {"run": {k: getattr(run, k) for k in ("id", "status", "termination_reason", "failure_origin",
                "event_sequence", "payment_mode", "protocol_version")},
        "blueprint": {k: bp[k] for k in ("blueprint_version", "template_id", "template_version", "currency", "budget_minor",
                                          "products", "merchants", "policies", "challenges")},
        "runtime": {k: run.runtime_json.get(k) for k in ("purchases", "spent_minor", "payment_inspected", "http_requests")},
        "events": events, "payments": payments, "policy": binding.policy_json,
        "policy_hash": binding.policy_hash, "assignment": binding.assignment, "engine_hash": ENGINE_HASH}


def process_one(factory: sessionmaker[Session], run_id: str) -> None:
    # UPDATE first serializes scoring requests across processes. The pure bounded
    # calculation and insert share one short transaction; no external await occurs.
    with factory() as session, session.begin():
        claimed = session.execute(update(EvaluationJob).where(EvaluationJob.run_id == run_id,
            EvaluationJob.status == "pending", EvaluationJob.attempts < MAX_ATTEMPTS)
            .values(attempts=EvaluationJob.attempts + 1))
        if claimed.rowcount != 1:
            return
        job = session.get(EvaluationJob, run_id)
        try:
            run = session.get(Assessment, run_id)
            binding = session.get(ScoringBinding, run_id)
            if (run.status not in TERMINAL or binding.version not in EVALUATORS
                or binding.policy_hash != digest(binding.policy_json) or binding.policy_json != POLICIES[binding.version]()):
                raise ValueError("Unsupported or altered scoring policy")
            inputs = snapshot(session, run, binding)
            checksum = digest(inputs)
            existing = session.scalar(select(Evaluation.id).where(Evaluation.run_id == run.id,
                Evaluation.version == binding.version, Evaluation.input_digest == checksum))
            if existing is None:
                result = EVALUATORS[binding.version](inputs)
                session.add(Evaluation(run_id=run.id, version=binding.version, input_digest=checksum,
                    cutoff_sequence=run.event_sequence, input_json=inputs, result_json=result))
            job.completed_sequence = job.requested_sequence = run.event_sequence
            job.status = "complete"
        except (ValueError, KeyError, TypeError, ServiceError):
            # No exception text, provider content, prompts or input values escape.
            if job.attempts >= MAX_ATTEMPTS:
                job.status = "failed"


def request_evaluation(factory: sessionmaker[Session], run_id: str) -> dict:
    # A harmless row lock with no revision/state changes; same writer serialization
    # boundary as execution. This is an explicit management mutation, never a GET.
    with factory() as session, session.begin():
        found = session.execute(update(Assessment).where(Assessment.id == run_id).values(id=Assessment.id))
        if found.rowcount != 1:
            raise ServiceError(404, "assessment_not_found", "Assessment not found.")
        run = session.get(Assessment, run_id)
        if run.status not in TERMINAL:
            raise ServiceError(409, "assessment_not_terminal", "Scoring requires a terminal assessment.")
        if session.get(ScoringBinding, run_id) is None:
            bind(session, run, "retrospective")
            session.flush()
        enqueue(session, run, retry=True)
    with factory() as session:
        return read_evaluation(session, session.get(Assessment, run_id))


def public_result(row: Evaluation) -> dict:
    return {"id": row.id, "run_id": row.run_id, "cutoff_sequence": row.cutoff_sequence,
            "input_digest": row.input_digest, "created_at": row.created_at.isoformat(), **row.result_json,
            "assignment": row.input_json["assignment"], "policy_hash": row.input_json["policy_hash"],
            "engine_hash": row.input_json.get("engine_hash", "development-before-final-verification")}


def read_evaluation(session: Session, run: Assessment) -> dict:
    binding = session.get(ScoringBinding, run.id)
    if binding is None:
        return {"status": "not_requested", "result": None, "stale": False}
    job = session.get(EvaluationJob, run.id)
    latest = session.scalar(select(Evaluation).where(Evaluation.run_id == run.id)
                            .order_by(Evaluation.cutoff_sequence.desc(), Evaluation.created_at.desc()).limit(1))
    stale = bool(latest and latest.cutoff_sequence < run.event_sequence)
    status = "pending" if job and job.status == "pending" else "error" if job and job.status == "failed" else (
        latest.result_json["status"] if latest else "pending")
    return {"status": status, "result": public_result(latest) if latest else None, "stale": stale}


class EvaluationWorker:
    """Bounded polling of durable requests; interrupted transactions can be retried."""
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self.factory = factory
        self.task: asyncio.Task | None = None

    def start(self) -> None:
        self.task = asyncio.create_task(self.loop())

    def pump(self) -> None:
        with self.factory() as session:
            ids = session.scalars(select(EvaluationJob.run_id).where(EvaluationJob.status == "pending",
                EvaluationJob.attempts < MAX_ATTEMPTS).order_by(EvaluationJob.run_id).limit(16)).all()
        for run_id in ids:
            process_one(self.factory, run_id)

    async def loop(self) -> None:
        import anyio
        from sqlalchemy.exc import SQLAlchemyError
        while True:
            try:
                await anyio.to_thread.run_sync(self.pump)
            except SQLAlchemyError:
                logging.getLogger(__name__).warning("Evaluation storage unavailable; pending work is retained.")
            await asyncio.sleep(1)

    async def close(self) -> None:
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
