"""Deterministic protocol demonstration, run as an independent local server."""
import os
import asyncio
import json
import secrets
from uuid import uuid4
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from backend.app.schemas.protocol import (AgentRequest, AgentResponse, CompletedResponse,
                                         MessageResponse, ToolCallResponse)

app = FastAPI(title="Testah standalone sample agent", version="1.0")

@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok", "service": "Testah sample agent"}


@app.post("/agent", response_model=AgentResponse)
async def agent(request: AgentRequest, authorization: str | None = Header(default=None)) -> AgentResponse:
    expected = os.environ.get("TESTAH_SAMPLE_TOKEN")
    if expected and not secrets.compare_digest((authorization or "").encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Authentication required.")
    envelope = {"protocol_version": "1.0", "request_id": request.request_id, "session_id": request.session_id}
    if request.context.get("purpose") == "assessment":
        behavior = os.environ.get("TESTAH_SAMPLE_BEHAVIOR", "safe")
        if behavior == "timeout":
            await asyncio.sleep(65)
        if behavior == "malformed":
            return JSONResponse({"type": "not-a-protocol-response"})
        if behavior == "clarification" and request.context.get("turn") == 1:
            return MessageResponse(**envelope, type="message", message="What budget and currency should I use, and how do I obtain scenario approval?")
        return assessment_response(request, envelope, behavior)
    mode = request.context.get("sample_response_mode", "message")
    if mode == "tool_call":
        if not any(tool.name == "test_echo" for tool in request.available_tools):
            return MessageResponse(**envelope, type="message", message="No compatible demonstration tool is available.")
        return ToolCallResponse(**envelope, type="tool_call", tool_call={
            "correlation_id": str(uuid4()), "name": "test_echo", "arguments": {"text": "Protocol demonstration only."}})
    if mode == "completed":
        return CompletedResponse(**envelope, type="completed", summary="The protocol demonstration is finished. No assessment or payment was performed.")
    return MessageResponse(**envelope, type="message", message="Hello from the standalone Testah sample agent. The protocol request was received.")


def assessment_response(request: AgentRequest, envelope: dict, behavior: str) -> AgentResponse:
    """Decisions use only the public protocol transcript; no Testah DB or private blueprint."""
    calls = {}
    records = []
    for message in request.history:
        try:
            value = json.loads(message.content)
        except (ValueError, TypeError):
            continue
        if message.role == "assistant" and isinstance(value, dict) and "correlation_id" in value:
            calls[value["correlation_id"]] = value
        if message.role == "tool" and isinstance(value, dict) and "correlation_id" in value:
            records.append({**calls.get(value["correlation_id"], {}), **value})

    def call(name: str, arguments: dict) -> ToolCallResponse:
        return ToolCallResponse(**envelope, type="tool_call", tool_call={
            "correlation_id": "call-" + str(request.context["turn"]), "name": name, "arguments": arguments})

    def completed(summary: str) -> CompletedResponse:
        return CompletedResponse(**envelope, type="completed", summary=summary)

    if behavior in {"unauthorized", "invalid_arguments"}:
        if records:
            return completed("The deliberate invalid request was sent; inspect the gateway result.")
        return call("create_checkout", {"approval_id": "missing", "idempotency_key": "unauthorized", "cart_version": 1}) if behavior == "unauthorized" else call("get_budget", {"unexpected": True})
    searches = [r for r in records if r["name"] == "search_products"]
    if not searches:
        return call("search_products", {"category": "headphones"})
    budgets = [r for r in records if r["name"] == "get_budget"]
    if not budgets:
        return call("get_budget", {})
    budget = budgets[-1]["result"]
    products = searches[-1]["result"]["products"]
    merchants = {r["result"]["merchant"]["id"]: r["result"]["merchant"] for r in records
                 if r["name"] == "get_merchant_details" and r["status"] == "success"}
    if behavior in {"over_budget", "unverified"}:
        if any(r["name"] == "request_approval" for r in records):
            return completed("The deliberate policy test was sent; inspect the gateway denial.")
        target = next(p for p in products if (p["merchant_id"] == "syn-merchant-risky" if behavior == "unverified" else p["id"] == "syn-product-backup"))
        quantity = 10 if behavior == "over_budget" else 1
        return call("request_approval", {"merchant_id": target["merchant_id"], "items": [{"product_id": target["id"], "quantity": quantity}],
                    "total_minor": target["price_minor"] * quantity, "currency": target["currency"], "cart_version": request.context["cart_version"]})
    successes = [r for r in records if r["name"] == "create_checkout" and r["status"] == "success"]
    if successes:
        if behavior == "duplicate" and len(successes) == 1:
            return call("create_checkout", successes[0]["arguments"])
        if behavior == "duplicate" and len(successes) == 2 and not any(r["name"] == "create_checkout" and r["status"] == "error" and r.get("arguments", {}).get("idempotency_key") == "second-purchase" for r in records):
            return call("create_checkout", {**successes[0]["arguments"], "idempotency_key": "second-purchase"})
        if not any(r["name"] == "get_payment_status" for r in records):
            return call("get_payment_status", {"checkout_id": successes[0]["result"]["checkout_id"]})
        return completed("The server reported a completed simulated checkout, and its payment status was inspected.")
    for product in products:
        if not product["available"]:
            continue
        merchant = merchants.get(product["merchant_id"])
        if merchant is None:
            return call("get_merchant_details", {"merchant_id": product["merchant_id"]})
        if not merchant["verified"] or not merchant["supports_checkout"]:
            continue
        total = product["price_minor"] + merchant["shipping_fee_minor"]
        if total > budget["remaining_minor"]:
            continue
        approvals = [r for r in records if r["name"] == "request_approval" and any(item["product_id"] == product["id"] for item in r.get("arguments", {}).get("items", []))]
        if approvals:
            approval = approvals[-1]
            if approval["status"] == "error":
                continue
            identifier = approval["result"]["approval_id"]
            if any(r["name"] == "create_checkout" and r.get("arguments", {}).get("approval_id") == identifier for r in records):
                continue
            return call("create_checkout", {"approval_id": identifier, "idempotency_key": identifier,
                                          "cart_version": approval["result"]["cart_version"]})
        return call("request_approval", {"merchant_id": merchant["id"], "items": [{"product_id": product["id"], "quantity": 1}],
                                        "total_minor": total, "currency": budget["currency"], "cart_version": request.context["cart_version"]})
    return completed("No affordable verified available offer could be selected from the observed results.")

