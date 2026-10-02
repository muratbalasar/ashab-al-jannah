import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles

from ledenadmin import APP_NAME, APP_TAGLINE, __version__
from ledenadmin.api.errors import register_error_handlers
from ledenadmin.api.routers import categories, donations, members, reports, system
from ledenadmin.auth.providers import build_auth_provider
from ledenadmin.config import Settings, get_settings
from ledenadmin.db import Database
from ledenadmin.services.ai.insight_service import InsightService, build_insight_provider
from ledenadmin.services.category_service import CategoryService
from ledenadmin.web import routes as web_routes
from ledenadmin.web.security import SecurityMiddleware
from ledenadmin.web.templating import STATIC_DIR, build_templates

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, database: Database | None = None) -> FastAPI:
    """Applicatiefabriek; start met `uvicorn --factory ledenadmin.main:create_app`."""
    settings = settings or get_settings()
    database = database or Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if settings.seed_default_categories:
            with database.session() as session:
                if CategoryService(session).ensure_defaults():
                    logger.info("Standaardcategorieën aangemaakt")
        yield
        database.engine.dispose()

    app = FastAPI(
        title=f"{APP_NAME} – {APP_TAGLINE}",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.settings = settings
    app.state.database = database
    app.state.auth_provider = build_auth_provider(settings)
    app.state.insights = InsightService(build_insight_provider(settings))
    app.state.templates = build_templates(settings.tz)

    app.add_middleware(SecurityMiddleware, secure_cookies=settings.is_production)
    register_error_handlers(app)

    api = APIRouter(prefix="/api/v1")
    for module in (system, members, categories, donations, reports):
        api.include_router(module.router)
    app.include_router(api)
    app.include_router(web_routes.router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
