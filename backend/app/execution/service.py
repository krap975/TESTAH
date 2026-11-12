"""Central transitions, database claims, fencing, and transaction boundaries."""
from contextlib import contextmanager
from collections.abc import Iterator
from copy import deepcopy
from datetime import timedelta, timezone
from uuid import uuid4
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.attributes import flag_modified
from app.agents.service import find_agent
from app.core.config import Settings
from app.core.domain_errors import ServiceError
from app.environments.runtime import initial_state
from app.environments.service import find_environment, load_blueprint
from app.events.store import append_event
from app.models.agent import Agent, utcnow
from app.models.assessment import Assessment
from app.schemas.assessments import AssessmentCreate
from app.models.rai import RaiProposal, RaiProposalEvent
from app.rai.provider import provider_config, provider_metadata, secret_values

TRANSITIONS = {"created": {"running", "cancelled"},
               "running": {"completed", "failed", "cancelled", "inconclusive"},
               "completed": set(), "failed": set(), "cancelled": set(), "inconclusive": set()}


class LeaseLost(Exception):
    pass


def transition(session: Session, run: Assessment, status: str, reason: str | None = None,
               origin: str | None = None) -> None:
    if status not in TRANSITIONS[run.status]:
        raise ServiceError(409, "invalid_run_transition", "This assessment cannot make the requested state transition.")
    previous = run.status
    run.status = status
    if status == "running":
        run.started_at = utcnow()
    else:
        run.ended_at = utcnow()
        run.termination_reason = reason
        run.failure_origin = origin
        run.lease_token = None
        run.lease_expires_at = None
    append_event(session, run, "assessment.state_changed", {"from": previous, "to": status, "reason": reason, "origin": origin})
    if status != "running":
        append_event(session, run, "assessment.finished", {"status": status, "reason": reason, "origin": origin})


def agent_configuration(agent: Agent) -> dict:
    return {key: getattr(agent, key) for key in ("endpoint_url", "connection_mode", "auth_header_name", "auth_secret_key")}


def create_assessment(session: Session, data: AssessmentCreate, settings: Settings) -> Assessment:
    try:
        if settings.payment_mode == "paypal_sandbox":
            from app.payments.paypal import configured
            if not configured(settings):
                raise ServiceError(503, "paypal_not_configured", "Configure PayPal Sandbox credentials, merchant and operator access before creating a Sandbox assessment.")
        agent = find_agent(session, data.agent_id)
        if agent.last_test_status != "connected":
            raise ServiceError(409, "agent_not_connected", "Test the agent protocol connection before creating an assessment.")
        environment = find_environment(session, data.environment_id)
        blueprint = load_blueprint(environment)
        limits = {name.removeprefix("execution_"): getattr(settings, name) for name in type(settings).model_fields if name.startswith("execution_")}
        if settings.payment_mode == "paypal_sandbox":
            limits["approval_wait_seconds"] = settings.paypal_approval_wait_seconds
        config = provider_config(settings) if data.examiner_mode == "rai" else {}
        metadata = provider_metadata(config) if config else {"provider": "none", "model": None}
        run = Assessment(id=str(uuid4()), agent_id=agent.id, environment_id=environment.id,
                         agent_name=agent.name, environment_name=environment.name,
                         agent_config=agent_configuration(agent), blueprint_json=blueprint.model_dump(mode="json"),
                         runtime_json={**initial_state(blueprint), "payment_mode": settings.payment_mode}, limits=limits, status="created", event_sequence=0,
                         payment_mode=settings.payment_mode,
                         examiner_mode=data.examiner_mode, examiner_provider=metadata["provider"], examiner_model=metadata["model"], examiner_config=config)
        if settings.payment_mode == "paypal_sandbox":
            from app.payments.paypal import client_binding
            run.runtime_json["paypal_client_binding"] = client_binding(settings)
        session.add(run)
        from app.evaluation.service import bind
        bind(session, run)
        append_event(session, run, "assessment.created", {"protocol_version": "1.0", "status": "created", "payment_mode": settings.payment_mode})
        if data.examiner_mode == "rai":
            append_event(session, run, "rai.examiner.configured", {"mode": "rai", **metadata}, secret_values(settings))
        proposal = session.scalar(select(RaiProposal).where(RaiProposal.environment_id == environment.id, RaiProposal.status == "compiled"))
        if proposal is not None:
            for event in session.scalars(select(RaiProposalEvent).where(RaiProposalEvent.proposal_id == proposal.id).order_by(RaiProposalEvent.sequence)):
                append_event(session, run, event.event_type, {"proposal_id": proposal.id, "source_event_id": event.id, **event.payload}, secret_values(settings))
        session.commit()
        return run
    except Exception:
        session.rollback()
        raise


@contextmanager
def locked_run(factory: sessionmaker[Session], run_id: str, token: str | None = None) -> Iterator[tuple[Session, Assessment]]:
    with factory() as session, session.begin():
        # UPDATE first: acquires the SQLite writer lock / PostgreSQL row lock without
        # a preceding stale read. All run state and event writers use this boundary.
        result = session.execute(update(Assessment).where(Assessment.id == run_id)
                                 .values(revision=Assessment.revision + 1))
        if result.rowcount != 1:
            raise ServiceError(404, "assessment_not_found", "Assessment not found.")
        run = session.get(Assessment, run_id)
        expired = (run.status == "running" and run.lease_expires_at is not None
                   and run.lease_expires_at.replace(tzinfo=timezone.utc) <= utcnow())
        if token is not None and (run.status != "running" or run.lease_token != token or expired):
            raise LeaseLost()
        if expired:
            transition(session, run, "inconclusive", "worker_lease_expired", "infrastructure")
        run.runtime_json = deepcopy(run.runtime_json)
        yield session, run
        flag_modified(run, "runtime_json")


def start_assessment(factory: sessionmaker[Session], run_id: str, settings: Settings) -> tuple[Assessment, str | None]:
    recover_expired(factory)
    with locked_run(factory, run_id) as (session, run):
        if run.status == "running":
            return run, None
        if run.status != "created":
            raise ServiceError(409, "invalid_run_transition", "Only a created assessment can be started.")
        if run.payment_mode == "paypal_sandbox":
            from app.payments.paypal import client_binding, configured
            if not configured(settings) or run.runtime_json.get("paypal_client_binding") != client_binding(settings):
                raise ServiceError(409, "paypal_assessment_configuration_changed", "Create a new Sandbox assessment after validating the current app configuration.")
        agent = find_agent(session, run.agent_id)
        if agent.last_test_status != "connected" or agent_configuration(agent) != run.agent_config:
            raise ServiceError(409, "agent_configuration_changed", "Create a new assessment with the current connected agent configuration.")
        transition(session, run, "running")
        token = run.lease_token = str(uuid4())
        # Never reclaim and replay an outbound POST. Expired work becomes inconclusive.
        run.lease_expires_at = utcnow() + timedelta(seconds=run.limits["duration_seconds"] + run.limits.get("approval_wait_seconds", 0) + 30)
        return run, token


def cancel_assessment(factory: sessionmaker[Session], run_id: str) -> Assessment:
    recover_expired(factory)
    with locked_run(factory, run_id) as (session, run):
        if run.status == "cancelled":
            return run
        transition(session, run, "cancelled", "user_cancelled")
        return run


def recover_expired(factory: sessionmaker[Session], run_id: str | None = None) -> None:
    with factory() as session:
        query = select(Assessment.id).where(Assessment.status == "running", Assessment.lease_expires_at <= utcnow())
        if run_id is not None:
            query = query.where(Assessment.id == run_id)
        ids = session.scalars(query).all()
    for run_id in ids:
        with locked_run(factory, run_id):
            pass
