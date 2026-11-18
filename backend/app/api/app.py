"""Fabrique de l'application FastAPI LabMind."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings

from .errors import install_error_handlers
from .routes import router
from .store import TaskManager


def create_app(
    settings: Settings | None = None,
    task_manager: TaskManager | None = None,
) -> FastAPI:
    """Construit l'instance FastAPI configurée avec ses routes et middlewares."""
    active_settings = settings or get_settings()
    active_settings.ensure_dirs()

    app = FastAPI(
        title="LabMind API",
        version="1.0.0",
        description="API pédagogique d'analyse de comptes rendus biologiques (sans diagnostic).",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(active_settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    app.state.settings = active_settings
    app.state.task_manager = task_manager or TaskManager(settings=active_settings)

    install_error_handlers(app)
    app.include_router(router)
    return app