"""Controlled extension of the existing compiler, with full final Blueprint validation."""
from app.environments.templates import compile_blueprint, load_templates
from app.schemas.environment_design import EnvironmentDesign, safe_scenario_text
from app.schemas.environments import Blueprint, EnvironmentCreate


def compile_design(design: EnvironmentDesign, blueprint_id: str) -> Blueprint:
    definition = next(t for t in load_templates() if t.id == design.template_id and t.version == design.template_version)
    baseline = compile_blueprint(definition, EnvironmentCreate(name=design.name, template_id=design.template_id,
                                  currency=design.currency, budget_minor=design.budget_minor), blueprint_id)
    data = baseline.model_dump(mode="json")
    for text in [design.customer.name, design.customer.description, *design.customer.preferences]:
        safe_scenario_text(text)
    data["customer"] = design.customer.model_dump(mode="json")
    data["objective"] = design.objective
    for changes, entities, id_field, copy_fields in (
        (design.products, data["products"], "product_id", ("name", "price_minor")),
        (design.merchants, data["merchants"], "merchant_id", ("display_name", "shipping_fee_minor")),
    ):
        seen = set()
        by_id = {entity["id"]: entity for entity in entities}
        for change in changes:
            values = change.model_dump()
            identifier = values[id_field]
            if identifier in seen or identifier not in by_id:
                raise ValueError("Invalid or repeated variation reference.")
            seen.add(identifier)
            for key in copy_fields:
                if isinstance(values[key], str):
                    safe_scenario_text(values[key])
                by_id[identifier][key] = values[key]
    selected = set()
    challenges = {c["id"]: c for c in data["challenges"]}
    for selection in design.challenges:
        if selection.challenge_id in selected or selection.challenge_id not in challenges:
            raise ValueError("Unsupported or repeated challenge selection.")
        selected.add(selection.challenge_id)
        mutation = challenges[selection.challenge_id]["state_change"]
        if selection.increase_minor is not None:
            if "increase_minor" not in mutation or selection.increase_minor > design.budget_minor:
                raise ValueError("Unsupported challenge parameter.")
            mutation["increase_minor"] = selection.increase_minor
    data["challenges"] = [c for c in data["challenges"] if c["id"] in selected]
    # Retain canonical base evidence and every selected challenge's canonical recovery rule.
    data["evaluation"]["expectations"] = [e for e in data["evaluation"]["expectations"]
        if e["challenge_id"] is None or e["challenge_id"] in selected]
    return Blueprint.model_validate(data)
