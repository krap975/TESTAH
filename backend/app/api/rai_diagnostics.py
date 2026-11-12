from typing import Literal
from fastapi import APIRouter, Request
from app.core.domain_errors import ServiceError
from app.schemas.protocol import StrictModel

router = APIRouter(prefix="/rai", tags=["Development provider diagnostics"])


class DiagnosticRequest(StrictModel):
    run_smoke_test: Literal[True]


@router.post("/diagnostics")
async def check_provider(data: DiagnosticRequest, request: Request) -> dict:
    # Router is not installed in test/production. JSON plus Origin validation prevents
    # a cross-site simple form from triggering a paid check in a local development API.
    origin = request.headers.get("origin")
    if origin is not None and origin not in request.app.state.settings.cors_origins:
        raise ServiceError(403, "diagnostics_origin_denied", "Provider checks require an allowed development origin.")
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        raise ServiceError(415, "diagnostics_json_required", "Provider checks require an explicit JSON request.")
    diagnostics = request.app.state.provider_diagnostics
    # No await between admission and claim: one diagnostic at a time per API process.
    if diagnostics.running:
        raise ServiceError(409, "diagnostics_busy", "A provider check is already running. Wait for its result.")
    diagnostics.running = True
    try:
        return await diagnostics.run()
    finally:
        diagnostics.running = False
