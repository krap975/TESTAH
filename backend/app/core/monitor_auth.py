"""Shared operator authentication, not user/assessment ownership authorization."""
from typing import Annotated
from secrets import compare_digest
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.domain_errors import ServiceError

bearer = HTTPBearer(auto_error=False, scheme_name="MonitoringBearer")


def require_monitor_access(request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> None:
    expected = request.app.state.settings.monitor_token.get_secret_value()
    if not expected:
        raise ServiceError(503, "monitor_not_configured", "Monitoring access is not configured. Set the server-side monitoring token and restart the API.")
    supplied = credentials.credentials if credentials else ""
    if len(supplied) > 512 or not compare_digest(supplied.encode("utf-8"), expected.encode("ascii")):
        raise HTTPException(401, "Valid monitoring credentials are required.", headers={"WWW-Authenticate": "Bearer"})
