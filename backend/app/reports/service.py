"""Read-only projections. No execution, provider, gateway or scoring-job operations."""
from datetime import datetime, timezone
import json
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.config import Settings
from app.core.domain_errors import ServiceError
from app.events.public import monitoring_secrets, public_event
from app.events.store import sanitize
from app.evaluation.service import public_result, read_evaluation
from app.models.assessment import Assessment, RunEvent
from app.models.evaluation import Evaluation, EvaluationJob, ScoringBinding
from app.schemas.assessments import AssessmentRead, EventRead
from app.schemas.evaluation import EvaluationRead, EvaluationResultRead
from app.schemas.reports import ReportRead, ReportEventsRead, ReportExportRead, ReportListRead, PaymentEvidenceRead, RecoveryRead
from app.reports.recommendations import VERSION, recommendations

SCHEMA_VERSION = "testah-report-v1.0.0"
MAX_EVENTS = 5000
MAX_EXPORT_BYTES = 10 * 1024 * 1024


def report_event(row: RunEvent, settings: Settings) -> EventRead:
    """Defense in depth for report downloads, without modifying stored evidence."""
    result = public_event(row, settings)
    private_keys = {"input_json", "agent_config", "blueprint_json", "runtime_json", "provider_response",
        "callback_hash", "approval_url", "client_binding", "create_key", "capture_key", "private_prompt",
        "trigger", "state_change", "expected_behavior"}
    def redact(value: object) -> object:
        if isinstance(value, dict):
            return {key: "[redacted]" if key.lower() in private_keys or "token" in key.lower() else redact(item)
                    for key, item in value.items()}
        if isinstance(value, list):
            return [redact(item) for item in value]
        return value
    result.payload = redact(result.payload)
    return result


def select_report(session: Session, run_id: str, evaluation_id: str | None, settings: Settings) -> tuple[Assessment, EvaluationRead, bool, str | None]:
    run = session.get(Assessment, run_id)
    if run is None:
        raise ServiceError(404, "assessment_not_found", "Assessment not found.")
    state = EvaluationRead.model_validate(read_evaluation(session, run))
    latest_id = state.result.id if state.result else None
    if evaluation_id:
        row = session.scalar(select(Evaluation).where(Evaluation.id == evaluation_id, Evaluation.run_id == run_id))
        if row is None:
            raise ServiceError(404, "evaluation_not_found", "Evaluation not found for this assessment.")
        result = EvaluationResultRead.model_validate(public_result(row))
        state = EvaluationRead(status=result.status, result=result, stale=result.cutoff_sequence < run.event_sequence)
    # Apply the same configured-secret redaction to public metadata and explanations.
    state = EvaluationRead.model_validate(sanitize(state.model_dump(), monitoring_secrets(settings)))
    return run, state, state.result is None or state.result.id == latest_id, latest_id


def evidence(session: Session, run_id: str, cutoff: int, settings: Settings) -> list[EventRead]:
    rows = session.scalars(select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.sequence <= cutoff)
        .order_by(RunEvent.sequence).limit(MAX_EVENTS + 1)).all()
    if len(rows) > MAX_EVENTS:
        raise ServiceError(409, "report_history_limit", "This history exceeds the report limit of 5000 events.")
    return [report_event(row, settings) for row in rows]


def payment_evidence(events: list[EventRead]) -> list[PaymentEvidenceRead]:
    grouped: dict[str, dict] = {}
    for event in events:
        data = event.payload
        if event.event_type == "tool.completed" and data.get("name") == "get_payment_status":
            data = data.get("result", {})
        elif not event.event_type.startswith(("payment.", "checkout.")):
            continue
        if not isinstance(data, dict):
            continue
        key = data.get("checkout_id")
        if not isinstance(key, str):
            continue
        row = grouped.setdefault(key, {"checkout_id": key, "provider": None, "status": None, "total_minor": None,
            "currency": None, "order_id": None, "capture_id": None, "event_ids": [], "captured_event_ids": [], "inspection_event_ids": [],
            "authorization_event_ids": [], "buyer_approval_event_ids": []})
        for field in ("provider", "status", "currency", "order_id", "capture_id"):
            if isinstance(data.get(field), str):
                row[field] = data[field]
        if type(data.get("total_minor")) is int:
            row["total_minor"] = data["total_minor"]
        row["event_ids"].append(event.id)
        if event.event_type == "payment.authorization_verified":
            row["authorization_event_ids"].append(event.id)
        if event.event_type == "payment.buyer_approved":
            row["buyer_approval_event_ids"].append(event.id)
        if event.event_type == "payment.captured":
            row["captured_event_ids"].append(event.id)
        if event.event_type == "tool.completed":
            row["inspection_event_ids"].append(event.id)
    return [PaymentEvidenceRead.model_validate(row) for row in grouped.values()]


def assemble_report(session: Session, run_id: str, evaluation_id: str | None, settings: Settings) -> tuple[ReportRead, list[EventRead]]:
    run, state, latest, latest_id = select_report(session, run_id, evaluation_id, settings)
    result = state.result
    cutoff = result.cutoff_sequence if result else 0
    events = evidence(session, run_id, cutoff, settings)
    ids = {event.id for event in events}
    refs = set()
    if result:
        refs = {ref for item in [*result.findings, *result.dimensions] for ref in item.event_ids}
    missing = sorted(refs - ids)
    complete = bool(result) and [e.sequence for e in events] == list(range(1, cutoff + 1)) and not missing
    metadata = AssessmentRead.model_validate(run).model_dump(mode="json")
    metadata["evaluation"] = None  # Selected evaluation lives in one explicit place.
    report = ReportRead(schema_version=SCHEMA_VERSION, recommendations_version=VERSION,
        assessment=AssessmentRead.model_validate(sanitize(metadata, monitoring_secrets(settings))),
        evaluation=state, is_latest_evaluation=latest, latest_evaluation_id=latest_id, cutoff_sequence=cutoff,
        evidence_total=len(events), evidence_complete=complete, missing_event_ids=missing,
        recommendations=recommendations(result), payments=payment_evidence(events),
        recovery=[RecoveryRead(status=f.status, points=f.points, explanation=f.explanation, event_ids=f.event_ids)
                  for f in result.findings if f.rule_id == "recovery_episode"] if result else [])
    return report, events


def report_events(session: Session, run_id: str, evaluation_id: str | None, after: int, limit: int, settings: Settings) -> ReportEventsRead:
    run, state, _, _ = select_report(session, run_id, evaluation_id, settings)
    cutoff = state.result.cutoff_sequence if state.result else 0
    rows = session.scalars(select(RunEvent).where(RunEvent.run_id == run.id, RunEvent.sequence <= cutoff,
        RunEvent.sequence > after).order_by(RunEvent.sequence).limit(limit + 1)).all()
    total = session.scalar(select(func.count()).select_from(RunEvent).where(RunEvent.run_id == run_id, RunEvent.sequence <= cutoff))
    return ReportEventsRead(evaluation_id=state.result.id if state.result else None, cutoff_sequence=cutoff,
        events=[report_event(row, settings) for row in rows[:limit]], total=total,
        next_after_sequence=rows[limit - 1].sequence if len(rows) > limit else None)


def export_report(session: Session, run_id: str, evaluation_id: str | None, settings: Settings) -> bytes:
    report, events = assemble_report(session, run_id, evaluation_id, settings)
    if report.evaluation.result is None:
        raise ServiceError(409, "report_not_evaluated", "No persisted evaluation is available to export.")
    # A partial evaluation is exportable; missing history is not silently truncated.
    if not report.evidence_complete:
        raise ServiceError(409, "report_evidence_incomplete", "The complete evidence for this evaluation is unavailable.")
    output = ReportExportRead(**report.model_dump(), evidence=events, exported_at=datetime.now(timezone.utc).isoformat())
    payload = json.dumps(output.model_dump(mode="json"), ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    if len(payload) > MAX_EXPORT_BYTES:
        raise ServiceError(409, "report_export_limit", "The report exceeds the 10 MiB download limit.")
    return payload


def list_reports(session: Session, offset: int, limit: int, settings: Settings) -> ReportListRead:
    runs = session.scalars(select(Assessment).order_by(Assessment.created_at.desc(), Assessment.id).offset(offset).limit(limit)).all()
    ids = [r.id for r in runs]
    ranked = select(Evaluation.id, func.row_number().over(partition_by=Evaluation.run_id,
        order_by=(Evaluation.cutoff_sequence.desc(), Evaluation.created_at.desc(), Evaluation.id.desc())).label("position")).where(Evaluation.run_id.in_(ids)).subquery()
    rows = session.scalars(select(Evaluation).join(ranked, ranked.c.id == Evaluation.id).where(ranked.c.position == 1)).all()
    latest = {e.run_id: EvaluationResultRead.model_validate(public_result(e)) for e in rows}
    jobs = {j.run_id: j.status for j in session.scalars(select(EvaluationJob).where(EvaluationJob.run_id.in_(ids)))}
    bindings = set(session.scalars(select(ScoringBinding.run_id).where(ScoringBinding.run_id.in_(ids))))
    items = []
    for run in runs:
        result = latest.get(run.id)
        status = "pending" if jobs.get(run.id) == "pending" else "error" if jobs.get(run.id) == "failed" else result.status if result else "pending" if run.id in bindings else "not_requested"
        items.append({"run_id": run.id, "agent_name": run.agent_name, "environment_name": run.environment_name,
            "status": run.status, "payment_mode": run.payment_mode,
            "created_at": (run.created_at if run.created_at.tzinfo else run.created_at.replace(tzinfo=timezone.utc)).isoformat(),
            "evaluation_id": result.id if result else None, "evaluation_status": status,
            "overall_score": result.overall_score if result else None, "certification": result.certification.decision if result else None,
            "rubric": result.version if result else None, "stale": bool(result and result.cutoff_sequence < run.event_sequence)})
    return ReportListRead(items=sanitize(items, monitoring_secrets(settings)),
        total=session.scalar(select(func.count()).select_from(Assessment)), offset=offset, limit=limit)
