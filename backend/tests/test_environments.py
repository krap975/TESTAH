from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.core.config import Settings
from app.environments.templates import compile_blueprint, load_templates, public_template
from app.environments.service import load_blueprint
from app.main import create_app
from app.models.environment import Environment
from app.schemas.environments import Blueprint, EnvironmentCreate

TEMPLATE = "price_change_before_checkout"
VALID = {"name":"Commerce snapshot", "template_id":TEMPLATE}

@pytest.fixture
def blueprint():
    definition = next(item for item in load_templates() if item.id == TEMPLATE)
    return compile_blueprint(definition, EnvironmentCreate(**VALID), "blueprint-test").model_dump(mode="json")

def test_templates_are_valid_and_deterministic():
    templates = load_templates()
    assert [item.name for item in templates] == ["Budget-Constrained Purchase", "Merchant Trust Verification", "Price Change Before Checkout"]
    kinds = set()
    for template in templates:
        for currency in ("USD", "EUR", "GBP"):
            for budget in (1000,10001,1_000_000):
                request = EnvironmentCreate(name="Deterministic", template_id=template.id, currency=currency, budget_minor=budget)
                first = compile_blueprint(template, request, "same-id")
                second = compile_blueprint(template, request, "same-id")
                assert first == second
                assert first.budget_minor == budget
                assert all(item.currency == currency and type(item.price_minor) is int and item.synthetic for item in first.products)
                assert all(item.synthetic for item in first.merchants)
                kinds.update(item.kind for item in first.challenges)
        preview = public_template(template).model_dump(mode="json")
        assert "evaluation" not in preview and "challenges" not in preview
        assert "trigger" not in str(preview)
    assert kinds == {"product_price_increase","shipping_fee_increase","unverified_merchant","product_unavailable"}

def test_compiler_copies_templates_and_fixtures():
    template = load_templates()[0]
    first = compile_blueprint(template, EnvironmentCreate(name="One",template_id=template.id),"one")
    first.products[0].price_minor = 1
    first.customer.preferences.append("Changed locally")
    second = compile_blueprint(template, EnvironmentCreate(name="Two",template_id=template.id),"two")
    assert second.products[0].price_minor == 9000
    assert "Changed locally" not in second.customer.preferences
    assert template.defaults.customer.preferences == load_templates()[0].defaults.customer.preferences

@pytest.mark.parametrize("change", [
    "budget_zero","budget_float","budget_bool","budget_string","bad_currency","unsupported_version","template_version",
    "template_id","registry_version","duplicate_product","duplicate_merchant","duplicate_challenge","missing_merchant",
    "product_currency","merchant_currency","price_zero","price_float","nonsynthetic","unknown_tool","modified_schema",
    "missing_tool","duplicate_tool","unsafe_policy","missing_challenge_product","bad_challenge_merchant","bad_trigger_reference",
    "wrong_mutation","negative_increase","wrong_behavior","bad_expectation_reference","missing_base_rule","missing_recovery",
    "weakened_evidence","no_legal_alternative","evaluation_version"
])
def test_invalid_blueprints_are_rejected(blueprint, change):
    data = deepcopy(blueprint)
    if change == "budget_zero": data["budget_minor"] = 0
    if change == "budget_float": data["budget_minor"] = 10000.5
    if change == "budget_bool": data["budget_minor"] = True
    if change == "budget_string": data["budget_minor"] = "10000"
    if change == "bad_currency": data["currency"] = "ZZZ"
    if change == "unsupported_version": data["blueprint_version"] = "2.0"
    if change == "template_version": data["template_version"] = "9.0"
    if change == "template_id": data["template_id"] = "unsafe_template"
    if change == "registry_version": data["tool_registry_version"] = "9.0"
    if change == "duplicate_product": data["products"].append(deepcopy(data["products"][0]))
    if change == "duplicate_merchant": data["merchants"].append(deepcopy(data["merchants"][0]))
    if change == "duplicate_challenge": data["challenges"].append(deepcopy(data["challenges"][0]))
    if change == "missing_merchant": data["products"][0]["merchant_id"] = "missing"
    if change == "product_currency": data["products"][0]["currency"] = "EUR"
    if change == "merchant_currency": data["merchants"][0]["currency"] = "EUR"
    if change == "price_zero": data["products"][0]["price_minor"] = 0
    if change == "price_float": data["products"][0]["price_minor"] = 3.14
    if change == "nonsynthetic": data["merchants"][0]["synthetic"] = False
    if change == "unknown_tool": data["tool_permissions"][0]["name"] = "run_shell"
    if change == "modified_schema": data["tool_permissions"][0]["input_schema"] = {}
    if change == "missing_tool": data["tool_permissions"].pop()
    if change == "duplicate_tool": data["tool_permissions"].append(deepcopy(data["tool_permissions"][0]))
    if change == "unsafe_policy": data["policies"]["scenario_approval_required"] = False
    if change == "missing_challenge_product": data["challenges"][0]["affected_product_id"] = "missing"
    if change == "bad_challenge_merchant": data["challenges"][0]["affected_merchant_id"] = "missing"
    if change == "bad_trigger_reference": data["challenges"][0]["trigger"]["product_id"] = "missing"
    if change == "wrong_mutation": data["challenges"][0]["state_change"] = {"field":"available","value":False}
    if change == "negative_increase": data["challenges"][0]["state_change"]["increase_minor"] = -1
    if change == "wrong_behavior": data["challenges"][0]["expected_behavior"] = "choose_available_alternative"
    if change == "bad_expectation_reference": data["evaluation"]["expectations"][-1]["challenge_id"] = "missing"
    if change == "missing_base_rule": data["evaluation"]["expectations"].pop(0)
    if change == "missing_recovery": data["evaluation"]["expectations"].pop()
    if change == "weakened_evidence": data["evaluation"]["expectations"][0]["evidence_types"] = ["assessment.finished"]
    if change == "no_legal_alternative": data["products"][1]["available"] = False
    if change == "evaluation_version": data["evaluation"]["version"] = "anything"
    with pytest.raises(ValidationError): Blueprint.model_validate(data)

def test_creation_and_safe_preview(agent_client):
    templates = agent_client.get("/api/environment-templates")
    assert templates.status_code == 200 and len(templates.json()) == 3
    response = agent_client.post("/api/environments",json={**VALID,"budget_minor":12345,"currency":"EUR","customer_name":"Synthetic Casey","objective":"Compare synthetic offers safely."})
    assert response.status_code == 201, response.text
    record = response.json()
    assert record["status"] == "compiled" and record["budget_minor"] == 12345
    assert record["created_at"].endswith("Z")
    assert record["blueprint"]["customer"]["name"] == "Synthetic Casey"
    assert len(record["blueprint"]["tool_permissions"]) == 6
    assert len(record["blueprint"]["products"]) == 5
    assert len(record["blueprint"]["merchants"]) == 4
    assert "evaluation" not in record["blueprint"] and "challenges" not in record["blueprint"]
    assert "trigger" not in response.text and "expected_behavior" not in response.text and "evidence_types" not in response.text
    assert "owner_scope_id" not in response.text
    assert agent_client.get("/api/environments/" + record["id"]).json() == record
    listing = agent_client.get("/api/environments").json()
    assert listing[0]["id"] == record["id"] and "blueprint" not in listing[0]
    assert agent_client.get("/api/environments?offset=1").json() == []
    assert agent_client.get("/api/environments?limit=101").status_code == 422
    assert agent_client.get("/api/environments/missing").status_code == 404

@pytest.mark.parametrize("change", [
    {"name":""}, {"name":"   "}, {"budget_minor":0}, {"budget_minor":-1}, {"budget_minor":999},
    {"budget_minor":1_000_001}, {"budget_minor":12.34}, {"budget_minor":True}, {"budget_minor":"10000"},
    {"currency":"usd"}, {"currency":"ZZZ"}, {"currency":"JPY"}, {"template_id":"missing"}, {"template_version":"2.0"},
    {"blueprint":{}}, {"policies":{"enforce_budget":False}}, {"owner_scope_id":"another-user"}, {"status":"completed"},
    {"customer_name":" "}, {"objective":""}
])
def test_api_rejects_invalid_and_unrestricted_updates(agent_client,change):
    response = agent_client.post("/api/environments", json={**VALID,**change})
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] in {"validation_error","unsupported_template"}
    assert agent_client.get("/api/environments").json() == []

def test_persistence_restart_and_snapshot_isolation(agent_client):
    one = agent_client.post("/api/environments",json={**VALID,"name":"One"}).json()
    two = agent_client.post("/api/environments",json={**VALID,"name":"Two"}).json()
    assert one["id"] != two["id"]
    with agent_client.app.state.session_factory() as session:
        first = session.get(Environment,one["id"])
        second = session.get(Environment,two["id"])
        assert first.blueprint_json is not second.blueprint_json
        assert first.owner_scope_id is None
        original_second = deepcopy(second.blueprint_json)
        changed = deepcopy(first.blueprint_json)
        changed["products"][0]["price_minor"] += 1
        first.blueprint_json = changed  # Trusted internal test only; no HTTP mutation exists.
        session.commit()
        assert session.get(Environment,two["id"]).blueprint_json == original_second
        assert load_blueprint(first).evaluation.version == "commerce-evidence-v1"
    with TestClient(create_app(agent_client.app.state.settings)) as restarted:
        assert restarted.get("/api/environments/"+two["id"]).json() == two
        first_after = restarted.get("/api/environments/"+one["id"]).json()
        assert first_after["blueprint"]["products"][0]["price_minor"] == one["blueprint"]["products"][0]["price_minor"] + 1
    assert agent_client.patch("/api/environments/"+one["id"],json={"blueprint":{}}).status_code == 405
    assert agent_client.delete("/api/environments/"+one["id"]).status_code == 405

