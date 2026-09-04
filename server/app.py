"""
FastAPI Application Factory for Personal Live Quant Brain.
Provides REST APIs, Webhooks, Observability, and serves the Web Dashboard.
Compatible with both persistent servers (Docker, VPS) and Serverless (Vercel, AWS Lambda).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config.quant_brain_config import settings
from storage.db import init_db
from server.routes import chat, market, tradingview, connections, health, telegram_webhook

logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("Starting up %s v%s...", settings.APP_NAME, settings.APP_VERSION)
    await init_db()
    yield
    logger.info("Shutting down %s...", settings.APP_NAME)


def create_app() -> FastAPI:
    """Creates and configures the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Personal Live-Market Quant Intelligence Platform & AI Brain",
        lifespan=lifespan,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API Routers
    app.include_router(chat.router)
    app.include_router(market.router)
    app.include_router(tradingview.router)
    app.include_router(connections.router)
    app.include_router(health.router)
    app.include_router(telegram_webhook.router)

    # Mount static assets if frontend directory exists
    if FRONTEND_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
        if (FRONTEND_DIR / "css").exists():
            app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
        if (FRONTEND_DIR / "js").exists():
            app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")

    @app.get("/")
    async def serve_index():
        # Check frontend/index.html first, then public/index.html
        index_path = FRONTEND_DIR / "index.html"
        if not index_path.exists():
            public_index = FRONTEND_DIR.parent / "public" / "index.html"
            if public_index.exists():
                index_path = public_index

        if index_path.exists():
            return FileResponse(str(index_path))
        return {
            "status": "ONLINE",
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs_url": "/docs",
            "health_url": "/health",
        }

    return app


app = create_app()
