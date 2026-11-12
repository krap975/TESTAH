"""Inspect one bound Sandbox checkout; provider mode permits OAuth and GET only."""
import argparse
import asyncio
from datetime import timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select, text
from paypalserversdk.models.capture_incomplete_reason import CaptureIncompleteReason
from app.core.config import Settings
from app.database.session import build_engine, make_session_factory
from app.models.agent import utcnow
from app.models.assessment import Assessment, RunEvent
from app.models.payment import Payment
from app.payments.paypal import BASE, PayPalError, PayPalSandbox, client_binding, configured
from app.payments.service import find_payment, verify_capture, verify_merchant_configuration, verify_order


async def running_backend_report(settings: Settings, payment: Payment) -> dict:
    """An already-created capture can only be inspected by this API request.

    Useful when the running server retains the original app and .env has changed.
    No credential extraction or binding bypass: existing server verification applies.
    """
    import httpx
    if not payment.order_id or not payment.capture_id or payment.capture_requested_at is None or payment.status not in {"capture_pending", "unknown"}:
        raise PayPalError("payment_diagnostic_existing_capture_required")
    url = f"http://127.0.0.1:8000/api/assessments/{payment.run_id}/payments/{payment.id}/reconcile"
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=40) as client:
        response = await client.post(url, headers={"Authorization": "Bearer " + settings.payment_operator_token.get_secret_value()},
                                     json={"capture_if_approved": False})
    data = response.json()
    if response.status_code != 200:
        return {"http_status": response.status_code, "error_code": data.get("error", {}).get("code")}
    if data.get("order_id") != payment.order_id or data.get("capture_id") != payment.capture_id:
        raise PayPalError("paypal_capture_mismatch")
    return {"http_status": 200, "capture_if_approved": False,
            **{key: data.get(key) for key in ("status", "error_code", "order_id", "capture_id", "currency", "total_minor")}}


class ReadOnlySandbox(PayPalSandbox):
    async def request(self, method: str, url: str, **kwargs) -> dict:
        if not (method == "GET" and (url.startswith(BASE + "/v2/checkout/orders/")
                                     or url.startswith(BASE + "/v2/payments/captures/"))
                or method == "POST" and url == BASE + "/v1/oauth2/token"):
            raise PayPalError("payment_diagnostic_write_blocked")
        return await super().request(method, url, **kwargs)


async def provider_report(settings: Settings, payment: Payment) -> dict:
    verify_merchant_configuration(payment, settings)
    adapter = ReadOnlySandbox(settings)
    order = await adapter.get_order(payment.order_id)
    verify_order(order, payment)
    report = {"provider_order_status": order["status"], "order_binding_verified": True, "captures": []}
    for embedded in order["purchase_units"][0].get("payments", {}).get("captures", []):
        verify_capture(embedded, payment)
        capture = await adapter.get_capture(embedded["id"])
        status = verify_capture(capture, payment)
        related = capture.get("supplementary_data", {}).get("related_ids", {}).get("order_id")
        if capture["id"] != embedded["id"] or related is not None and related != payment.order_id:
            raise PayPalError("paypal_capture_mismatch")
        report["captures"].append({"id": capture["id"], "status": status,
                                   "amount_minor": payment.amount_minor, "currency": payment.currency,
                                   "status_reason": CaptureIncompleteReason.from_value((capture.get("status_details") or {}).get("reason")),
                                   "independent_capture_verified": True})
    report["financial_posts_permitted"] = False
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--checkout-id", required=True)
    parser.add_argument("--order-id", required=True)
    parser.add_argument("--provider", action="store_true")
    parser.add_argument("--backend-status", action="store_true", help="Reconcile a known capture through the running server, with capture disabled.")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    args = parser.parse_args()
    if not args.env_file.is_file():
        print("Configuration file is missing; no requests made.")
        return 1
    engine = None
    try:
        settings = Settings(_env_file=args.env_file)
        engine = build_engine(settings.database_url)
        with make_session_factory(engine)() as session:
            if engine.dialect.name == "sqlite":
                session.execute(text("PRAGMA query_only=ON"))
            payment = find_payment(session, args.run_id, args.checkout_id)
            if payment.order_id != args.order_id:
                raise PayPalError("paypal_order_mismatch")
            run = session.get(Assessment, args.run_id)
            fields = ("status", "error_code", "order_id", "capture_id", "currency", "amount_minor",
                      "created_at", "updated_at", "approved_at", "capture_requested_at", "captured_at", "expires_at", "operation_expires_at")
            report = {key: getattr(payment, key) for key in fields}
            report.update(checked_at=utcnow(), configuration_present=configured(settings),
                app_binding_matches=payment.client_binding == client_binding(settings),
                explicit_merchant_pin_matches=not settings.paypal_merchant_id or payment.merchant_id == settings.paypal_merchant_id,
                operation_claim_present=bool(payment.operation_token),
                operation_claim_expired=bool(payment.operation_token and payment.operation_expires_at and payment.operation_expires_at.replace(tzinfo=timezone.utc) <= utcnow()),
                assessment={key: getattr(run, key) for key in ("status", "termination_reason", "failure_origin", "started_at", "ended_at", "event_sequence")},
                runtime_payment_status=run.runtime_json.get("checkouts", {}).get(payment.id, {}).get("status"),
                purchases=run.runtime_json["purchases"], spent_minor=run.runtime_json["spent_minor"],
                reserved_minor=run.runtime_json.get("reserved_minor", 0))
            events = session.scalars(select(RunEvent).where(RunEvent.run_id == run.id).order_by(RunEvent.sequence))
            report["events"] = [{"sequence": event.sequence, "created_at": event.created_at, "type": event.event_type,
                "facts": {key: event.payload[key] for key in ("status", "error_code", "order_id", "capture_id", "code", "reason", "origin", "from", "to") if key in event.payload}}
                for event in events if event.event_type.startswith(("payment.", "checkout.", "assessment.", "execution."))]
        print(json.dumps({"local": report}, default=str))
        if args.backend_status:
            print(json.dumps({"running_backend": asyncio.run(running_backend_report(settings, payment))}))
        if args.provider:
            try:
                verified = asyncio.run(provider_report(settings, payment))
                print(json.dumps({"provider": verified}))
            except PayPalError as exc:
                print(json.dumps({"provider_error": exc.code, "uncertain": exc.uncertain}))
                return 1
        return 0
    except Exception:
        print("Payment diagnostic failed safely; no credentials, raw provider data or financial requests emitted.")
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
