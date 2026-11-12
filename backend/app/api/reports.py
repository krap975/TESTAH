"""Read-only reporting routes; no operational service calls."""
from typing import Annotated
from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session
from app.database.session import get_session
from app.reports.service import assemble_report, export_report, list_reports, report_events
from app.schemas.reports import ReportRead, ReportListRead, ReportEventsRead
from app.schemas.errors import ErrorResponse

router = APIRouter(tags=["reports"], responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}})
DB = Annotated[Session, Depends(get_session)]
EvaluationID = Annotated[str | None, Query(max_length=80)]


@router.get("/reports", response_model=ReportListRead)
def index(request: Request, response: Response, session: DB, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)) -> ReportListRead:
    response.headers["Cache-Control"] = "no-store"
    return list_reports(session, offset, limit, request.app.state.settings)


@router.get("/assessments/{run_id}/report", response_model=ReportRead)
def detail(run_id: str, request: Request, response: Response, session: DB, evaluation_id: EvaluationID = None) -> ReportRead:
    response.headers["Cache-Control"] = "no-store"
    return assemble_report(session, run_id, evaluation_id, request.app.state.settings)[0]


@router.get("/assessments/{run_id}/report/events", response_model=ReportEventsRead)
def events(run_id: str, request: Request, response: Response, session: DB, evaluation_id: EvaluationID = None,
           after_sequence: int = Query(0, ge=0), limit: int = Query(500, ge=1, le=500)) -> ReportEventsRead:
    response.headers["Cache-Control"] = "no-store"
    return report_events(session, run_id, evaluation_id, after_sequence, limit, request.app.state.settings)


@router.get("/assessments/{run_id}/report/export")
def download(run_id: str, request: Request, session: DB, evaluation_id: EvaluationID = None) -> Response:
    payload = export_report(session, run_id, evaluation_id, request.app.state.settings)
    # Fixed ASCII filename: never interpolate untrusted route values into headers.
    return Response(payload, media_type="application/json", headers={"Cache-Control": "no-store",
        "Content-Disposition": 'attachment; filename="testah-assessment-report.json"', "X-Content-Type-Options": "nosniff"})
