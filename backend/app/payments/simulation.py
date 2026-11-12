"""Server-owned deterministic simulation; replace this provider boundary in Phase 7."""
from uuid import uuid4
from app.environments.runtime import Emitter


def create_simulated_payment(approval: dict, emit: Emitter) -> dict:
    checkout = {"checkout_id": "sim-" + str(uuid4()), "payment_id": "sim-payment-" + str(uuid4()),
                "provider": "simulation", "status": "created", "merchant_id": approval["merchant_id"],
                "items": approval["items"], "total_minor": approval["total_minor"], "currency": approval["currency"]}
    emit("checkout.created", dict(checkout))
    checkout["status"] = "authorized"
    emit("payment.authorized", dict(checkout))
    checkout["status"] = "completed"
    emit("payment.captured", dict(checkout))
    return checkout
