"""Only the four validated v1 mutations; never mutate a source Blueprint."""
from collections.abc import Callable
from app.schemas.environments import Blueprint

Emitter = Callable[[str, dict], None]


def initial_state(blueprint: Blueprint) -> dict:
    return {"products": [p.model_dump() for p in blueprint.products],
            "merchants": [m.model_dump() for m in blueprint.merchants],
            "cart_version": 1, "applied": [], "approvals": {}, "checkouts": {}, "idempotency": {},
            "spent_minor": 0, "purchases": 0, "calls": {}, "correlations": [], "turns": 0,
            "tool_calls": 0, "http_requests": 0, "message_responses": 0, "history": [],
            "previous_tool_result": None, "payment_inspected": False,
            "next_message": blueprint.objective}


def activate(state: dict, blueprint: Blueprint, trigger_type: str, merchant_id: str,
             product_ids: list[str], emit: Emitter) -> None:
    for challenge in blueprint.challenges:
        trigger = challenge.trigger
        if (challenge.id in state["applied"] or trigger.type != trigger_type or trigger.merchant_id != merchant_id
                or (trigger.product_id is not None and trigger.product_id not in product_ids)):
            continue
        target = next(item for item in state["products" if challenge.state_change.field in ("price_minor", "available") else "merchants"]
                      if item["id"] == (challenge.affected_product_id if challenge.state_change.field in ("price_minor", "available") else merchant_id))
        change = challenge.state_change
        if change.field in ("price_minor", "shipping_fee_minor"):
            target[change.field] += change.increase_minor
        else:
            target[change.field] = change.value
        state["applied"].append(challenge.id)
        if challenge.id in state.get("requested_challenges", []):
            state["requested_challenges"].remove(challenge.id)
            emit("rai.challenge.request_fulfilled", {"challenge_id": challenge.id})
        state["cart_version"] += 1
        # Conservatively invalidate all outstanding approvals on any catalog change.
        for approval in state["approvals"].values():
            if approval["status"] == "granted":
                approval["status"] = "invalidated"
        emit("challenge.activated", {"kind": challenge.kind, "summary": challenge.summary,
                                     "cart_version": state["cart_version"]})


def request_activation(state: dict, blueprint: Blueprint, challenge_id: str, emit: Emitter) -> None:
    """Accept only a conditional request; no caller may skip the declared trigger."""
    challenge = next((c for c in blueprint.challenges if c.id == challenge_id), None)
    code = "awaiting_declared_trigger"
    if challenge is None:
        code = "unsupported_challenge"
    elif challenge_id in state["applied"]:
        code = "already_activated"
    elif state["purchases"]:
        code = "purchase_already_completed"
    else:
        merchant = next(m for m in state["merchants"] if m["id"] == challenge.affected_merchant_id)
        product = next((p for p in state["products"] if p["id"] == challenge.affected_product_id), None)
        if not merchant["supports_checkout"] or (product is not None and not product["available"]):
            code = "runtime_target_unavailable"
        elif challenge.kind == "unverified_merchant" and not merchant["verified"]:
            code = "runtime_target_unavailable"
    accepted = code == "awaiting_declared_trigger"
    if accepted:
        pending = state.setdefault("requested_challenges", [])
        if challenge_id not in pending:
            pending.append(challenge_id)
    emit("rai.challenge.request_accepted" if accepted else "rai.challenge.request_rejected",
         {"challenge_id": challenge_id, "code": code})
