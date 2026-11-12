"""Keep the short-lived callback capability out of Uvicorn access logs."""
import logging
from typing import Annotated
from secrets import compare_digest
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.domain_errors import ServiceError

payment_bearer = HTTPBearer(auto_error=False, scheme_name="SandboxPaymentOperator")


def require_payment_access(request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(payment_bearer)]) -> None:
    expected = request.app.state.settings.payment_operator_token.get_secret_value()
    if not expected:
        raise ServiceError(503, "payment_operator_not_configured", "Sandbox payment operator access is not configured.")
    supplied = credentials.credentials if credentials else ""
    if len(supplied) > 512 or not compare_digest(supplied.encode("utf-8"), expected.encode("ascii")):
        raise HTTPException(401, "Valid payment operator credentials are required.", headers={"WWW-Authenticate": "Bearer"})


class PaymentReturnFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple) and len(record.args) == 5:
            client, method, path, version, status = record.args
            if isinstance(path, str) and path.startswith("/api/payments/return/"):
                record.args = (client, method, path.split("?", 1)[0], version, status)
        return True
