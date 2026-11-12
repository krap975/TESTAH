"""Versioned declarative template resources and deterministic compilation."""
import json
from pathlib import Path
from typing import Annotated, Literal
from pydantic import Field, TypeAdapter
from app.schemas.environments import (Blueprint, Challenge, EnvironmentCreate, EvaluationExpectations,
                                     Persona, PurchasePolicies, ShortText, TemplateRead, ChallengeSummary)
from app.schemas.protocol import Identifier, StrictModel
from app.tools.registry import Currency, tool_definitions

DATA = Path(__file__).with_name("data")

class Defaults(StrictModel):
    customer: Persona
    objective: ShortText
    currency: Currency
    budget_minor: Annotated[int, Field(ge=1000, le=1_000_000)]
    policies: PurchasePolicies

class TemplateDefinition(StrictModel):
    id: Identifier
    version: Literal["1.0"]
    name: ShortText
    description: ShortText
    defaults: Defaults
    challenges: list[Challenge]
    evaluation: EvaluationExpectations

def load_templates() -> list[TemplateDefinition]:
    # Fresh models on each call avoid exposing mutable cached template state.
    definitions = TypeAdapter(list[TemplateDefinition]).validate_json((DATA / "templates.json").read_text(encoding="utf-8"))
    if len({definition.id for definition in definitions}) != len(definitions):
        raise ValueError("Duplicate template references.")
    return definitions

def compile_blueprint(definition: TemplateDefinition, data: EnvironmentCreate, blueprint_id: str) -> Blueprint:
    if data.template_id != definition.id or data.template_version != definition.version:
        raise ValueError("Template identifier/version must match the selected definition.")
    fixtures = json.loads((DATA / "commerce-fixtures.json").read_text(encoding="utf-8"))
    defaults = definition.defaults.model_dump(mode="json")
    budget = data.budget_minor if data.budget_minor is not None else defaults["budget_minor"]
    denominator = defaults["budget_minor"]
    def scale(amount: int) -> int:
        return (amount * budget + denominator - 1) // denominator
    for merchant in fixtures["merchants"]:
        merchant["shipping_fee_minor"] = scale(merchant["shipping_fee_minor"])
        merchant["currency"] = data.currency
    for product in fixtures["products"]:
        product["price_minor"] = scale(product["price_minor"])
        product["currency"] = data.currency
    challenges = [challenge.model_dump(mode="json") for challenge in definition.challenges]
    for challenge in challenges:
        change = challenge["state_change"]
        if "increase_minor" in change:
            change["increase_minor"] = scale(change["increase_minor"])
    if data.customer_name is not None:
        defaults["customer"]["name"] = data.customer_name
    return Blueprint.model_validate({
        "blueprint_id": blueprint_id, "blueprint_version": "1.0", "template_id": definition.id,
        "template_version": definition.version, "customer": defaults["customer"],
        "objective": data.objective if data.objective is not None else defaults["objective"],
        "currency": data.currency, "budget_minor": budget, **fixtures,
        "tool_registry_version": "1.0", "tool_permissions": [tool.model_dump() for tool in tool_definitions()],
        "policies": defaults["policies"], "challenges": challenges,
        "evaluation": definition.evaluation.model_dump(mode="json"),
    })

def public_template(definition: TemplateDefinition) -> TemplateRead:
    # Compile defaults too: an invalid source definition must never be offered.
    compile_blueprint(definition, EnvironmentCreate(name=definition.name, template_id=definition.id), "template-validation")
    return TemplateRead(
        id=definition.id, version=definition.version, name=definition.name, description=definition.description,
        default_budget_minor=definition.defaults.budget_minor, default_currency=definition.defaults.currency,
        customer=definition.defaults.customer, objective=definition.defaults.objective,
        supported_currencies=["USD", "EUR", "GBP"], min_budget_minor=1000, max_budget_minor=1_000_000,
        allowed_tools=tool_definitions(), policies=definition.defaults.policies,
        challenge_summaries=[ChallengeSummary(id=item.id, kind=item.kind, summary=item.summary) for item in definition.challenges],
        evaluation_version=definition.evaluation.version,
    )

