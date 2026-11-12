"""Durable intent, single-operation claims, and server-verified Sandbox lifecycle."""
from copy import deepcopy
from datetime import timedelta, timezone
from hashlib import sha256
import re
from secrets import compare_digest, token_urlsafe
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import Settings
from app.core.domain_errors import ServiceError
from app.events.store import append_event
from app.execution.service import locked_run
from app.models.agent import utcnow
from app.models.assessment import Assessment
from app.models.payment import Payment
from app.payments.paypal import PayPalError, PayPalSandbox, approval_link, client_binding, configured, matches_amount

FINAL = {"completed", "failed", "expired"}


def public_payment(payment: Payment, operator: bool = False) -> dict:
    result = {"checkout_id": payment.id, "provider": "paypal_sandbox", "payment_mode": payment.mode,
              "status": payment.status, "merchant_id": payment.cart["merchant_id"],
              "items": payment.cart["items"], "total_minor": payment.amount_minor, "currency": payment.currency,
              "order_id": payment.order_id, "capture_id": payment.capture_id, "error_code": payment.error_code}
    if operator:
        result.update(approval_url=payment.approval_url if payment.status == "awaiting_buyer_approval" else None,
                      created_at=payment.created_at.isoformat(), updated_at=payment.updated_at.isoformat(),
                      expires_at=payment.expires_at.isoformat())
    return result


def find_payment(session: Session, run_id: str, checkout_id: str) -> Payment:
    payment = session.get(Payment, checkout_id)
    if payment is None or payment.run_id != run_id:
        raise ServiceError(404, "checkout_not_found", "Checkout not found in this assessment.")
    return payment


def reserve_payment(session: Session, run: Assessment, settings: Settings, approval: dict) -> dict:
    # Called exclusively by the gateway, after its complete policy/challenge checks.
    if run.payment_mode != "paypal_sandbox" or not configured(settings):
        raise ServiceError(503, "paypal_not_configured", "PayPal Sandbox and operator access must be configured.")
    if run.runtime_json.get("paypal_client_binding") != client_binding(settings):
        raise ServiceError(409, "paypal_assessment_configuration_changed", "Create a new Sandbox assessment after validating the current app configuration.")
    now = utcnow()
    payment = Payment(id=str(uuid4()), run_id=run.id, mode=run.payment_mode,
        approval_id=approval["approval_id"], cart=deepcopy(approval), merchant_id=settings.paypal_merchant_id,
        client_binding=client_binding(settings),
        amount_minor=approval["total_minor"], currency=approval["currency"], status="requested",
        callback_hash="", create_key=str(uuid4()), capture_key=str(uuid4()),
        created_at=now, updated_at=now, expires_at=now + timedelta(seconds=settings.paypal_approval_wait_seconds))
    session.add(payment)
    return public_payment(payment)


def evidence(session: Session, run: Assessment, payment: Payment, kind: str) -> None:
    payment.updated_at = utcnow()
    run.runtime_json["checkouts"][payment.id] = public_payment(payment)
    append_event(session, run, kind, public_payment(payment))


def verify_cart(run: Assessment, payment: Payment) -> None:
    # Restore only this intent's reservation for the normal authoritative checks.
    from app.schemas.environments import Blueprint
    from app.tools.gateway import PolicyDenied, cart_fingerprint, checked_cart
    state = deepcopy(run.runtime_json)
    state["reserved_minor"] = max(0, state.get("reserved_minor", 0) - payment.amount_minor)
    state["reserved_purchases"] = max(0, state.get("reserved_purchases", 0) - 1)
    approval = state["approvals"].get(payment.approval_id)
    if not approval or approval["status"] != "consumed":
        raise PayPalError("paypal_authorization_invalidated")
    try:
        cart = checked_cart(state, Blueprint.model_validate(run.blueprint_json), payment.cart)
        if cart_fingerprint(cart) != payment.cart["fingerprint"]:
            raise PayPalError("paypal_authorization_invalidated")
    except PolicyDenied:
        raise PayPalError("paypal_authorization_invalidated") from None


def verify_merchant_configuration(payment: Payment, settings: Settings) -> None:
    if not configured(settings):
        raise PayPalError("paypal_not_configured")
    if payment.client_binding is not None:
        if payment.client_binding != client_binding(settings):
            raise PayPalError("paypal_merchant_changed")
        if settings.paypal_merchant_id and payment.merchant_id != settings.paypal_merchant_id:
            raise PayPalError("paypal_merchant_changed")
    elif not settings.paypal_merchant_id or payment.merchant_id != settings.paypal_merchant_id:
        # Legacy intents have no app binding: retain their explicit merchant pin.
        raise PayPalError("paypal_merchant_changed")


def verify_order(order: dict, payment: Payment, bind_merchant: bool = False) -> None:
    try:
        PayPalSandbox.check_id(order["id"])
        units = order["purchase_units"]
        unit = units[0]
        merchant = unit["payee"]["merchant_id"]
        may_bind = (bind_merchant and payment.order_id is None and not payment.merchant_id
                    and payment.client_binding is not None)
        merchant_matches = (isinstance(merchant, str) and re.fullmatch(r"[2-9A-HJ-NP-Z]{13}", merchant)
                            if may_bind else payment.merchant_id and merchant == payment.merchant_id)
        valid = (len(units) == 1 and order["intent"] == "CAPTURE"
                 and (payment.order_id is None or order["id"] == payment.order_id)
                 and unit["reference_id"] == payment.id and unit["custom_id"] == payment.run_id
                 and merchant_matches
                 and matches_amount(unit["amount"], payment.amount_minor, payment.currency)
                 and order["status"] in {"CREATED", "SAVED", "PAYER_ACTION_REQUIRED", "APPROVED", "COMPLETED", "VOIDED"})
        if not valid:
            raise PayPalError("paypal_order_mismatch")
        if may_bind:
            payment.merchant_id = merchant
    except (KeyError, IndexError, TypeError):
        raise PayPalError("paypal_order_mismatch") from None


def verify_capture(capture: dict, payment: Payment) -> str:
    try:
        PayPalSandbox.check_id(capture["id"])
        if (not matches_amount(capture["amount"], payment.amount_minor, payment.currency)
                or (payment.capture_id is not None and capture["id"] != payment.capture_id)):
            raise PayPalError("paypal_capture_mismatch")
        status = capture["status"]
        if status not in {"COMPLETED", "PENDING", "DECLINED", "FAILED", "REFUNDED", "PARTIALLY_REFUNDED"}:
            raise PayPalError("paypal_capture_mismatch")
        return status
    except (KeyError, TypeError):
        raise PayPalError("paypal_capture_mismatch") from None


class PaymentService:
    def __init__(self, factory: sessionmaker[Session], settings: Settings, adapter: PayPalSandbox | None = None) -> None:
        self.factory = factory
        self.settings = settings
        self.adapter = adapter or PayPalSandbox(settings)

    def check_configuration(self, payment: Payment) -> None:
        """Reject another app's intent without changing its status or evidence."""
        try:
            verify_merchant_configuration(payment, self.settings)
        except PayPalError as exc:
            raise ServiceError(503 if exc.code == "paypal_not_configured" else 409, exc.code,
                "Use the original Sandbox app and merchant configuration to reconcile this checkout.") from None

    async def process(self, run_id: str, checkout_id: str, allow_capture: bool = False,
                      worker_token: str | None = None) -> dict:
        """Explicit mutation/reconciliation only. GET list, SSE and replay never call this.

        Network responses are committed even after cancellation: payment evidence must
        survive a financial side effect. This never resumes or completes a cancelled run.
        Only an active fenced worker or authenticated operator can initiate work.
        """
        # Check before the run writer/lease recovery, then again under its lock.
        # A credential cutover must not fail, rebind or inspect an old intent.
        with self.factory() as session:
            original = find_payment(session, run_id, checkout_id)
            if original.status not in FINAL:
                self.check_configuration(original)
        raw_state = token_urlsafe(32)
        with locked_run(self.factory, run_id, worker_token) as (session, run):
            payment = find_payment(session, run_id, checkout_id)
            now = utcnow()
            if payment.status in FINAL:
                return public_payment(payment, True)
            self.check_configuration(payment)
            if payment.operation_token:
                if payment.operation_expires_at.replace(tzinfo=timezone.utc) > now:
                    return public_payment(payment, True)
                payment.operation_token = None
                payment.status = "unknown"
                payment.error_code = "paypal_operation_interrupted"
                evidence(session, run, payment, "payment.status_unknown")
            if payment.order_id is None and payment.status != "requested":
                return public_payment(payment, True)  # Never repeat an uncertain create, even after retention expires.
            action = "create" if payment.status == "requested" else "inspect"
            if action == "create" and (run.status != "running" or now >= payment.expires_at.replace(tzinfo=timezone.utc)):
                payment.status = "expired"
                evidence(session, run, payment, "payment.expired")
                return public_payment(payment, True)
            if action == "create":
                try:
                    verify_cart(run, payment)
                    verify_merchant_configuration(payment, self.settings)
                except PayPalError as exc:
                    payment.status, payment.error_code = "failed", exc.code
                    evidence(session, run, payment, "payment.failed")
                    return public_payment(payment, True)
                payment.callback_hash = sha256(raw_state.encode()).hexdigest()
                payment.status = "creating_order"
                evidence(session, run, payment, "payment.order_requested")
            operation = payment.operation_token = str(uuid4())
            payment.operation_expires_at = now + timedelta(seconds=self.settings.paypal_timeout_seconds * 4 + 30)
            snapshot = {key: getattr(payment, key) for key in ("id", "run_id", "amount_minor", "currency", "merchant_id", "create_key", "order_id")}
        try:
            order = (await self.adapter.create_order(snapshot, raw_state) if action == "create"
                     else await self.adapter.get_order(snapshot["order_id"]))
            with locked_run(self.factory, run_id) as (session, run):
                payment = find_payment(session, run_id, checkout_id)
                if payment.operation_token != operation:
                    return public_payment(payment, True)
                if action == "create":
                    verify_merchant_configuration(payment, self.settings)
                verify_order(order, payment, bind_merchant=action == "create")
                if action == "create":
                    payment.order_id = order["id"]
                    payment.approval_url = approval_link(order)
                    payment.status = "order_created"
                    evidence(session, run, payment, "payment.order_created")
                status = order["status"]
                captures = order["purchase_units"][0].get("payments", {}).get("captures", [])
                if len(captures) > 1:
                    raise PayPalError("paypal_capture_mismatch")
                if captures:
                    verify_capture(captures[0], payment)
                    payment.capture_id = captures[0]["id"]
                    action = "capture_details"
                    capture_id = payment.capture_id
                elif status == "COMPLETED":
                    raise PayPalError("paypal_capture_missing")
                elif status == "VOIDED":
                    payment.status = "failed"
                    payment.error_code = "paypal_order_voided"
                    evidence(session, run, payment, "payment.failed")
                    action = "done"
                elif status == "APPROVED":
                    # Approval always comes from verified PayPal state, including callback return.
                    if payment.approved_at is None:
                        payment.approved_at = utcnow()
                        payment.status = "approved"
                        evidence(session, run, payment, "payment.buyer_approved")
                    if payment.capture_requested_at is None:
                        payment.status = "approved"
                        run.runtime_json["checkouts"][payment.id] = public_payment(payment)
                    action = "done"
                    if payment.capture_requested_at is None and utcnow() >= payment.expires_at.replace(tzinfo=timezone.utc):
                        payment.status = "expired"
                        evidence(session, run, payment, "payment.expired")
                    elif allow_capture and run.status == "running" and payment.capture_requested_at is None:
                        verify_cart(run, payment)
                        verify_merchant_configuration(payment, self.settings)
                        payment.status = "capture_pending"
                        payment.capture_requested_at = utcnow()
                        evidence(session, run, payment, "payment.capture_requested")
                        action = "capture"
                        order_id, capture_key = payment.order_id, payment.capture_key
                else:
                    action = "done"
                    # A capture with an uncertain outcome is never POSTed again by a later call.
                    if payment.capture_requested_at is None:
                        if payment.status != "awaiting_buyer_approval":
                            payment.status = "awaiting_buyer_approval"
                            payment.error_code = None
                            evidence(session, run, payment, "payment.approval_pending")
                    if utcnow() >= payment.expires_at.replace(tzinfo=timezone.utc) and payment.status == "awaiting_buyer_approval":
                        payment.status = "expired"
                        evidence(session, run, payment, "payment.expired")
                if action == "done":
                    if payment.capture_requested_at is not None and status in {"APPROVED", "CREATED", "SAVED", "PAYER_ACTION_REQUIRED"}:
                        # A persisted capture request is never permission to POST
                        # again. Without a provider capture its outcome is unknown.
                        if payment.status != "unknown" or payment.error_code != "paypal_capture_unconfirmed":
                            payment.status, payment.error_code = "unknown", "paypal_capture_unconfirmed"
                            evidence(session, run, payment, "payment.status_unknown")
                    payment.operation_token = None
                    return public_payment(payment, True)
            if action == "capture":
                captured_order = await self.adapter.capture_order(order_id, capture_key)
                with locked_run(self.factory, run_id) as (session, run):
                    payment = find_payment(session, run_id, checkout_id)
                    if payment.operation_token != operation:
                        return public_payment(payment, True)
                    verify_order(captured_order, payment)
                    captures = captured_order["purchase_units"][0].get("payments", {}).get("captures", [])
                    if len(captures) != 1:
                        raise PayPalError("paypal_capture_missing", True)
                    verify_capture(captures[0], payment)
                    payment.capture_id = capture_id = captures[0]["id"]
            # Independently retrieve capture details; never infer success from an order ID.
            capture = await self.adapter.get_capture(capture_id)
            with locked_run(self.factory, run_id) as (session, run):
                payment = find_payment(session, run_id, checkout_id)
                if payment.operation_token != operation:
                    return public_payment(payment, True)
                capture_status = verify_capture(capture, payment)
                related = capture.get("supplementary_data", {}).get("related_ids", {}).get("order_id")
                if related is not None and related != payment.order_id:
                    raise PayPalError("paypal_capture_mismatch")
                # Capture ID originated exclusively from this verified order, never browser input.
                if capture_status == "COMPLETED":
                    if payment.captured_at is None:
                        payment.captured_at = utcnow()
                        state = run.runtime_json
                        state["spent_minor"] += payment.amount_minor
                        state["purchases"] += 1
                        state["reserved_minor"] -= payment.amount_minor
                        state["reserved_purchases"] -= 1
                    payment.status, payment.error_code = "completed", None
                    evidence(session, run, payment, "payment.captured")
                elif capture_status == "PENDING":
                    previous = run.runtime_json["checkouts"].get(payment.id, {})
                    changed = (payment.status != "capture_pending" or payment.error_code is not None
                               or previous.get("capture_id") != payment.capture_id
                               or previous.get("status") != "capture_pending")
                    payment.status, payment.error_code = "capture_pending", None
                    if changed:
                        # capture_requested already set this status. The first
                        # verified PENDING result must still publish its actual ID.
                        evidence(session, run, payment, "payment.capture_pending")
                else:
                    payment.status, payment.error_code = "failed", "paypal_capture_declined"
                    evidence(session, run, payment, "payment.failed")
                payment.operation_token = None
                return public_payment(payment, True)
        except PayPalError as exc:
            with locked_run(self.factory, run_id) as (session, run):
                payment = find_payment(session, run_id, checkout_id)
                if payment.operation_token == operation:
                    # Any error after a capture was sent requires reconciliation, including malformed replies.
                    definite_rejection = exc.code in {"paypal_declined", "paypal_auth_failed", "paypal_request_rejected", "paypal_not_found"}
                    uncertain = exc.uncertain or (payment.capture_requested_at is not None and not definite_rejection) or (action != "create" and not definite_rejection and exc.code not in {
                        "paypal_order_mismatch", "paypal_authorization_invalidated", "paypal_merchant_changed", "paypal_capture_mismatch"})
                    payment.status = "unknown" if uncertain else "failed"
                    payment.error_code = exc.code
                    payment.operation_token = None
                    evidence(session, run, payment, "payment.status_unknown" if uncertain else "payment.failed")
                return public_payment(payment, True)

    async def buyer_return(self, run_id: str, checkout_id: str, state: str, order_id: str) -> dict:
        with self.factory() as session:
            payment = find_payment(session, run_id, checkout_id)
            if (not payment.callback_hash or len(state) > 128 or not compare_digest(payment.callback_hash, sha256(state.encode()).hexdigest())
                    or (order_id and payment.order_id != order_id) or not payment.order_id
                    or utcnow() >= payment.expires_at.replace(tzinfo=timezone.utc)):
                raise ServiceError(403, "invalid_payment_return", "This Sandbox return does not match an active checkout.")
        return await self.process(run_id, checkout_id, allow_capture=False)

    def list(self, run_id: str) -> list[dict]:
        with self.factory() as session:
            if session.get(Assessment, run_id) is None:
                raise ServiceError(404, "assessment_not_found", "Assessment not found.")
            return [public_payment(row, True) for row in session.scalars(select(Payment).where(Payment.run_id == run_id).order_by(Payment.created_at))]
