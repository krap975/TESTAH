from typing import Annotated
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.domain_errors import ServiceError
from app.database.session import get_session
from app.models.rai import RaiProposal, RaiProposalEvent
from app.rai.designer import compile_proposal, create_proposal, read_proposal, recover_proposals
from app.rai.provider import provider_config, provider_metadata
from app.schemas.rai import ProposalCreate, ProposalRead
from app.schemas.errors import ErrorResponse

router = APIRouter(prefix="/rai", tags=["RAI"], responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse},
                    422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
DB = Annotated[Session, Depends(get_session)]


def find_proposal(session: Session, proposal_id: str) -> RaiProposal:
    proposal = session.get(RaiProposal, proposal_id)
    if proposal is None:
        raise ServiceError(404, "proposal_not_found", "RAI proposal not found.")
    return proposal


@router.get("/configuration")
def configuration(request: Request) -> dict:
    settings = request.app.state.settings
    return {**provider_metadata(provider_config(settings)), "examiner_modes": ["deterministic", "rai"],
            "diagnostics_available": settings.environment == "development"}


@router.post("/proposals", response_model=ProposalRead, status_code=202)
async def generate_proposal(data: ProposalCreate, request: Request) -> ProposalRead:
    # Admission and task scheduling happen without an await, within this process.
    worker = request.app.state.designer_worker
    if not worker.has_capacity():
        with request.app.state.session_factory() as session:
            existing = session.scalar(select(RaiProposal).where(RaiProposal.agent_id == data.agent_id, RaiProposal.request_key == data.request_key))
            if existing is not None:
                return read_proposal(existing, request.app.state.settings)
        raise ServiceError(503, "rai_capacity_reached", "RAI generation capacity is busy. Retry the same request key later.")
    proposal, token = create_proposal(request.app.state.session_factory, data, request.app.state.settings)
    if token:
        worker.submit(proposal.id, token)
    return read_proposal(proposal, request.app.state.settings)


@router.get("/proposals", response_model=list[ProposalRead])
def list_proposals(request: Request, session: DB, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)) -> list[ProposalRead]:
    recover_proposals(request.app.state.session_factory)
    proposals = session.scalars(select(RaiProposal).order_by(RaiProposal.created_at.desc(), RaiProposal.id).offset(offset).limit(limit)).all()
    return [read_proposal(proposal, request.app.state.settings) for proposal in proposals]


@router.get("/proposals/{proposal_id}", response_model=ProposalRead)
def get_proposal(proposal_id: str, request: Request, session: DB) -> ProposalRead:
    recover_proposals(request.app.state.session_factory)
    return read_proposal(find_proposal(session, proposal_id), request.app.state.settings)


@router.post("/proposals/{proposal_id}/compile", response_model=ProposalRead)
def approve_compile(proposal_id: str, request: Request) -> ProposalRead:
    return read_proposal(compile_proposal(request.app.state.session_factory, proposal_id, request.app.state.settings), request.app.state.settings)


@router.get("/proposals/{proposal_id}/events")
def proposal_events(proposal_id: str, session: DB, after_sequence: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500)) -> list[dict]:
    find_proposal(session, proposal_id)
    events = session.scalars(select(RaiProposalEvent).where(RaiProposalEvent.proposal_id == proposal_id, RaiProposalEvent.sequence > after_sequence)
                            .order_by(RaiProposalEvent.sequence).limit(limit)).all()
    return [{"id": e.id, "proposal_id": e.proposal_id, "sequence": e.sequence,
             "created_at": e.created_at.isoformat() + ("Z" if e.created_at.tzinfo is None else ""),
             "event_type": e.event_type, "payload": e.payload} for e in events]
