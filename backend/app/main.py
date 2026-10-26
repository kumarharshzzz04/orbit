"""FastAPI application for ORBIT backend."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .db import models  # noqa: F401 - import to register models
from .db.config import get_engine, init_db
from .routers import experiments, hypotheses, missions, ws
from .schemas.common import ErrorResponse, HealthResponse
from .services.execution import init_execution_service, shutdown_execution_service
from .services.ws_manager import get_ws_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
LOG = logging.getLogger("orbit.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    LOG.info("Starting ORBIT backend...")

    # Initialize database
    init_db()
    LOG.info("Database initialized")

    # Initialize execution service
    await init_execution_service()
    LOG.info("Execution service initialized")

    # Initialize WebSocket manager
    get_ws_manager()
    LOG.info("WebSocket manager initialized")

    yield

    # Shutdown
    LOG.info("Shutting down ORBIT backend...")
    await shutdown_execution_service()
    LOG.info("Execution service stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="ORBIT Backend API",
        description="Experiment registry, execution management, and WebSocket events for ORBIT",
        version="0.2.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(missions.router)
    app.include_router(hypotheses.router)
    app.include_router(experiments.router)
    app.include_router(ws.router)

    # Health endpoint
    @app.get("/health", response_model=HealthResponse, tags=["health"])
    async def health_check():
        """Health check endpoint."""
        # Check database
        db_status = "healthy"
        try:
            engine = get_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as e:
            LOG.error("Database health check failed: %s", e)
            db_status = "unhealthy"

        # Check ML sandbox
        ml_status = "unknown"
        try:
            # Quick check if ml_sandbox module is importable
            import ml_sandbox  # noqa: F401

            ml_status = "healthy"
        except Exception as e:
            LOG.warning("ML sandbox check failed: %s", e)
            ml_status = "unhealthy"

        return HealthResponse(
            status="healthy" if db_status == "healthy" else "degraded",
            database=db_status,
            ml_sandbox=ml_status,
            timestamp=__import__("datetime")
            .datetime.now(__import__("datetime").UTC)
            .isoformat(timespec="seconds"),
        )

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        LOG.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                detail="Internal server error", code="INTERNAL_ERROR"
            ).model_dump(),
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Set to True for development
        workers=1,  # Important: single worker for SQLite
    )
