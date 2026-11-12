from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.session import get_session
from app.environments.service import (available_templates, create_environment, environment_details,
                                       environment_summary, find_environment)
from app.models.environment import Environment
from app.schemas.environments import EnvironmentCreate, EnvironmentRead, EnvironmentSummary, TemplateRead
from app.schemas.errors import ErrorResponse

router = APIRouter(tags=["environments"], responses={422:{"model":ErrorResponse}, 404:{"model":ErrorResponse}})
DB = Annotated[Session, Depends(get_session)]

@router.get("/environment-templates", response_model=list[TemplateRead])
def list_templates() -> list[TemplateRead]:
    return available_templates()

@router.post("/environments", response_model=EnvironmentRead, status_code=201)
def new_environment(data: EnvironmentCreate, session: DB) -> EnvironmentRead:
    return create_environment(session, data)

@router.get("/environments", response_model=list[EnvironmentSummary])
def list_environments(session: DB, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)) -> list[EnvironmentSummary]:
    rows = session.scalars(select(Environment).order_by(Environment.created_at.desc(), Environment.id).offset(offset).limit(limit)).all()
    return [environment_summary(row) for row in rows]

@router.get("/environments/{environment_id}", response_model=EnvironmentRead)
def read_environment(environment_id: str, session: DB) -> EnvironmentRead:
    return environment_details(find_environment(session, environment_id))

