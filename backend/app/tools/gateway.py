"""Every commerce operation runs here inside a serialized run transaction."""
import hashlib
import json
from collections.abc import Callable
from uuid import uuid4
from pydantic import ValidationError
from app.environments.runtime import Emitter, activate
from app.payments.simulation import create_simulated_payment
from app.schemas.environments import Blueprint
from app.schemas.protocol import ToolCall, ToolResult
from app.tools.registry import validate_tool_call


class PolicyDenied(Exception):
    def __init__(self, code: str) -> None:
        self.code = code


def deny(code: str) -> None:
    raise PolicyDenied(code)


def cart_fingerprint(cart: dict) -> str:
    return hashlib.sha256(json.dumps(cart, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def checked_cart(state: dict, blueprint: Blueprint, data: dict) -> dict:
    merchant = next((m for m in state["merchants"] if m["id"] == data["merchant_id"]), None)
    if merchant is None:
        deny("unknown_merchant")
    if not merchant["verified"]:
        deny("unverified_merchant")
    if not merchant["supports_checkout"]:
        deny("checkout_unsupported")
    products = {p["id"]: p for p in state["products"]}
    subtotal = 0
    items = sorted(data["items"], key=lambda item: item["product_id"])
    for item in items:
        product = products.get(item["product_id"])
        if product is None or product["merchant_id"] != merchant["id"]:
            deny("invalid_cart")
        if not product["available"]:
            deny("product_unavailable")
        if product["currency"] != blueprint.currency:
            deny("currency_mismatch")
        subtotal += product["price_minor"] * item["quantity"]
    total = subtotal + merchant["shipping_fee_minor"]
    if data["currency"] != blueprint.currency or merchant["currency"] != blueprint.currency:
        deny("currency_mismatch")
    if total > blueprint.budget_minor - state["spent_minor"] - state.get("reserved_minor", 0):
        deny("budget_exceeded")
    if state["purchases"] + state.get("reserved_purchases", 0) >= blueprint.policies.max_purchases:
        deny("purchase_limit")
    if data["total_minor"] != total:
        deny("amount_changed")
    if data["cart_version"] != state["cart_version"]:
        deny("stale_cart")
    return {"merchant_id": merchant["id"], "items": items, "total_minor": total,
            "currency": blueprint.currency, "cart_version": state["cart_version"],
            "shipping_fee_minor": merchant["shipping_fee_minor"],
            "unit_prices": {item["product_id"]: products[item["product_id"]]["price_minor"] for item in items}}


def execute_tool(state: dict, blueprint: Blueprint, call: ToolCall, emit: Emitter,
                 payment_factory: Callable[[dict], dict] | None = None) -> ToolResult:
    try:
        try:
            args = validate_tool_call(call, [tool.name for tool in blueprint.tool_permissions]).model_dump()
        except (ValidationError, ValueError):
            deny("invalid_tool_arguments")
        emit("tool.requested", {"name": call.name, "arguments": args})
        result = dispatch(state, blueprint, call.name, args, emit, payment_factory)
        emit("tool.completed", {"name": call.name, "result": result})
        return ToolResult(correlation_id=call.correlation_id, name=call.name, status="success", result=result)
    except PolicyDenied as exc:
        result = {"code": exc.code, "message": "The gateway rejected this request.", "cart_version": state["cart_version"]}
        emit("policy.violation", {"name": call.name, **result})
        if call.name == "request_approval":
            emit("approval.denied", result)
        emit("tool.failed", {"name": call.name, "result": result})
        return ToolResult(correlation_id=call.correlation_id, name=call.name, status="error", result=result)


def dispatch(state: dict, blueprint: Blueprint, name: str, args: dict, emit: Emitter,
             payment_factory: Callable[[dict], dict] | None = None) -> dict:
    version = lambda: {"cart_version": state["cart_version"]}
    if name == "search_products":
        products = [dict(p) for p in state["products"] if args["query"].casefold() in p["name"].casefold()
                    and (args["category"] is None or args["category"] == p["category"])
                    and (args["max_price_minor"] is None or p["price_minor"] <= args["max_price_minor"])]
        return {"products": products, **version()}
    if name == "get_merchant_details":
        activate(state, blueprint, "merchant_selected", args["merchant_id"], [], emit)
        merchant = next((m for m in state["merchants"] if m["id"] == args["merchant_id"]), None)
        if merchant is None:
            deny("unknown_merchant")
        return {"merchant": dict(merchant), **version()}
    if name == "get_budget":
        return {"budget_minor": blueprint.budget_minor, "remaining_minor": blueprint.budget_minor - state["spent_minor"] - state.get("reserved_minor", 0),
                "currency": blueprint.currency, "purchases": state["purchases"], **version()}
    if name == "request_approval":
        # Validate membership before selection can activate a challenge.
        selected = [item["product_id"] for item in args["items"]]
        if any(not any(p["id"] == pid and p["merchant_id"] == args["merchant_id"] for p in state["products"]) for pid in selected):
            deny("invalid_cart")
        activate(state, blueprint, "merchant_selected", args["merchant_id"], selected, emit)
        activate(state, blueprint, "product_selected", args["merchant_id"], selected, emit)
        cart = checked_cart(state, blueprint, args)
        approval = {**cart, "approval_id": "approval-" + str(uuid4()), "status": "granted", "fingerprint": cart_fingerprint(cart)}
        state["approvals"][approval["approval_id"]] = approval
        emit("approval.granted", {key: value for key, value in approval.items() if key != "fingerprint"})
        return {key: value for key, value in approval.items() if key != "fingerprint"}
    if name == "create_checkout":
        prior = state["idempotency"].get(args["idempotency_key"])
        intent = {"approval_id": args["approval_id"], "cart_version": args["cart_version"]}
        if prior is not None:
            if prior["intent"] != intent:
                deny("idempotency_conflict")
            return {**state["checkouts"][prior["checkout_id"]], "idempotent_replay": True}
        approval = state["approvals"].get(args["approval_id"])
        if approval is None:
            deny("approval_required")
        if approval["status"] != "granted":
            deny("approval_" + approval["status"])
        if args["cart_version"] != approval["cart_version"]:
            deny("stale_cart")
        selected = [item["product_id"] for item in approval["items"]]
        activate(state, blueprint, "before_checkout", approval["merchant_id"], selected, emit)
        cart = checked_cart(state, blueprint, approval)
        if approval["status"] != "granted" or cart_fingerprint(cart) != approval["fingerprint"]:
            deny("approval_invalidated")
        sandbox = state.get("payment_mode", "simulated") == "paypal_sandbox"
        if sandbox:
            if payment_factory is None:
                deny("payment_provider_unavailable")
            checkout = payment_factory(approval)
            emit("checkout.requested", dict(checkout))
            emit("payment.authorization_verified", dict(checkout))
        else:
            checkout = create_simulated_payment(approval, emit)
        state["checkouts"][checkout["checkout_id"]] = checkout
        state["idempotency"][args["idempotency_key"]] = {"intent": intent, "checkout_id": checkout["checkout_id"]}
        if sandbox:
            state["reserved_minor"] = state.get("reserved_minor", 0) + cart["total_minor"]
            state["reserved_purchases"] = state.get("reserved_purchases", 0) + 1
        else:
            state["spent_minor"] += cart["total_minor"]
            state["purchases"] += 1
        approval["status"] = "consumed"
        return checkout
    if name == "get_payment_status":
        checkout = state["checkouts"].get(args["checkout_id"])
        if checkout is None:
            deny("unknown_checkout")
        if checkout["status"] == "completed":
            state["payment_inspected"] = True
        return dict(checkout)
    deny("tool_not_allowed")
