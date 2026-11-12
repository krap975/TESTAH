from typing import Annotated
from fastapi import APIRouter, Depends, Query, Request
import anyio
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from app.core.monitor_auth import require_monitor_access
from app.events.public import public_event
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.domain_errors import ServiceError
from app.database.session import get_session
from app.execution.service import cancel_assessment, create_assessment, recover_expired, start_assessment
from app.models.assessment import Assessment, RunEvent
from app.schemas.assessments import AssessmentCreate, AssessmentRead, EventRead
from app.schemas.errors import ErrorResponse
from app.schemas.evaluation import EvaluationRead, EvaluationRequest, EvaluationResultRead
from app.evaluation.service import public_result, read_evaluation, request_evaluation
from app.models.evaluation import Evaluation

router = APIRouter(prefix="/assessments", tags=["assessments"], responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}})
DB = Annotated[Session, Depends(get_session)]


def find_run(session: Session, run_id: str) -> Assessment:
    run = session.get(Assessment, run_id)
    if run is None:
        raise ServiceError(404, "assessment_not_found", "Assessment not found.")
    return run


@router.post("", response_model=AssessmentRead, status_code=201)
def create_run(data: AssessmentCreate, request: Request, session: DB) -> Assessment:
    return create_assessment(session, data, request.app.state.settings)


@router.get("", response_model=list[AssessmentRead])
def list_runs(request: Request, session: DB, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)) -> list[Assessment]:
    recover_expired(request.app.state.session_factory)
    return session.scalars(select(Assessment).order_by(Assessment.created_at.desc(), Assessment.id).offset(offset).limit(limit)).all()


@router.get("/{run_id}", response_model=AssessmentRead)
def read_run(run_id: str, request: Request, session: DB) -> AssessmentRead:
    recover_expired(request.app.state.session_factory)
    run = find_run(session, run_id)
    result = AssessmentRead.model_validate(run)
    result.evaluation = EvaluationRead.model_validate(read_evaluation(session, run))
    return result


@router.post("/{run_id}/evaluate", response_model=EvaluationRead, status_code=202)
def score_run(run_id: str, data: EvaluationRequest, request: Request) -> dict:
    return request_evaluation(request.app.state.session_factory, run_id)


@router.get("/{run_id}/evaluations", response_model=list[EvaluationResultRead])
def evaluation_history(run_id: str, session: DB, offset: int = Query(0, ge=0),
                       limit: int = Query(20, ge=1, le=100)) -> list[dict]:
    find_run(session, run_id)
    rows = session.scalars(select(Evaluation).where(Evaluation.run_id == run_id)
        .order_by(Evaluation.cutoff_sequence.desc(), Evaluation.created_at.desc()).offset(offset).limit(limit)).all()
    return [public_result(row) for row in rows]


@router.post("/{run_id}/start", response_model=AssessmentRead, status_code=202)
async def start_run(run_id: str, request: Request) -> Assessment:
    run, token = start_assessment(request.app.state.session_factory, run_id, request.app.state.settings)
    if token is not None:
        request.app.state.worker.submit(run.id, token)
    return run


@router.post("/{run_id}/cancel", response_model=AssessmentRead)
async def cancel_run(run_id: str, request: Request) -> Assessment:
    run = cancel_assessment(request.app.state.session_factory, run_id)
    request.app.state.worker.cancel(run_id)
    return run


@router.get("/{run_id}/events", response_model=list[EventRead])
def run_events(run_id: str, request: Request, session: DB, after_sequence: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500)) -> list[EventRead]:
    find_run(session, run_id)
    rows = session.scalars(select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.sequence > after_sequence)
                           .order_by(RunEvent.sequence).limit(limit)).all()
    return [public_event(row, request.app.state.settings) for row in rows]


@router.get("/{run_id}/stream", dependencies=[Depends(require_monitor_access)], response_class=StreamingResponse)
async def stream_events(run_id: str, request: Request, after_sequence: int = Query(0, ge=0)) -> StreamingResponse:
    streams = request.app.state.assessment_streams
    lease = streams.reserve()
    try:
        cursor = await anyio.to_thread.run_sync(lambda: streams.cursor(run_id, after_sequence, request.headers.get("last-event-id")))
    except BaseException:
        lease.close()
        raise
    async def release() -> None:
        lease.close()
    return StreamingResponse(streams.iterate(run_id, cursor, request.is_disconnected, lease), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"}, background=BackgroundTask(release))
