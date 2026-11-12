"""Operator payment actions; no amounts/status/merchant supplied by the browser."""
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from app.payments.security import require_payment_access
from app.schemas.protocol import StrictModel

router = APIRouter(tags=["payments"])


class PaymentRead(BaseModel):
    checkout_id: str
    provider: str
    payment_mode: str
    status: str
    merchant_id: str
    items: list[dict]
    total_minor: int
    currency: str
    order_id: str | None
    capture_id: str | None
    error_code: str | None
    approval_url: str | None
    created_at: str
    updated_at: str
    expires_at: str


class ReconcileRequest(StrictModel):
    capture_if_approved: bool = False


@router.get("/assessments/{run_id}/payments", response_model=list[PaymentRead], dependencies=[Depends(require_payment_access)])
def payments(run_id: str, request: Request, response: Response) -> list[dict]:
    response.headers["Cache-Control"] = "no-store"
    return request.app.state.payments.list(run_id)


@router.post("/assessments/{run_id}/payments/{checkout_id}/reconcile", response_model=PaymentRead, dependencies=[Depends(require_payment_access)])
async def reconcile(run_id: str, checkout_id: str, data: ReconcileRequest, request: Request, response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return await request.app.state.payments.process(run_id, checkout_id, data.capture_if_approved)


@router.get("/payments/return/{run_id}/{checkout_id}", response_class=HTMLResponse, include_in_schema=False)
async def buyer_return(run_id: str, checkout_id: str, request: Request,
                       state: str = Query(max_length=128), token: str = Query(default="", max_length=36),
                       cancelled: bool = False) -> HTMLResponse:
    result = await request.app.state.payments.buyer_return(run_id, checkout_id, state, token)
    message = {
        "approved": "PayPal Sandbox buyer approval was verified server-side. Return to the Testah checkout panel to request capture.",
        "completed": "PayPal Sandbox capture was verified server-side. Return to the Testah checkout panel.",
        "awaiting_buyer_approval": "PayPal Sandbox buyer approval remains pending. Return to the Testah checkout panel.",
    }.get(result["status"], "Payment verification has not established a completed capture. Return to the Testah checkout panel for the recorded state.")
    return HTMLResponse("<!doctype html><html><head><title>Testah Sandbox checkout</title></head>"
                        '<body style="background:#101018;color:#eee;font:18px system-ui;padding:3rem"><h1>Testah Sandbox checkout</h1><p>'
                        + message + "</p><p>No real money is involved.</p></body></html>",
                        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'"})
