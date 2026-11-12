from typing import Annotated
from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from app.models.assessment import Assessment
from app.models.rai import RaiProposal
from app.core.domain_errors import ServiceError
from sqlalchemy.orm import Session
from app.agents.service import commit, find_agent, register_agent, update_agent
from app.database.session import get_session
from app.execution.connector import AgentConnector, ConnectorError, connection_probe, get_connector
from app.models.agent import Agent, utcnow
from app.schemas.agents import AgentCreate, AgentRead, AgentUpdate, ConnectionTestInput, ConnectionTestResult
from app.schemas.errors import ErrorResponse

router = APIRouter(prefix="/agents", tags=["agents"], responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}})
DB = Annotated[Session, Depends(get_session)]

@router.post("", response_model=AgentRead, status_code=201)
def create_agent(data: AgentCreate, request: Request, session: DB) -> Agent:
    return register_agent(session, data, request.app.state.settings)

@router.get("", response_model=list[AgentRead])
def list_agents(session: DB, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)) -> list[Agent]:
    return session.scalars(select(Agent).order_by(Agent.created_at.desc(), Agent.id).offset(offset).limit(limit)).all()

@router.get("/{agent_id}", response_model=AgentRead)
def read_agent(agent_id: str, session: DB) -> Agent:
    return find_agent(session, agent_id)

@router.patch("/{agent_id}", response_model=AgentRead)
def patch_agent(agent_id: str, data: AgentUpdate, request: Request, session: DB):
    return update_agent(session, find_agent(session, agent_id), data, request.app.state.settings)

@router.delete("/{agent_id}", status_code=204)
def delete_agent(agent_id: str, session: DB) -> Response:
    if session.scalar(select(Assessment.id).where(Assessment.agent_id == agent_id).limit(1)):
        raise ServiceError(409, "agent_in_use", "This agent is referenced by a saved assessment and cannot be deleted.")
    if session.scalar(select(RaiProposal.id).where(RaiProposal.agent_id == agent_id).limit(1)):
        raise ServiceError(409, "agent_in_use", "This agent is referenced by a saved RAI proposal and cannot be deleted.")
    session.delete(find_agent(session, agent_id))
    commit(session)
    return Response(status_code=204)

@router.post("/{agent_id}/test", response_model=ConnectionTestResult,
             responses={502: {"model": ErrorResponse}, 504: {"model": ErrorResponse}})
async def test_connection(agent_id: str, session: DB, connector: Annotated[AgentConnector, Depends(get_connector)],
                          data: ConnectionTestInput = ConnectionTestInput()) -> ConnectionTestResult:
    agent = find_agent(session, agent_id)
    probe = connection_probe(data.response_mode)
    try:
        result = await connector.exchange(agent, probe)
    except ConnectorError as exc:
        agent.last_test_status = "failed"
        agent.last_test_at = utcnow()
        agent.last_test_code = exc.code
        agent.last_test_message = exc.message
        commit(session)
        raise
    agent.last_test_status = "connected"
    agent.last_test_at = utcnow()
    agent.last_test_code = None
    agent.last_test_message = "A valid protocol response was received."
    commit(session)
    return ConnectionTestResult(request_id=probe.request_id, response_type=result.type)

