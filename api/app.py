from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes import router, orchestrator
from services.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-load the retriever and sentence-transformers model at startup
    # so the first API request doesn't time out on Render free tier
    orchestrator.technical.retriever.ensure_ready()
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="CloudDash Multi-Agent Customer Support API",
        description="API-first prototype for multi-agent customer support.",
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.include_router(router)
    return app