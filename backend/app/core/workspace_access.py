"""Shared perimeter for a trusted demo; not tenant identity or payment authority."""
from secrets import compare_digest
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class WorkspaceAccessMiddleware:
    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and self.token:
            path = scope["path"]
            # PayPal redirects carry an existing expiring, order-bound capability.
            public_get = scope["method"] == "GET" and (
                path == "/api/health" or path.startswith("/api/payments/return/")
            )
            supplied = Headers(scope=scope).get("x-testah-workspace-token", "")
            if not public_get and (len(supplied) > 512 or not compare_digest(
                supplied.encode("utf-8"), self.token.encode("ascii")
            )):
                response = JSONResponse(
                    {"error": {"code": "workspace_access_required", "message": "Valid workspace access is required."}},
                    status_code=401, headers={"Cache-Control": "no-store"},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
