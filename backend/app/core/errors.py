import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from app.core.domain_errors import ServiceError
from app.execution.network import DestinationError

logger = logging.getLogger(__name__)


def error_response(status: int, code: str, message: str, headers=None):
    return JSONResponse(
        status_code=status, content={"error": {"code": code, "message": message}},
        headers=headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def service_error(_request: Request, exc: ServiceError):
        return error_response(exc.status, exc.code, exc.message)

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException):
        return error_response(exc.status_code, f"http_{exc.status_code}", str(exc.detail), exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _exc: RequestValidationError):
        # Only fixed validator messages and known field labels may be exposed.
        # Never serialize Pydantic input values or arbitrary error context.
        known = {"name", "description", "endpoint_url", "connection_mode", "authentication", "header_name", "secret_key", "template_id", "template_version", "currency", "budget_minor", "customer_name", "objective"}
        for error in _exc.errors():
            cause = error.get("ctx", {}).get("error")
            if isinstance(cause, DestinationError):
                return error_response(422, "validation_error", str(cause))
        fields = sorted({str(part) for error in _exc.errors() for part in error.get("loc", ()) if part in known})
        message = "Request validation failed."
        if fields:
            message += " Check: " + ", ".join(fields) + "."
        return error_response(422, "validation_error", message)

    @app.exception_handler(Exception)
    async def unexpected_error(_request: Request, exc: Exception):
        logger.error("Unhandled API error (%s)", type(exc).__name__)
        return error_response(500, "internal_error", "An internal server error occurred.")
