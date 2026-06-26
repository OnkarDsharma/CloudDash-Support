from fastapi import FastAPI

from api.routes import router
from services.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="CloudDash Multi-Agent Customer Support API",
        description="API-first prototype for multi-agent customer support.",
        version=settings.app_version,
    )
    app.include_router(router)
    return app

