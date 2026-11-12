"""Read-only, value-free configuration audit and non-financial OAuth preflight."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.config import Settings
from app.models.assessment import Assessment
from app.models.payment import Payment
from app.payments.paypal import PayPalError, PayPalSandbox, client_binding, configured, credential_configured


def configuration_report(session: Session, settings: Settings) -> dict:
    def count(*conditions) -> int:
        return session.scalar(select(func.count()).select_from(Payment).where(*conditions)) or 0

    binding = client_binding(settings)
    currencies = dict(session.execute(select(Payment.currency, func.count()).group_by(Payment.currency)).all())
    statuses = dict(session.execute(select(Payment.status, func.count()).group_by(Payment.status)).all())
    snapshots = session.scalars(select(Assessment.blueprint_json).where(Assessment.payment_mode == "paypal_sandbox"))
    scenario_currencies: dict[str, int] = {}
    for snapshot in snapshots:
        currency = snapshot["currency"]
        scenario_currencies[currency] = scenario_currencies.get(currency, 0) + 1
    return {
        "sandbox_mode": settings.payment_mode == "paypal_sandbox",
        "sandbox_origin_fixed": settings.paypal_api_base_url == "https://api-m.sandbox.paypal.com",
        "client_id_configured": credential_configured(settings.paypal_client_id.get_secret_value()),
        "client_secret_configured": credential_configured(settings.paypal_client_secret.get_secret_value()),
        "configuration_present": configured(settings),
        "explicit_merchant_pin": bool(settings.paypal_merchant_id),
        "scenario_currency_counts": scenario_currencies,
        "intent_currency_counts": currencies,
        "intent_status_counts": statuses,
        "stored_order_count": count(Payment.order_id.is_not(None)),
        "intents_bound_to_current_app": count(Payment.client_binding == binding),
        "intents_bound_to_another_app": count(Payment.client_binding.is_not(None), Payment.client_binding != binding),
        "legacy_intents_without_app_binding": count(Payment.client_binding.is_(None)),
        "distinct_bound_merchant_count": session.scalar(select(func.count(func.distinct(Payment.merchant_id))).where(Payment.merchant_id != "")) or 0,
        "bound_merchants_match_explicit_pin": (count(Payment.merchant_id != "", Payment.merchant_id != settings.paypal_merchant_id) == 0
                                              if settings.paypal_merchant_id else None),
        "merchant_country_verified": False,
        "merchant_usd_acceptance_verified": False,
        "oauth_authenticated": False,
        "payment_requests_made": False,
    }


async def authenticate_configuration(adapter: PayPalSandbox) -> dict:
    """Only OAuth: never order creation, approval, capture or reconciliation."""
    try:
        await adapter.access_token()
        return {"oauth_authenticated": True}
    except PayPalError as exc:
        return {"oauth_authenticated": False, "oauth_error_code": exc.code}
