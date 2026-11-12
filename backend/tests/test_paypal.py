"""Mock the HTTP boundary, exercising the real official SDK and durable workflow."""
import asyncio
from copy import deepcopy
from datetime import timedelta
import json
import logging
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4
import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import select
from app.core.config import Settings
from app.core.domain_errors import ServiceError
from app.events.store import append_event
from app.execution.service import cancel_assessment, locked_run, start_assessment
from app.models.agent import Agent, utcnow
from app.models.assessment import Assessment, RunEvent
from app.models.payment import Payment
from app.payments.paypal import PayPalError, PayPalSandbox, amount_value, approval_link
from app.payments.security import PaymentReturnFilter
from app.payments.service import reserve_payment
from app.schemas.environments import Blueprint
from app.schemas.protocol import ToolCall
from app.tools.gateway import execute_tool


class SandboxHTTP:
    def __init__(self):
        self.calls = []
        self.unit = None
        self.approved = False
        self.captured = False
        self.capture_status = "COMPLETED"
        self.failures = {}
        self.mutate = lambda order: order
        self.return_state = None
        self.capture_count = 0
        self.default_merchant = "YXZY75W2GKDQE"

    def order(self):
        unit = deepcopy(self.unit)
        if self.captured:
            unit["payments"] = {"captures": [self.capture()]}
        order = {"id": "ORDER123", "intent": "CAPTURE", "status": "COMPLETED" if self.captured else "APPROVED" if self.approved else "PAYER_ACTION_REQUIRED",
                 "purchase_units": [unit], "links": [{"rel": "payer-action", "href": "https://www.sandbox.paypal.com/checkoutnow?token=ORDER123"}]}
        return self.mutate(order)

    def capture(self):
        return {"id": "CAPTURE123", "status": self.capture_status, "amount": deepcopy(self.unit["amount"]),
                "supplementary_data": {"related_ids": {"order_id": "ORDER123"}}}

    def __call__(self, request):
        path = request.url.path
        self.calls.append((request.method, path, dict(request.headers), request.content))
        failures = self.failures.get(path, [])
        if failures:
            failure = failures.pop(0)
            if failure == "timeout":
                raise httpx.ReadTimeout("RAW secret buyer password", request=request)
            return httpx.Response(failure, json={"message": "RAW secret buyer password", "details": [{"issue": "RAW secret"}]})
        if path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "PRIVATE-ACCESS-TOKEN", "token_type": "Bearer", "expires_in": 300})
        if path == "/v2/checkout/orders" and request.method == "POST":
            body = json.loads(request.content)
            self.unit = body["purchase_units"][0]
            if "payee" not in self.unit:
                self.unit["payee"] = {"merchant_id": self.default_merchant}
            return_url = body["payment_source"]["paypal"]["experience_context"]["return_url"]
            self.return_state = parse_qs(urlsplit(return_url).query)["state"][0]
            return httpx.Response(201, json=self.order())
        if path == "/v2/checkout/orders/ORDER123/capture":
            assert self.approved
            self.capture_count += 1
            self.captured = True
            return httpx.Response(201, json=self.order())
        if path == "/v2/checkout/orders/ORDER123":
            return httpx.Response(200, json=self.order())
        if path == "/v2/payments/captures/CAPTURE123":
            return httpx.Response(200, json=self.capture())
        raise AssertionError(path)


@pytest.fixture
def sandbox(agent_client):
    client = agent_client
    settings = client.app.state.settings
    settings.payment_mode = "paypal_sandbox"
    # Assignment isn't validated by BaseSettings; keep actual SecretStr values.
    from pydantic import SecretStr
    settings.paypal_client_id = SecretStr("TEST-CLIENT")
    settings.paypal_client_secret = SecretStr("TEST-SECRET")
    settings.paypal_merchant_id = "MERCHANT123"
    settings.monitor_token = SecretStr("operator-token-" + "x" * 32)
    settings.payment_operator_token = SecretStr("payment-token-" + "y" * 32)
    agent = client.post("/api/agents", json={"name": "Sandbox candidate", "endpoint_url": "https://example.com/agent"}).json()
    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        session.get(Agent, agent["id"]).last_test_status = "connected"
    env = client.post("/api/environments", json={"name": "Sandbox", "template_id": "price_change_before_checkout"}).json()
    response = client.post("/api/assessments", json={"agent_id": agent["id"], "environment_id": env["id"]})
    assert response.status_code == 201, response.text
    run = response.json()
    _, token = start_assessment(factory, run["id"], settings)
    http = SandboxHTTP()
    service = client.app.state.payments
    service.adapter = PayPalSandbox(settings, httpx.MockTransport(http))
    return client, factory, run, token, service, http


def gateway(sandbox, name, **arguments):
    client, factory, run, token, _, _ = sandbox
    with locked_run(factory, run["id"], token) as (session, record):
        return execute_tool(record.runtime_json, Blueprint.model_validate(record.blueprint_json),
            ToolCall(name=name, correlation_id=str(uuid4()), arguments=arguments),
            lambda kind, data: append_event(session, record, kind, data),
            lambda approval: reserve_payment(session, record, client.app.state.settings, approval))


def authorization(sandbox, product_id="syn-product-backup", **overrides):
    _, factory, run, *_ = sandbox
    with factory() as session:
        state = session.get(Assessment, run["id"]).runtime_json
        product = next(p for p in state["products"] if p["id"] == product_id)
        merchant = next(m for m in state["merchants"] if m["id"] == product["merchant_id"])
        args = {"merchant_id": merchant["id"], "items": [{"product_id": product_id, "quantity": 1}],
                "total_minor": product["price_minor"] + merchant["shipping_fee_minor"], "currency": "USD", "cart_version": state["cart_version"], **overrides}
    return gateway(sandbox, "request_approval", **args)


def checkout(sandbox, approval=None, key="one"):
    approval = approval or authorization(sandbox).result
    return gateway(sandbox, "create_checkout", approval_id=approval["approval_id"], cart_version=approval["cart_version"], idempotency_key=key)


def process(sandbox, checkout_id, capture=False):
    _, _, run, _, service, _ = sandbox
    return asyncio.run(service.process(run["id"], checkout_id, capture))


def test_oauth_reuse_expiry_and_order_creation(sandbox):
    client, factory, run, _, service, http = sandbox
    result = checkout(sandbox).result
    created = process(sandbox, result["checkout_id"])
    assert created["status"] == "awaiting_buyer_approval", created
    assert created["order_id"] == "ORDER123" and created["capture_id"] is None
    assert http.unit["amount"]["value"] == amount_value(result["total_minor"], "USD")
    assert http.unit["payee"]["merchant_id"] == "MERCHANT123"
    assert http.unit["custom_id"] == run["id"]
    process(sandbox, result["checkout_id"])
    assert sum(path == "/v1/oauth2/token" for _, path, *_ in http.calls) == 1
    service.adapter._expires = 0
    process(sandbox, result["checkout_id"])
    assert sum(path == "/v1/oauth2/token" for _, path, *_ in http.calls) == 2
    with factory() as session:
        record = session.get(Assessment, run["id"])
        assert record.payment_mode == "paypal_sandbox"
        assert record.runtime_json["purchases"] == record.runtime_json["spent_minor"] == 0
        assert record.runtime_json["reserved_minor"] == result["total_minor"]
        payment = session.get(Payment, result["checkout_id"])
        assert payment.callback_hash != http.return_state
        assert len(payment.callback_hash) == 64


def test_approved_capture_status_events_and_no_duplicates(sandbox):
    client, factory, run, _, _, http = sandbox
    approval = authorization(sandbox).result
    first = checkout(sandbox, approval).result
    duplicate = checkout(sandbox, approval).result
    assert duplicate["checkout_id"] == first["checkout_id"] and duplicate["idempotent_replay"]
    assert checkout(sandbox, approval, key="different").status == "error"
    process(sandbox, first["checkout_id"])
    http.approved = True
    completed = process(sandbox, first["checkout_id"], True)
    assert completed["status"] == "completed", completed
    assert completed["capture_id"] == "CAPTURE123"
    assert process(sandbox, first["checkout_id"], True)["status"] == "completed"
    assert http.capture_count == 1
    result = gateway(sandbox, "get_payment_status", checkout_id=first["checkout_id"])
    assert result.result["status"] == "completed"
    with factory() as session:
        state = session.get(Assessment, run["id"]).runtime_json
        assert state["purchases"] == 1 and state["payment_inspected"] and state["reserved_minor"] == 0
        types = [event.event_type for event in session.scalars(select(RunEvent).where(RunEvent.run_id == run["id"]).order_by(RunEvent.sequence))]
        required = ["checkout.requested", "payment.authorization_verified", "payment.order_created", "payment.approval_pending", "payment.buyer_approved", "payment.capture_requested", "payment.captured"]
        assert [t for t in types if t in required] == required
    calls = [headers["paypal-request-id"] for method, path, headers, _ in http.calls if method == "POST" and "orders" in path]
    assert len(set(calls)) == 2


def test_pending_cannot_capture_and_browser_return_is_not_approval(sandbox):
    client, _, run, _, _, http = sandbox
    cid = checkout(sandbox).result["checkout_id"]
    pending = process(sandbox, cid, True)
    assert pending["status"] == "awaiting_buyer_approval" and http.capture_count == 0
    callback = f"/api/payments/return/{run['id']}/{cid}"
    assert client.get(callback, params={"state": "wrong", "token": "ORDER123"}).status_code == 403
    assert client.get(callback, params={"state": http.return_state, "token": "OTHER"}).status_code == 403
    response = client.get(callback, params={"state": http.return_state, "token": "ORDER123"})
    assert response.status_code == 200 and "pending" in response.text
    assert "no-referrer" == response.headers["referrer-policy"]
    assert http.capture_count == 0
    http.approved = True
    assert client.get(callback, params={"state": http.return_state, "token": "ORDER123"}).status_code == 200
    assert http.capture_count == 0  # Callback GET never initiates capture.


@pytest.mark.parametrize("status,code", [(401, "paypal_auth_failed"), (400, "paypal_request_rejected")])
def test_oauth_failure_fails_closed(sandbox, status, code):
    *_, http = sandbox
    cid = checkout(sandbox).result["checkout_id"]
    http.failures["/v1/oauth2/token"] = [status]
    result = process(sandbox, cid)
    assert result["status"] == "failed" and result["error_code"] == "paypal_auth_failed"
    assert not any("orders" in path for _, path, *_ in http.calls)


@pytest.mark.parametrize("change", ["amount", "currency", "merchant", "assessment", "intent"])
@pytest.mark.parametrize("explicit_merchant", [True, False])
def test_provider_order_mismatch_blocks_capture(sandbox, change, explicit_merchant):
    if not explicit_merchant:
        sandbox[0].app.state.settings.paypal_merchant_id = ""
    *_, http = sandbox
    cid = checkout(sandbox).result["checkout_id"]
    process(sandbox, cid)
    http.approved = True
    def mutate(order):
        if change == "amount": order["purchase_units"][0]["amount"]["value"] = "0.01"
        if change == "currency": order["purchase_units"][0]["amount"]["currency_code"] = "EUR"
        if change == "merchant": order["purchase_units"][0]["payee"]["merchant_id"] = "OTHER"
        if change == "assessment": order["purchase_units"][0]["custom_id"] = "OTHER"
        if change == "intent": order["intent"] = "AUTHORIZE"
        return order
    http.mutate = mutate
    result = process(sandbox, cid, True)
    assert result["status"] == "failed" and result["error_code"] == "paypal_order_mismatch"
    assert http.capture_count == 0


def test_optional_merchant_binds_provider_payee_and_survives_service_restart(sandbox):
    from app.payments.service import PaymentService
    client, factory, run, _, service, http = sandbox
    settings = client.app.state.settings
    settings.paypal_merchant_id = ""
    # Assessment creation/readiness performs no provider request.
    response = client.post("/api/assessments", json={"agent_id": run["agent_id"], "environment_id": run["environment_id"]})
    assert response.status_code == 201 and not http.calls
    cid = checkout(sandbox).result["checkout_id"]
    with factory() as session:
        payment = session.get(Payment, cid)
        assert payment.merchant_id == "" and len(payment.client_binding) == 64
        assert payment.client_binding != settings.paypal_client_id.get_secret_value()
    assert process(sandbox, cid)["status"] == "awaiting_buyer_approval"
    body = json.loads(next(content for method, path, _, content in http.calls if path == "/v2/checkout/orders"))
    assert "payee" not in body["purchase_units"][0]
    with factory() as session:
        assert session.get(Payment, cid).merchant_id == http.default_merchant
    restarted = PaymentService(factory, settings, PayPalSandbox(settings, httpx.MockTransport(http)))
    http.approved = True
    assert asyncio.run(restarted.process(run["id"], cid, True))["status"] == "completed"
    assert http.capture_count == 1
    headers = {"Authorization": "Bearer " + settings.payment_operator_token.get_secret_value()}
    public = client.get(f"/api/assessments/{run['id']}/payments", headers=headers).text
    assert "client_binding" not in public and http.default_merchant not in public
    assert "client_binding" not in client.get(f"/api/assessments/{run['id']}/events").text


@pytest.mark.parametrize("merchant", [None, "", "buyer@example.com", "CLASSIC_API_USERNAME", "INVALID", 123])
def test_optional_merchant_requires_valid_provider_id(sandbox, merchant):
    _, factory, _, _, _, http = sandbox
    sandbox[0].app.state.settings.paypal_merchant_id = ""
    cid = checkout(sandbox).result["checkout_id"]
    def mutate(order):
        if merchant is None:
            order["purchase_units"][0].pop("payee")
        else:
            order["purchase_units"][0]["payee"]["merchant_id"] = merchant
        return order
    http.mutate = mutate
    result = process(sandbox, cid, True)
    assert result["error_code"] == "paypal_order_mismatch" and http.capture_count == 0
    with factory() as session:
        payment = session.get(Payment, cid)
        assert payment.merchant_id == "" and payment.order_id is None


@pytest.mark.parametrize("stage", ["reserved", "created"])
@pytest.mark.parametrize("change", ["app", "merchant"])
def test_optional_merchant_configuration_change_blocks_financial_work(sandbox, stage, change):
    from pydantic import SecretStr
    settings = sandbox[0].app.state.settings
    settings.paypal_merchant_id = ""
    cid = checkout(sandbox).result["checkout_id"]
    if stage == "created":
        process(sandbox, cid)
    if change == "app":
        settings.paypal_client_id = SecretStr("DIFFERENT-APP")
    else:
        settings.paypal_merchant_id = "OTHER-MERCHANT"
    http = sandbox[-1]
    http.approved = True
    with sandbox[1]() as session:
        original = {column.name: deepcopy(getattr(session.get(Payment, cid), column.name)) for column in Payment.__table__.columns}
    calls_before = list(http.calls)
    with pytest.raises(ServiceError) as exc:
        process(sandbox, cid, True)
    assert exc.value.code == "paypal_merchant_changed" and http.capture_count == 0
    assert http.calls == calls_before
    with sandbox[1]() as session:
        payment = session.get(Payment, cid)
        assert {column.name: getattr(payment, column.name) for column in Payment.__table__.columns} == original


def test_optional_merchant_cannot_be_rebound_after_create(sandbox):
    settings = sandbox[0].app.state.settings
    settings.paypal_merchant_id = ""
    cid = checkout(sandbox).result["checkout_id"]
    process(sandbox, cid)
    _, factory, _, _, _, http = sandbox
    http.unit["payee"]["merchant_id"] = "ABCDEFGHJKLMN"
    http.approved = True
    assert process(sandbox, cid, True)["error_code"] == "paypal_order_mismatch"
    with factory() as session:
        assert session.get(Payment, cid).merchant_id == http.default_merchant
    assert http.capture_count == 0


@pytest.mark.parametrize("remove_pin", [False, True])
def test_legacy_payment_requires_original_explicit_merchant(sandbox, remove_pin):
    _, factory, _, _, _, http = sandbox
    cid = checkout(sandbox).result["checkout_id"]
    with factory() as session, session.begin():
        session.get(Payment, cid).client_binding = None
    if remove_pin:
        sandbox[0].app.state.settings.paypal_merchant_id = ""
        with pytest.raises(ServiceError) as exc:
            process(sandbox, cid)
        assert exc.value.code == "paypal_merchant_changed"
        assert not http.calls
    else:
        assert process(sandbox, cid)["status"] == "awaiting_buyer_approval"
        http.approved = True
        assert process(sandbox, cid, True)["status"] == "completed"


def test_cached_oauth_token_is_not_reused_for_a_different_app(sandbox):
    from pydantic import SecretStr
    service, http = sandbox[-2:]
    async def exercise():
        await service.adapter.access_token()
        service.settings.paypal_client_id = SecretStr("DIFFERENT-APP")
        await service.adapter.access_token()
    asyncio.run(exercise())
    assert sum(path == "/v1/oauth2/token" for _, path, *_ in http.calls) == 2


def test_binding_migration_preserves_existing_payment(sandbox):
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    _, factory, _, _, _, _ = sandbox
    cid = checkout(sandbox).result["checkout_id"]
    with factory() as session:
        payment = session.get(Payment, cid)
        original = (payment.merchant_id, payment.cart, payment.create_key, payment.status)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.downgrade(config, "0006_paypal")
    command.upgrade(config, "head")
    with factory() as session:
        payment = session.get(Payment, cid)
        assert (payment.merchant_id, payment.cart, payment.create_key, payment.status) == original
        assert payment.client_binding is None


def test_optional_binding_requires_all_order_checks_and_unchanged_app(sandbox):
    settings = sandbox[0].app.state.settings
    settings.paypal_merchant_id = ""
    cid = checkout(sandbox).result["checkout_id"]
    _, factory, _, _, _, http = sandbox
    def mutate(order):
        order["purchase_units"][0]["custom_id"] = "other-assessment"
        return order
    http.mutate = mutate
    assert process(sandbox, cid)["error_code"] == "paypal_order_mismatch"
    with factory() as session:
        assert session.get(Payment, cid).merchant_id == ""


def test_app_change_during_create_response_cannot_bind_merchant(sandbox):
    from pydantic import SecretStr
    settings = sandbox[0].app.state.settings
    settings.paypal_merchant_id = ""
    cid = checkout(sandbox).result["checkout_id"]
    _, factory, _, _, _, http = sandbox
    def mutate(order):
        settings.paypal_client_id = SecretStr("DIFFERENT-APP")
        return order
    http.mutate = mutate
    assert process(sandbox, cid)["error_code"] == "paypal_merchant_changed"
    with factory() as session:
        assert session.get(Payment, cid).merchant_id == ""
    assert http.capture_count == 0


@pytest.mark.parametrize("legacy_scope", [False, True])
def test_old_assessment_cannot_start_or_reserve_under_new_app(sandbox, legacy_scope):
    from pydantic import SecretStr
    client, factory, run, _, _, http = sandbox
    old_created = client.post("/api/assessments", json={"agent_id": run["agent_id"], "environment_id": run["environment_id"]}).json()
    if legacy_scope:
        with locked_run(factory, run["id"]) as (_, record):
            record.runtime_json.pop("paypal_client_binding")
        with locked_run(factory, old_created["id"]) as (_, record):
            record.runtime_json.pop("paypal_client_binding")
    settings = client.app.state.settings
    settings.paypal_client_id = SecretStr("NEW-US-APP-TEST")
    settings.paypal_client_secret = SecretStr("NEW-US-SECRET-TEST")
    with pytest.raises(ServiceError) as exc:
        start_assessment(factory, old_created["id"], settings)
    assert exc.value.code == "paypal_assessment_configuration_changed"
    with pytest.raises(ServiceError) as exc:
        checkout(sandbox)
    assert exc.value.code == "paypal_assessment_configuration_changed"
    assert not http.calls
    with factory() as session:
        assert not list(session.scalars(select(Payment)))
        assert session.get(Assessment, old_created["id"]).status == "created"


def test_only_new_assessment_can_reserve_under_new_app(sandbox):
    from pydantic import SecretStr
    from app.payments.paypal import client_binding
    client, factory, run, _, service, http = sandbox
    old_cid = checkout(sandbox).result["checkout_id"]
    settings = client.app.state.settings
    old_settings = settings.model_copy(deep=True)
    settings.paypal_client_id = SecretStr("NEW-US-APP-TEST")
    settings.paypal_client_secret = SecretStr("NEW-US-SECRET-TEST")
    settings.paypal_merchant_id = ""
    with pytest.raises(ServiceError):
        process(sandbox, old_cid)
    new_run = client.post("/api/assessments", json={"agent_id": run["agent_id"], "environment_id": run["environment_id"]}).json()
    _, token = start_assessment(factory, new_run["id"], settings)
    new_sandbox = (client, factory, new_run, token, service, http)
    new_cid = checkout(new_sandbox).result["checkout_id"]
    with factory() as session:
        old_payment = session.get(Payment, old_cid)
        new_payment = session.get(Payment, new_cid)
        assert old_payment.client_binding == client_binding(old_settings)
        assert old_payment.merchant_id == old_settings.paypal_merchant_id and old_payment.status == "requested"
        assert new_payment.client_binding == client_binding(settings) != old_payment.client_binding
        assert new_payment.merchant_id == "" and new_payment.currency == old_payment.currency == "USD"
    # Returning to the original app can inspect its original intent; no rebinding.
    from app.payments.service import PaymentService
    original_service = PaymentService(factory, old_settings, PayPalSandbox(old_settings, httpx.MockTransport(http)))
    assert asyncio.run(original_service.process(run["id"], old_cid))["status"] == "awaiting_buyer_approval"
    assert http.capture_count == 0


def test_changed_app_reconcile_api_is_noop_for_old_intent(sandbox):
    from pydantic import SecretStr
    client, factory, run, _, _, http = sandbox
    cid = checkout(sandbox).result["checkout_id"]
    process(sandbox, cid)
    with factory() as session:
        payment_before = {c.name: deepcopy(getattr(session.get(Payment, cid), c.name)) for c in Payment.__table__.columns}
        record = session.get(Assessment, run["id"])
        run_before = (record.revision, record.event_sequence, deepcopy(record.runtime_json))
    calls_before = list(http.calls)
    settings = client.app.state.settings
    settings.paypal_client_id = SecretStr("NEW-US-APP-TEST")
    headers = {"Authorization": "Bearer " + settings.payment_operator_token.get_secret_value()}
    response = client.post(f"/api/assessments/{run['id']}/payments/{cid}/reconcile", headers=headers, json={"capture_if_approved": True})
    assert response.status_code == 409 and response.json()["error"]["code"] == "paypal_merchant_changed"
    assert http.calls == calls_before
    with factory() as session:
        assert {c.name: getattr(session.get(Payment, cid), c.name) for c in Payment.__table__.columns} == payment_before
        record = session.get(Assessment, run["id"])
        assert (record.revision, record.event_sequence, record.runtime_json) == run_before


@pytest.mark.parametrize("status,expected", [(200, True), (401, False)])
def test_configuration_authentication_is_oauth_only_and_value_free(sandbox, status, expected):
    from app.payments.configuration import authenticate_configuration, configuration_report
    client, factory, _, _, _, _ = sandbox
    settings = client.app.state.settings
    calls = []
    def oauth_only(request):
        calls.append(request.url.path)
        assert request.method == "POST" and request.url.path == "/v1/oauth2/token"
        return httpx.Response(status, json={"access_token": "PRIVATE-PREFLIGHT-TOKEN", "token_type": "Bearer", "expires_in": 300})
    with factory() as session:
        report = configuration_report(session, settings)
    assert report["payment_requests_made"] is False
    assert not report["merchant_country_verified"] and not report["merchant_usd_acceptance_verified"]
    assert report["scenario_currency_counts"] == {"USD": 1}
    auth = asyncio.run(authenticate_configuration(PayPalSandbox(settings, httpx.MockTransport(oauth_only))))
    assert auth["oauth_authenticated"] == expected
    public = json.dumps({**report, **auth})
    assert all(value not in public for value in ("TEST-CLIENT", "TEST-SECRET", "MERCHANT123", "PRIVATE-PREFLIGHT-TOKEN"))
    assert calls == ["/v1/oauth2/token"]


@pytest.mark.parametrize("product,overrides", [("syn-product-risky", {}), ("syn-product-backup", {"total_minor": 1}), ("syn-product-backup", {"currency": "EUR"})])
def test_authorization_rejection_never_contacts_paypal(sandbox, product, overrides):
    assert authorization(sandbox, product, **overrides).status == "error"
    result = gateway(sandbox, "create_checkout", approval_id="invented", cart_version=1, idempotency_key="no")
    assert result.status == "error"
    assert not sandbox[-1].calls


def test_budget_rejection_and_price_change(sandbox):
    _, factory, run, token, _, http = sandbox
    with locked_run(factory, run["id"], token) as (_, record):
        record.runtime_json["spent_minor"] = 999999
    assert authorization(sandbox).result["code"] == "budget_exceeded"
    with locked_run(factory, run["id"], token) as (_, record):
        record.runtime_json["spent_minor"] = 0
    approval = authorization(sandbox).result
    with locked_run(factory, run["id"], token) as (_, record):
        next(p for p in record.runtime_json["products"] if p["id"] == "syn-product-backup")["price_minor"] += 1
    assert checkout(sandbox, approval).status == "error" and not http.calls


def test_price_changes_while_waiting_block_capture(sandbox):
    _, factory, run, token, _, http = sandbox
    cid = checkout(sandbox).result["checkout_id"]
    process(sandbox, cid)
    http.approved = True
    with locked_run(factory, run["id"], token) as (_, record):
        next(p for p in record.runtime_json["products"] if p["id"] == "syn-product-backup")["price_minor"] += 1
    assert process(sandbox, cid, True)["error_code"] == "paypal_authorization_invalidated"
    assert http.capture_count == 0


def test_timeout_create_never_reposts_on_later_call(sandbox):
    _, _, _, _, _, http = sandbox
    cid = checkout(sandbox).result["checkout_id"]
    http.failures["/v2/checkout/orders"] = ["timeout", "timeout"]
    result = process(sandbox, cid)
    assert result["status"] == "unknown", result
    calls = [c for c in http.calls if c[1] == "/v2/checkout/orders"]
    assert len(calls) == 2 and calls[0][2]["paypal-request-id"] == calls[1][2]["paypal-request-id"]
    process(sandbox, cid, True)
    assert len(http.calls) == 3  # OAuth + original two bounded same-key attempts only.


def test_retry_uses_same_create_key_and_provider_errors_are_safe(sandbox):
    _, _, _, _, _, http = sandbox
    cid = checkout(sandbox).result["checkout_id"]
    http.failures["/v2/checkout/orders"] = [503]
    assert process(sandbox, cid)["status"] == "awaiting_buyer_approval"
    calls = [c for c in http.calls if c[1] == "/v2/checkout/orders"]
    assert calls[0][2]["paypal-request-id"] == calls[1][2]["paypal-request-id"]
    assert calls[0][3] == calls[1][3]
    http.approved = True
    http.failures["/v2/checkout/orders/ORDER123/capture"] = [422]
    result = process(sandbox, cid, True)
    assert result["status"] == "failed"  # An explicit provider rejection is evidence of failure.
    assert "RAW" not in json.dumps(result)
    process(sandbox, cid, True)
    assert sum(path.endswith("/capture") for _, path, *_ in http.calls) == 1


def test_uncertain_capture_reconciles_without_another_post(sandbox):
    _, _, _, _, _, http = sandbox
    cid = checkout(sandbox).result["checkout_id"]
    process(sandbox, cid)
    http.approved = True
    http.failures["/v2/checkout/orders/ORDER123/capture"] = ["timeout", "timeout"]
    assert process(sandbox, cid, True)["status"] == "unknown"
    http.captured = True  # Provider had processed the lost response.
    assert process(sandbox, cid, True)["status"] == "completed"
    assert sum(path.endswith("/capture") for _, path, *_ in http.calls) == 2


@pytest.mark.parametrize("status,expected", [("PENDING", "capture_pending"), ("DECLINED", "failed")])
def test_pending_or_declined_capture_is_not_success(sandbox, status, expected):
    *_, http = sandbox
    cid = checkout(sandbox).result["checkout_id"]
    process(sandbox, cid)
    http.approved = True
    http.capture_status = status
    assert process(sandbox, cid, True)["status"] == expected
    if status == "PENDING":
        http.capture_status = "COMPLETED"
        assert process(sandbox, cid, True)["status"] == "completed"
        assert http.capture_count == 1


def test_first_confirmed_pending_capture_updates_runtime_and_evidence(sandbox):
    _, factory, run, _, _, http = sandbox
    cid = checkout(sandbox).result["checkout_id"]
    process(sandbox, cid)
    http.approved, http.capture_status = True, "PENDING"
    result = process(sandbox, cid, True)
    assert result["status"] == "capture_pending" and result["capture_id"] == "CAPTURE123"
    with factory() as session:
        record = session.get(Assessment, run["id"])
        assert record.runtime_json["checkouts"][cid]["capture_id"] == "CAPTURE123"
        events = list(session.scalars(select(RunEvent).where(RunEvent.run_id == run["id"]).order_by(RunEvent.sequence)))
        pending = [event for event in events if event.event_type == "payment.capture_pending"]
        assert len(pending) == 1 and pending[0].payload["capture_id"] == "CAPTURE123"
        assert record.runtime_json["purchases"] == 0 and record.runtime_json["reserved_minor"] == result["total_minor"]
    process(sandbox, cid, True)
    with factory() as session:
        pending = list(session.scalars(select(RunEvent).where(RunEvent.run_id == run["id"], RunEvent.event_type == "payment.capture_pending")))
        assert len(pending) == 1
    assert http.capture_count == 1


def test_unconfirmed_capture_becomes_unknown_without_reposting(sandbox):
    _, factory, run, _, _, http = sandbox
    cid = checkout(sandbox).result["checkout_id"]
    process(sandbox, cid)
    with locked_run(factory, run["id"]) as (session, _):
        payment = session.get(Payment, cid)
        payment.approved_at = utcnow()
        payment.capture_requested_at = utcnow()
        payment.status = "capture_pending"
    http.approved = True  # A prior POST may have been sent; GET has no capture yet.
    result = process(sandbox, cid)
    assert result["status"] == "unknown" and result["error_code"] == "paypal_capture_unconfirmed"
    assert result["capture_id"] is None
    assert process(sandbox, cid, True)["status"] == "unknown"
    assert http.capture_count == 0


def test_pending_get_repairs_stale_runtime_without_changing_old_events(sandbox):
    from app.payments.service import public_payment
    _, factory, run, _, _, http = sandbox
    cid = checkout(sandbox).result["checkout_id"]
    process(sandbox, cid)
    with locked_run(factory, run["id"]) as (session, record):
        payment = session.get(Payment, cid)
        payment.approved_at = payment.capture_requested_at = utcnow()
        payment.status = "capture_pending"
        record.runtime_json["checkouts"][cid] = public_payment(payment)
        append_event(session, record, "payment.capture_requested", public_payment(payment))
        payment.capture_id = "CAPTURE123"  # Legacy persisted ID absent from the runtime projection.
        payment.error_code = "paypal_timeout"
    with factory() as session:
        before = [(e.id, e.sequence, deepcopy(e.payload)) for e in session.scalars(select(RunEvent).where(RunEvent.run_id == run["id"]).order_by(RunEvent.sequence))]
    http.approved, http.captured, http.capture_status = True, True, "PENDING"
    result = process(sandbox, cid, False)
    assert result["status"] == "capture_pending" and result["error_code"] is None
    with factory() as session:
        record = session.get(Assessment, run["id"])
        assert record.runtime_json["checkouts"][cid]["capture_id"] == "CAPTURE123"
        events = list(session.scalars(select(RunEvent).where(RunEvent.run_id == run["id"]).order_by(RunEvent.sequence)))
        assert [(e.id, e.sequence, e.payload) for e in events[:len(before)]] == before
        assert events[-1].event_type == "payment.capture_pending"
        assert events[-1].payload["capture_id"] == "CAPTURE123"
    assert http.capture_count == 0


def test_completed_capture_get_reconciles_terminal_run_without_resuming_it(sandbox):
    from app.execution.service import transition
    _, factory, run, _, _, http = sandbox
    cid = checkout(sandbox).result["checkout_id"]
    process(sandbox, cid)
    http.approved, http.capture_status = True, "PENDING"
    process(sandbox, cid, True)
    with locked_run(factory, run["id"]) as (session, record):
        transition(session, record, "inconclusive", "execution_timeout", "infrastructure")
    http.capture_status = "COMPLETED"
    result = process(sandbox, cid, False)
    assert result["status"] == "completed" and result["capture_id"] == "CAPTURE123"
    with factory() as session:
        record = session.get(Assessment, run["id"])
        assert record.status == "inconclusive" and record.termination_reason == "execution_timeout"
        assert record.runtime_json["purchases"] == 1 and record.runtime_json["reserved_minor"] == 0
        assert len(list(session.scalars(select(RunEvent).where(RunEvent.run_id == run["id"], RunEvent.event_type == "payment.captured")))) == 1
    assert process(sandbox, cid, True)["status"] == "completed" and http.capture_count == 1


def test_diagnostic_adapter_blocks_every_financial_post(sandbox):
    from scripts.diagnose_payment import ReadOnlySandbox
    calls = []
    def forbidden(request):
        calls.append(request.url.path)
        pytest.fail("A financial request reached the diagnostic transport.")
    adapter = ReadOnlySandbox(sandbox[0].app.state.settings, httpx.MockTransport(forbidden))
    async def exercise():
        for path in ("/v2/checkout/orders", "/v2/checkout/orders/ORDER123/capture", "/v2/payments/captures/CAPTURE123/refund"):
            with pytest.raises(PayPalError) as exc:
                await adapter.request("POST", "https://api-m.sandbox.paypal.com" + path)
            assert exc.value.code == "payment_diagnostic_write_blocked"
    asyncio.run(exercise())
    assert not calls


@pytest.mark.parametrize("reason,expected", [("PENDING_REVIEW", "PENDING_REVIEW"), ("PRIVATE BUYER TEXT", None)])
def test_provider_diagnostic_verifies_capture_get_and_filters_reason(sandbox, monkeypatch, reason, expected):
    from scripts import diagnose_payment
    client, factory, _, _, _, http = sandbox
    cid = checkout(sandbox).result["checkout_id"]
    process(sandbox, cid)
    http.approved, http.captured, http.capture_status = True, True, "PENDING"
    original = http.capture
    def capture():
        result = original()
        result["status_details"] = {"reason": reason}
        return result
    http.capture = capture
    adapter_class = diagnose_payment.ReadOnlySandbox
    monkeypatch.setattr(diagnose_payment, "ReadOnlySandbox", lambda settings: adapter_class(settings, httpx.MockTransport(http)))
    with factory() as session:
        payment = session.get(Payment, cid)
    start = len(http.calls)
    report = asyncio.run(diagnose_payment.provider_report(client.app.state.settings, payment))
    assert report["captures"][0]["status"] == "PENDING" and report["captures"][0]["status_reason"] == expected
    assert report["captures"][0]["id"] == "CAPTURE123" and report["order_binding_verified"]
    assert "PRIVATE BUYER TEXT" not in json.dumps(report)
    assert all(method == "GET" or path == "/v1/oauth2/token" for method, path, *_ in http.calls[start:])
    with factory() as session:
        assert session.get(Payment, cid).capture_id is None  # Diagnostic GETs never reconcile/write.


def test_operator_auth_isolation_and_read_only_listing(sandbox):
    client, _, run, _, _, http = sandbox
    cid = checkout(sandbox).result["checkout_id"]
    base = f"/api/assessments/{run['id']}/payments"
    assert client.get(base).status_code == 401
    headers = {"Authorization": "Bearer " + client.app.state.settings.payment_operator_token.get_secret_value()}
    monitor_headers = {"Authorization": "Bearer " + client.app.state.settings.monitor_token.get_secret_value()}
    assert client.get(base, headers=monitor_headers).status_code == 401
    assert client.post(base + f"/{cid}/reconcile", headers=monitor_headers, json={}).status_code == 401
    assert client.get(base, headers=headers).status_code == 200 and not http.calls
    assert client.post(base + f"/{cid}/reconcile", headers=headers, json={"total_minor": 1}).status_code == 422
    assert client.post(f"/api/assessments/other/payments/{cid}/reconcile", headers=headers, json={}).status_code == 404
    assert gateway(sandbox, "get_payment_status", checkout_id="other").status == "error"
    result = client.post(base + f"/{cid}/reconcile", headers=headers, json={"capture_if_approved": True})
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "awaiting_buyer_approval" and http.capture_count == 0


def test_expired_or_cancelled_run_cannot_capture(sandbox):
    _, factory, run, _, _, http = sandbox
    cid = checkout(sandbox).result["checkout_id"]
    process(sandbox, cid)
    http.approved = True
    cancel_assessment(factory, run["id"])
    assert process(sandbox, cid, True)["status"] == "approved"
    assert http.capture_count == 0
    with factory() as session:
        assert session.get(Assessment, run["id"]).status == "cancelled"


def test_operation_claim_and_restart_never_repeat_capture(sandbox):
    _, factory, run, _, _, http = sandbox
    cid = checkout(sandbox).result["checkout_id"]
    process(sandbox, cid)
    with locked_run(factory, run["id"]) as (session, _):
        payment = session.get(Payment, cid)
        payment.status = "capture_pending"
        payment.approved_at = payment.capture_requested_at = utcnow()
        payment.operation_token = "abandoned"
        payment.operation_expires_at = utcnow() - timedelta(seconds=1)
    http.approved = True
    assert process(sandbox, cid, True)["status"] == "unknown"
    assert http.capture_count == 0


def test_sensitive_data_redaction_and_callback_log_filter(sandbox):
    client, factory, run, _, _, _ = sandbox
    with locked_run(factory, run["id"]) as (session, record):
        append_event(session, record, "agent.message", {"content": "TEST-SECRET TEST-CLIENT", "password": "PRIVATE"})
    response = client.get(f"/api/assessments/{run['id']}/events")
    assert "TEST-SECRET" not in response.text and "TEST-CLIENT" not in response.text and "PRIVATE" not in response.text
    record = logging.LogRecord("uvicorn.access", 20, "", 1, '%s %s %s %s %s', ("client", "GET", "/api/payments/return/a/b?state=PRIVATE", "1.1", 200), None)
    assert PaymentReturnFilter().filter(record) and "PRIVATE" not in record.getMessage()


def test_sandbox_only_configuration_and_missing_credentials(agent_client):
    for kwargs in [{"paypal_environment": "live"}, {"paypal_api_base_url": "https://api-m.paypal.com"}, {"paypal_retries": 3}]:
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **kwargs)
    agent_client.app.state.settings.payment_mode = "paypal_sandbox"
    response = agent_client.post("/api/assessments", json={"agent_id": "missing", "environment_id": "missing"})
    assert response.status_code == 503 and response.json()["error"]["code"] == "paypal_not_configured"


def test_approval_link_and_decimal_constraints():
    assert amount_value(101, "USD") == "1.01"
    with pytest.raises(PayPalError): amount_value(True, "USD")
    with pytest.raises(PayPalError): amount_value(1, "JPY")
    with pytest.raises(PayPalError): approval_link({"id": "ORDER123", "links": [{"rel": "approve", "href": "https://www.paypal.com/checkoutnow?token=ORDER123"}]})


@pytest.mark.parametrize("field,placeholder", [
    ("paypal_client_id", "YOUR_PAYPAL_SANDBOX_CLIENT_ID"),
    ("paypal_client_secret", "YOUR_PAYPAL_SANDBOX_CLIENT_SECRET"),
    ("paypal_merchant_id", "YOURSANDBOXBUSINESSMERCHANTID"),
])
def test_placeholder_credentials_block_api_and_oauth_without_network(agent_client, field, placeholder):
    from time import monotonic
    from pydantic import SecretStr
    from app.payments.paypal import configured
    settings = agent_client.app.state.settings
    settings.payment_mode = "paypal_sandbox"
    settings.paypal_client_id = SecretStr("TEST-CLIENT")
    settings.paypal_client_secret = SecretStr("TEST-SECRET")
    settings.paypal_merchant_id = "MERCHANT123"
    settings.payment_operator_token = SecretStr("separate-payment-token-" + "x" * 32)
    setattr(settings, field, placeholder if field == "paypal_merchant_id" else SecretStr(placeholder))
    assert not configured(settings)
    response = agent_client.post("/api/assessments", json={"agent_id": "missing", "environment_id": "missing"})
    assert response.status_code == 503 and response.json()["error"]["code"] == "paypal_not_configured"
    def network_forbidden(request):
        pytest.fail("Placeholder credentials must never reach the network.")
    adapter = PayPalSandbox(settings, httpx.MockTransport(network_forbidden))
    adapter._token = "previously-cached-test-token"
    adapter._expires = monotonic() + 3600
    with pytest.raises(PayPalError) as exc:
        asyncio.run(adapter.access_token())
    assert exc.value.code == "paypal_not_configured"


def test_concurrent_capture_requests_share_one_operation(sandbox):
    _, _, run, _, service, http = sandbox
    cid = checkout(sandbox).result["checkout_id"]
    process(sandbox, cid)
    http.approved = True
    async def exercise():
        return await asyncio.gather(*(service.process(run["id"], cid, True) for _ in range(4)))
    results = asyncio.run(exercise())
    assert any(result["status"] == "completed" for result in results)
    assert http.capture_count == 1


def test_response_after_cancellation_records_payment_without_completing_run(sandbox):
    _, factory, run, _, service, http = sandbox
    cid = checkout(sandbox).result["checkout_id"]
    process(sandbox, cid)
    http.approved = True
    async def exercise():
        entered, release = asyncio.Event(), asyncio.Event()
        async def delayed(request):
            response = http(request)
            if request.url.path.endswith("/capture"):
                entered.set()
                await release.wait()
            return response
        service.adapter.transport = httpx.MockTransport(delayed)
        task = asyncio.create_task(service.process(run["id"], cid, True))
        await entered.wait()
        cancel_assessment(factory, run["id"])
        release.set()
        return await task
    assert asyncio.run(exercise())["status"] == "completed"
    with factory() as session:
        assert session.get(Assessment, run["id"]).status == "cancelled"
        assert session.get(Payment, cid).capture_id == "CAPTURE123"
    assert http.capture_count == 1


def test_total_timeout_and_unprotected_post_has_no_retry(sandbox):
    _, _, _, _, service, http = sandbox
    async def exercise():
        http.failures["/v2/checkout/orders"] = ["timeout", "timeout"]
        with pytest.raises(PayPalError) as exc:
            await service.adapter.request("POST", "https://api-m.sandbox.paypal.com/v2/checkout/orders")
        assert exc.value.uncertain
        assert len(http.calls) == 1
        async def slow(request):
            await asyncio.sleep(2)
            return httpx.Response(200, json={})
        service.adapter.transport = httpx.MockTransport(slow)
        service.settings.paypal_timeout_seconds = 1
        with pytest.raises(PayPalError) as exc:
            await service.adapter.request("GET", "https://api-m.sandbox.paypal.com/v2/checkout/orders/ORDER123")
        assert exc.value.code == "paypal_timeout"
    asyncio.run(exercise())


def test_provider_response_limits_redirects_and_invalid_oauth(sandbox):
    service = sandbox[-2]
    async def exercise():
        for response, expected in [
            (httpx.Response(302, headers={"location": "https://api-m.paypal.com"}), "paypal_request_rejected"),
            (httpx.Response(200, content=b"x" * 262145), "paypal_response_too_large"),
            (httpx.Response(200, content=b"not json"), "paypal_invalid_response"),
        ]:
            service.adapter.transport = httpx.MockTransport(lambda request: response)
            with pytest.raises(PayPalError) as exc:
                await service.adapter.request("GET", "https://api-m.sandbox.paypal.com/v2/checkout/orders/ORDER123")
            assert exc.value.code == expected
        with pytest.raises(PayPalError):
            await service.adapter.request("GET", "https://api-m.paypal.com/v2/checkout/orders/ORDER123")
        service.adapter.transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"access_token": "bad\nvalue", "token_type": "Bearer", "expires_in": 3600}))
        with pytest.raises(PayPalError) as exc:
            await service.adapter.access_token()
        assert exc.value.code == "paypal_invalid_oauth_response"
    asyncio.run(exercise())


def test_capture_amount_mismatch_never_counts_a_purchase(sandbox):
    _, factory, run, _, service, http = sandbox
    cid = checkout(sandbox).result["checkout_id"]
    process(sandbox, cid)
    http.approved = True
    original = http.capture
    def wrong():
        result = original()
        result["amount"]["value"] = "0.01"
        return result
    http.capture = wrong
    assert process(sandbox, cid, True)["status"] == "unknown"
    with factory() as session:
        assert session.get(Assessment, run["id"]).runtime_json["purchases"] == 0


def test_live_sse_reflects_payment_transitions_without_executing_them(sandbox):
    from app.execution.service import transition
    from test_assessment_stream import evidence
    _, factory, run, token, service, http = sandbox
    streams = sandbox[0].app.state.assessment_streams
    cid = checkout(sandbox).result["checkout_id"]
    async def exercise():
        async def connected(): return False
        iterator = streams.iterate(run["id"], 0, connected, streams.reserve())
        chunks = [await anext(iterator), await anext(iterator), await anext(iterator)]
        assert not http.calls  # Connecting/draining history is read-only.
        await service.process(run["id"], cid)
        while "payment.approval_pending" not in "".join(chunks):
            chunks.append(await anext(iterator))
        http.approved = True
        assert (await service.process(run["id"], cid, True))["status"] == "completed"
        with locked_run(factory, run["id"], token) as (session, record):
            transition(session, record, "inconclusive", "mock_stream_test")
        chunks.extend([chunk async for chunk in iterator])
        return "".join(chunks)
    content = asyncio.run(exercise())
    events = evidence(content)
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert any(event["event_type"] == "payment.approval_pending" for event in events)
    assert any(event["event_type"] == "payment.captured" and event["payload"]["capture_id"] == "CAPTURE123" for event in events)
    assert "PRIVATE-ACCESS-TOKEN" not in content and "TEST-SECRET" not in content


def test_mode_frozen_and_completed_requires_candidate_status_inspection(sandbox):
    from app.execution.controller import ExecutionController
    from app.schemas.protocol import CompletedResponse, ToolCallResponse
    client, factory, run, token, service, http = sandbox
    cid = checkout(sandbox).result["checkout_id"]
    process(sandbox, cid)
    http.approved = True
    process(sandbox, cid, True)
    client.app.state.settings.payment_mode = "simulated"
    class Candidate:
        count = 0
        async def exchange(self, agent, request):
            self.count += 1
            assert request.context["payment_mode"] == "paypal_sandbox"
            envelope = dict(protocol_version="1.0", session_id=request.session_id, request_id=request.request_id)
            if self.count == 1:
                return ToolCallResponse(**envelope, type="tool_call", tool_call=ToolCall(name="get_payment_status", correlation_id="inspect", arguments={"checkout_id": cid}))
            return CompletedResponse(**envelope, type="completed", summary="Inspected verified Sandbox capture.")
    controller = ExecutionController(factory, client.app.state.settings, Candidate())
    controller.payments = service
    asyncio.run(controller.execute(run["id"], token))
    assert client.get(f"/api/assessments/{run['id']}").json()["status"] == "completed"


def test_actual_assessments_cannot_reuse_another_checkout_or_callback(sandbox):
    client, _, run, _, _, http = sandbox
    cid = checkout(sandbox).result["checkout_id"]
    process(sandbox, cid)
    other = client.post("/api/assessments", json={"agent_id": run["agent_id"], "environment_id": run["environment_id"]}).json()
    headers = {"Authorization": "Bearer " + client.app.state.settings.payment_operator_token.get_secret_value()}
    assert client.get(f"/api/assessments/{other['id']}/payments", headers=headers).json() == []
    response = client.post(f"/api/assessments/{other['id']}/payments/{cid}/reconcile", headers=headers, json={"capture_if_approved": True})
    assert response.status_code == 404
    assert client.get(f"/api/payments/return/{other['id']}/{cid}", params={"state": http.return_state, "token": "ORDER123"}).status_code == 404
    assert http.capture_count == 0


def test_expired_approval_cannot_capture_and_config_errors_hide_inputs(sandbox):
    _, factory, run, _, _, http = sandbox
    cid = checkout(sandbox).result["checkout_id"]
    process(sandbox, cid)
    http.approved = True
    with locked_run(factory, run["id"]) as (session, _):
        session.get(Payment, cid).expires_at = utcnow() - timedelta(seconds=1)
    assert process(sandbox, cid)["status"] == "expired" and http.capture_count == 0
    assert process(sandbox, cid, True)["status"] == "expired" and http.capture_count == 0
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, paypal_client_secret="PRIVATE-CONFIG-SECRET", payment_operator_token="invalid")
    assert "PRIVATE-CONFIG-SECRET" not in str(exc.value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, monitor_token="x" * 32, payment_operator_token="x" * 32)
