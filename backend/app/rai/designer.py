"""Proposal lifecycle; never gives an LLM a database session or trusted Blueprint."""
import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta, timezone
import logging
import re
from uuid import uuid4
import anyio
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from app.agents.service import find_agent
from app.core.config import Settings
from app.core.domain_errors import ServiceError
from app.environments.designed import compile_design
from app.environments.service import environment_record, preview_blueprint
from app.environments.templates import compile_blueprint, load_templates
from app.events.store import sanitize
from app.models.agent import Agent, utcnow
from app.models.environment import EnvironmentTemplate
from app.models.rai import RaiProposal, RaiProposalEvent
from app.rai.prompts import DESIGNER_PROMPT
from app.rai.errors import failure_message
from app.rai.diagnostics import diagnostic_scope, timed_phase, timing
from app.rai.provider import (JsonProvider, ProviderError, get_provider, provider_config, provider_metadata, secret_values)
from app.schemas.environment_design import EnvironmentDesign
from app.schemas.environments import Blueprint, EnvironmentCreate
from app.schemas.rai import ProposalCreate, ProposalRead


class ProposalLeaseLost(Exception):
    pass


def append_proposal_event(session: Session, proposal: RaiProposal, kind: str, payload: dict, secrets: list[str]) -> None:
    proposal.event_sequence += 1
    session.add(RaiProposalEvent(proposal_id=proposal.id, sequence=proposal.event_sequence, event_type=kind,
                                payload=sanitize(payload, secrets)))


def capability_summary(agent: Agent, settings: Settings) -> dict:
    description = sanitize(agent.description, secret_values(settings))
    evidence = bool(re.search(r"(?i)\b(commerce|shop\w*|purchas\w*|merchant|budget|checkout|headphones)\b", description))
    return {"source": "self_declared_description", "declared_description": description, "commerce_evidence": evidence,
            "capabilities_verified": False,
            "uncertainties": ["No structured candidate capability or supported-tool metadata exists; the description is unverified.",
                              *([] if evidence else ["Commerce capability is unknown or unsupported; use conservative commerce defaults."])],
            "tool_interface_source": "Testah registry 1.0, not a claim of candidate tool support"}


def designer_manifest(summary: dict) -> dict:
    templates = []
    for definition in load_templates():
        bp = compile_blueprint(definition, EnvironmentCreate(name="Design guide", template_id=definition.id), "design-guide")
        templates.append({"id": definition.id, "name": definition.name,
                          "products": [p.model_dump(mode="json") for p in bp.products],
                          "merchants": [m.model_dump(mode="json") for m in bp.merchants],
                          "challenge_options": [{"id": c.id, "kind": c.kind, "summary": c.summary,
                            "increase_allowed": c.state_change.field in {"price_minor", "shipping_fee_minor"}} for c in bp.challenges]})
    return {"capability_summary": summary, "templates": templates, "supported_category": "headphones",
            "supported_currencies": ["USD", "EUR", "GBP"], "budget_bounds_minor": [1000, 1_000_000],
            "tools": [tool.model_dump(mode="json") for tool in bp.tool_permissions]}


@contextmanager
def locked_proposal(factory: sessionmaker[Session], proposal_id: str, token: str | None = None) -> Iterator[tuple[Session, RaiProposal]]:
    with factory() as session, session.begin():
        result = session.execute(update(RaiProposal).where(RaiProposal.id == proposal_id).values(revision=RaiProposal.revision + 1))
        if result.rowcount != 1:
            raise ServiceError(404, "proposal_not_found", "RAI proposal not found.")
        proposal = session.get(RaiProposal, proposal_id)
        if token is not None and (proposal.status != "generating" or proposal.lease_token != token
                or proposal.lease_expires_at.replace(tzinfo=timezone.utc) <= utcnow()):
            raise ProposalLeaseLost()
        yield session, proposal
        if session.is_modified(proposal):
            proposal.updated_at = utcnow()


def recover_proposals(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        ids = session.scalars(select(RaiProposal.id).where(RaiProposal.status == "generating", RaiProposal.lease_expires_at <= utcnow())).all()
    for proposal_id in ids:
        with locked_proposal(factory, proposal_id) as (session, proposal):
            if proposal.status == "generating" and proposal.lease_expires_at.replace(tzinfo=timezone.utc) <= utcnow():
                proposal.status = "failed"
                proposal.validation_json = {"valid": False, "code": "generation_worker_expired"}
                proposal.lease_token = None
                proposal.lease_expires_at = None
                append_proposal_event(session, proposal, "rai.proposal.validation", proposal.validation_json, [])


def create_proposal(factory: sessionmaker[Session], data: ProposalCreate, settings: Settings) -> tuple[RaiProposal, str | None]:
    recover_proposals(factory)
    with factory() as session:
        existing = session.scalar(select(RaiProposal).where(RaiProposal.agent_id == data.agent_id, RaiProposal.request_key == data.request_key))
        if existing is not None:
            return existing, None
        agent = find_agent(session, data.agent_id)
        config = provider_config(settings)
        metadata = provider_metadata(config)
        token = str(uuid4())
        proposal = RaiProposal(id=str(uuid4()), agent_id=agent.id, request_key=data.request_key, status="generating",
                              provider=metadata["provider"], model=metadata["model"], capability_summary=capability_summary(agent, settings),
                              proposal_json=None, blueprint_json=None, validation_json={"valid": None, "code": "pending"},
                              provider_config=config, event_sequence=0, lease_token=token,
                              lease_expires_at=utcnow() + timedelta(seconds=settings.rai_generation_seconds + 5))
        session.add(proposal)
        append_proposal_event(session, proposal, "rai.generation.requested", metadata, secret_values(settings))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            existing = session.scalar(select(RaiProposal).where(RaiProposal.agent_id == data.agent_id, RaiProposal.request_key == data.request_key))
            if existing is None:
                raise ServiceError(409, "proposal_conflict", "The agent changed during proposal creation. Refresh and retry.") from None
            return existing, None
        except Exception:
            session.rollback()
            raise
        return proposal, token


def read_proposal(proposal: RaiProposal, settings: Settings) -> ProposalRead:
    preview = None
    if proposal.blueprint_json is not None:
        try:
            preview = preview_blueprint(Blueprint.model_validate(proposal.blueprint_json))
        except (ValidationError, ValueError):
            raise ServiceError(500, "invalid_stored_proposal", "The stored RAI proposal could not be validated.") from None
    validation = dict(proposal.validation_json)
    if proposal.status == "failed":
        validation["message"] = failure_message(validation["code"])
    return ProposalRead(id=proposal.id, agent_id=proposal.agent_id, status=proposal.status, provider=proposal.provider,
                        model=sanitize(proposal.model, secret_values(settings)), is_mock=proposal.provider == "mock",
                        capability_summary=proposal.capability_summary, validation=validation, preview=preview,
                        environment_id=proposal.environment_id, created_at=proposal.created_at.replace(tzinfo=timezone.utc),
                        updated_at=proposal.updated_at.replace(tzinfo=timezone.utc), event_sequence=proposal.event_sequence)


def compile_proposal(factory: sessionmaker[Session], proposal_id: str, settings: Settings) -> RaiProposal:
    with diagnostic_scope(proposal_id), timed_phase("environment_compilation"):
        return _compile_proposal(factory, proposal_id, settings)


def _compile_proposal(factory: sessionmaker[Session], proposal_id: str, settings: Settings) -> RaiProposal:
    with locked_proposal(factory, proposal_id) as (session, proposal):
        if proposal.status == "compiled":
            return proposal
        if proposal.status != "ready":
            raise ServiceError(409, "proposal_not_ready", "Only a validated ready proposal can be compiled.")
        try:
            design = EnvironmentDesign.model_validate(proposal.proposal_json)
            frozen = Blueprint.model_validate(proposal.blueprint_json)
            blueprint = compile_design(design, frozen.blueprint_id)
            if blueprint != frozen:
                raise ValueError()
        except (ValidationError, ValueError):
            raise ServiceError(409, "proposal_validation_failed", "The saved design failed independent compilation checks.") from None
        if session.get(EnvironmentTemplate, (blueprint.template_id, blueprint.template_version)) is None:
            raise ServiceError(503, "template_reference_missing", "Apply database migrations before compiling environments.")
        session.add(environment_record(design.name, blueprint, generation_mode=proposal.provider, designer_model=proposal.model))
        session.flush()  # FK target exists before linking this proposal.
        proposal.environment_id = blueprint.blueprint_id
        proposal.status = "compiled"
        append_proposal_event(session, proposal, "rai.environment.compiled", {"environment_id": blueprint.blueprint_id,
                              "provider": proposal.provider, "model": proposal.model}, secret_values(settings))
        return proposal


class DesignerWorker:
    def __init__(self, factory: sessionmaker[Session], settings: Settings) -> None:
        self.factory = factory
        self.settings = settings
        self.tasks: dict[str, asyncio.Task] = {}
        self.provider_override: JsonProvider | None = None  # Explicit dependency injection for isolated tests.

    def has_capacity(self) -> bool:
        return len(self.tasks) < self.settings.rai_max_generation_workers

    def submit(self, proposal_id: str, token: str) -> None:
        task = asyncio.create_task(self.execute(proposal_id, token))
        self.tasks[proposal_id] = task
        def finished(done: asyncio.Task) -> None:
            self.tasks.pop(proposal_id, None)
            if not done.cancelled() and done.exception() is not None:
                logging.getLogger(__name__).error("RAI worker failed; its durable lease will expire (proposal_id=%s)", proposal_id)
        task.add_done_callback(finished)

    def fail(self, proposal_id: str, token: str, code: str) -> None:
        timing("generation_result", 0, code=code)
        try:
            with locked_proposal(self.factory, proposal_id, token) as (session, proposal):
                proposal.status = "failed"
                proposal.validation_json = {"valid": False, "code": code}
                proposal.lease_token = None
                proposal.lease_expires_at = None
                append_proposal_event(session, proposal, "rai.proposal.validation", proposal.validation_json, [])
        except ProposalLeaseLost:
            pass

    async def execute(self, proposal_id: str, token: str) -> None:
        with diagnostic_scope(proposal_id), timed_phase("generation_total"):
            await self._execute(proposal_id, token)

    async def _execute(self, proposal_id: str, token: str) -> None:
        try:
            with locked_proposal(self.factory, proposal_id, token) as (_session, proposal):
                config = proposal.provider_config
                timing("queue_wait", (utcnow() - proposal.created_at.replace(tzinfo=timezone.utc)).total_seconds())
                with timed_phase("designer_manifest"):
                    manifest = designer_manifest(proposal.capability_summary)
                duration = (proposal.lease_expires_at.replace(tzinfo=timezone.utc) - utcnow()).total_seconds() - 5
                timing("generation_budget", 0, remaining_seconds=round(duration, 3))
            if duration <= 0:
                self.fail(proposal_id, token, "generation_timeout")
                return
            provider = self.provider_override or get_provider(self.settings, config)
            with anyio.fail_after(duration):
                for attempt in range(self.settings.rai_repair_attempts + 1):
                    timing("design_attempt", 0, repair_attempt=attempt)
                    try:
                        output = await provider.generate("designer", DESIGNER_PROMPT, {**manifest, "repair_attempt": attempt}, EnvironmentDesign.model_json_schema())
                        with timed_phase("schema_validation", repair_attempt=attempt):
                            design = EnvironmentDesign.model_validate(sanitize(output, secret_values(self.settings)))
                            if not manifest["capability_summary"]["commerce_evidence"] and design.template_id != "budget_constrained_purchase":
                                raise ValueError("Insufficient capability evidence for a specialized template.")
                        with timed_phase("blueprint_compilation", repair_attempt=attempt):
                            blueprint = compile_design(design, str(uuid4()))
                    except (ValidationError, ValueError) as _exc:
                        code = "invalid_environment_proposal"
                    except ProviderError as exc:
                        if exc.code != "invalid_model_output":
                            raise
                        code = exc.code
                    else:
                        with locked_proposal(self.factory, proposal_id, token) as (session, proposal):
                            proposal.proposal_json = design.model_dump(mode="json")
                            proposal.blueprint_json = blueprint.model_dump(mode="json")
                            proposal.validation_json = {"valid": True, "code": "validated", "attempts": attempt + 1}
                            proposal.status = "ready"
                            proposal.lease_token = None
                            proposal.lease_expires_at = None
                            append_proposal_event(session, proposal, "rai.template.selected", {"template_id": design.template_id,
                                "provider": proposal.provider, "model": proposal.model}, secret_values(self.settings))
                            append_proposal_event(session, proposal, "rai.proposal.validation", proposal.validation_json, [])
                        return
                    if attempt < self.settings.rai_repair_attempts:
                        timing("repair_scheduled", 0, repair_attempt=attempt + 1, reason=code)
                    with locked_proposal(self.factory, proposal_id, token) as (session, proposal):
                        append_proposal_event(session, proposal, "rai.proposal.validation", {"valid": False, "code": code,
                            "attempt": attempt + 1, "repair_scheduled": attempt < self.settings.rai_repair_attempts}, [])
                self.fail(proposal_id, token, code)
        except ProposalLeaseLost:
            pass
        except asyncio.CancelledError:
            self.fail(proposal_id, token, "generation_worker_stopped")
            raise
        except TimeoutError:
            timing("worker_timeout", 0, source="generation_deadline")
            self.fail(proposal_id, token, "generation_timeout")
        except ProviderError as exc:
            self.fail(proposal_id, token, exc.code)
        except Exception:
            self.fail(proposal_id, token, "generation_internal_error")

    async def close(self) -> None:
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
