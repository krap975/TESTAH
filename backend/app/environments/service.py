from uuid import uuid4
from pydantic import ValidationError
from sqlalchemy.orm import Session
from app.core.domain_errors import ServiceError
from app.environments.templates import compile_blueprint, load_templates, public_template
from app.models.environment import Environment, EnvironmentTemplate
from app.schemas.environments import (Blueprint, ChallengeSummary, EnvironmentCreate, EnvironmentPreview,
                                     EnvironmentRead, EnvironmentSummary, TemplateRead)

def available_templates() -> list[TemplateRead]:
    return [public_template(definition) for definition in load_templates()]

def create_environment(session: Session, data: EnvironmentCreate, owner_scope_id: str | None = None) -> EnvironmentRead:
    definition = next((item for item in load_templates() if item.id == data.template_id and item.version == data.template_version), None)
    if definition is None:
        raise ServiceError(422, "unsupported_template", "Select a supported environment template and version.")
    if session.get(EnvironmentTemplate, (definition.id, definition.version)) is None:
        raise ServiceError(503, "template_reference_missing", "Environment template references are missing. Apply database migrations.")
    identifier = str(uuid4())
    try:
        blueprint = compile_blueprint(definition, data, identifier)
    except (ValidationError, ValueError):
        raise ServiceError(422, "invalid_environment", "The selected customization cannot produce a consistent safe environment.") from None
    environment = environment_record(data.name, blueprint, owner_scope_id)
    session.add(environment)
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    return environment_details(environment)


def environment_record(name: str, blueprint: Blueprint, owner_scope_id: str | None = None,
                       generation_mode: str = "manual", designer_model: str | None = None) -> Environment:
    """Build a row; the caller owns its explicit transaction and commit."""
    return Environment(
        id=blueprint.blueprint_id, name=name, template_id=blueprint.template_id, template_version=blueprint.template_version,
        blueprint_version=blueprint.blueprint_version, blueprint_json=blueprint.model_dump(mode="json"),
        currency=blueprint.currency, budget_minor=blueprint.budget_minor, status="compiled", owner_scope_id=owner_scope_id,
        generation_mode=generation_mode, designer_model=designer_model,
    )

def find_environment(session: Session, environment_id: str) -> Environment:
    environment = session.get(Environment, environment_id)
    if environment is None:
        raise ServiceError(404, "environment_not_found", "Environment not found.")
    return environment

def load_blueprint(environment: Environment) -> Blueprint:
    """Internal authoritative snapshot accessor; never send its private fields to a candidate."""
    try:
        blueprint = Blueprint.model_validate(environment.blueprint_json)
        if (blueprint.blueprint_id, blueprint.template_id, blueprint.template_version, blueprint.blueprint_version,
                blueprint.currency, blueprint.budget_minor) != (environment.id, environment.template_id,
                environment.template_version, environment.blueprint_version, environment.currency, environment.budget_minor):
            raise ValueError("Snapshot metadata mismatch")
        return blueprint
    except (ValidationError, ValueError):
        raise ServiceError(500, "invalid_stored_environment", "The stored environment snapshot could not be validated.") from None

def environment_summary(environment: Environment) -> EnvironmentSummary:
    return EnvironmentSummary(
        id=environment.id, name=environment.name, template_id=environment.template_id,
        template_version=environment.template_version, blueprint_version=environment.blueprint_version,
        currency=environment.currency, budget_minor=environment.budget_minor, status=environment.status,
        created_at=environment.created_at, generation_mode=environment.generation_mode, designer_model=environment.designer_model,
    )

def environment_details(environment: Environment) -> EnvironmentRead:
    blueprint = load_blueprint(environment)
    return EnvironmentRead(**environment_summary(environment).model_dump(), blueprint=preview_blueprint(blueprint))


def preview_blueprint(blueprint: Blueprint) -> EnvironmentPreview:
    public = blueprint.model_dump(exclude={"challenges", "evaluation"})
    public["challenge_summaries"] = [ChallengeSummary(id=item.id, kind=item.kind, summary=item.summary) for item in blueprint.challenges]
    public["evaluation_version"] = blueprint.evaluation.version
    return EnvironmentPreview.model_validate(public)

