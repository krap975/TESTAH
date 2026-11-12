from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.environments import router as environments_router
from app.api.agents import router as agents_router
from app.api.health import router as health_router
from app.api.assessments import router as assessments_router
from app.api.payments import router as payments_router
from app.api.reports import router as reports_router
from app.payments.service import PaymentService
from app.payments.security import PaymentReturnFilter
import logging
from app.api.rai import router as rai_router
from app.api.rai_diagnostics import router as rai_diagnostics_router
from app.rai.provider_diagnostics import ProviderDiagnostics
from app.events.stream import AssessmentStreams
from app.rai.designer import DesignerWorker
from app.rai.diagnostics import log_configuration
from app.execution.controller import ExecutionController, LocalWorker
from app.core.config import Settings
from app.core.workspace_access import WorkspaceAccessMiddleware
from app.core.errors import register_error_handlers
from app.database.session import build_engine, make_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = build_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        log_configuration(settings)
        _app.state.evaluation_worker.start()
        try:
            yield
        finally:
            await _app.state.designer_worker.close()
            await _app.state.worker.close()
            await _app.state.evaluation_worker.close()
            engine.dispose()

    production = settings.environment == "production"
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan,
                  docs_url=None if production else "/docs",
                  redoc_url=None if production else "/redoc",
                  openapi_url=None if production else "/openapi.json")
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    from app.evaluation.service import EvaluationWorker
    app.state.evaluation_worker = EvaluationWorker(app.state.session_factory)
    app.state.assessment_streams = AssessmentStreams(app.state.session_factory, settings)
    app.state.payments = PaymentService(app.state.session_factory, settings)
    controller = ExecutionController(app.state.session_factory, settings)
    controller.payments = app.state.payments
    app.state.worker = LocalWorker(controller)
    access_logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, PaymentReturnFilter) for item in access_logger.filters):
        access_logger.addFilter(PaymentReturnFilter())
    app.state.designer_worker = DesignerWorker(app.state.session_factory, settings)
    app.add_middleware(WorkspaceAccessMiddleware, token=settings.workspace_access_token.get_secret_value())
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Content-Type", "Authorization", "Last-Event-ID", "X-Testah-Workspace-Token"],
    )
    register_error_handlers(app)
    app.include_router(health_router, prefix="/api")
    app.include_router(agents_router, prefix="/api")
    app.include_router(environments_router, prefix="/api")
    app.include_router(assessments_router, prefix="/api")
    app.include_router(payments_router, prefix="/api")
    app.include_router(reports_router, prefix="/api")
    app.include_router(rai_router, prefix="/api")
    if settings.environment == "development":
        app.state.provider_diagnostics = ProviderDiagnostics(settings)
        app.include_router(rai_diagnostics_router, prefix="/api")
    return app
