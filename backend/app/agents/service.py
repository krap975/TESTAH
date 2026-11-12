from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from app.core.config import Settings
from app.core.domain_errors import ServiceError
from app.models.agent import Agent
from app.schemas.agents import AgentCreate, AgentUpdate

def find_agent(session: Session, agent_id: str) -> Agent:
    agent = session.get(Agent, agent_id)
    if agent is None:
        raise ServiceError(404, "agent_not_found", "Agent not found.")
    return agent

def commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ServiceError(409, "agent_conflict", "An agent with this name already exists.") from None
    except StaleDataError:
        session.rollback()
        raise ServiceError(409, "agent_changed", "Agent configuration changed during this operation. Refresh and retry.") from None

def validate_configuration(data: AgentCreate, settings: Settings) -> None:
    if data.connection_mode == "local_sample" and not (settings.environment == "development" and settings.allow_local_sample):
        raise ServiceError(400, "local_sample_disabled", "Local sample registration requires the explicit development setting.")
    if data.authentication and data.authentication.secret_key not in settings.agent_secrets:
        raise ServiceError(400, "secret_unavailable", "Configure the secret key in the server settings before using it.")

def apply_configuration(agent: Agent, data: AgentCreate) -> None:
    agent.name = data.name
    agent.name_key = data.name.casefold()
    agent.description = data.description
    agent.endpoint_url = data.endpoint_url
    agent.connection_mode = data.connection_mode
    agent.auth_header_name = data.authentication.header_name if data.authentication else None
    agent.auth_secret_key = data.authentication.secret_key if data.authentication else None

def register_agent(session: Session, data: AgentCreate, settings: Settings) -> Agent:
    validate_configuration(data, settings)
    agent = Agent()
    apply_configuration(agent, data)
    session.add(agent)
    commit(session)
    return agent

def update_agent(session: Session, agent: Agent, patch: AgentUpdate, settings: Settings) -> Agent:
    merged = {"name": agent.name, "description": agent.description, "endpoint_url": agent.endpoint_url,
              "connection_mode": agent.connection_mode,
              "authentication": {"header_name": agent.auth_header_name, "secret_key": agent.auth_secret_key} if agent.auth_secret_key else None}
    merged.update(patch.model_dump(exclude_unset=True))
    try:
        data = AgentCreate.model_validate(merged)
    except ValidationError:
        raise ServiceError(422, "invalid_agent", "Invalid endpoint configuration. External agents require public HTTPS on port 443; local sample mode uses its fixed URL.") from None
    validate_configuration(data, settings)
    old_connection = (agent.endpoint_url, agent.connection_mode, agent.auth_header_name, agent.auth_secret_key)
    new_connection = (data.endpoint_url, data.connection_mode,
                      data.authentication.header_name if data.authentication else None,
                      data.authentication.secret_key if data.authentication else None)
    changed = old_connection != new_connection
    apply_configuration(agent, data)
    if changed:
        agent.last_test_status = "not_tested"
        agent.last_test_at = agent.last_test_code = agent.last_test_message = None
    commit(session)
    return agent

