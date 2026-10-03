import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles

from ledenadmin import APP_NAME, APP_TAGLINE, __version__
from ledenadmin.api.errors import register_error_handlers
from ledenadmin.api.routers import categories, donations, members, reports, system
from ledenadmin.audit import AuditMiddleware
from ledenadmin.auth.providers import build_auth_provider
from ledenadmin.config import Settings, get_settings
from ledenadmin.db import Database
from ledenadmin.services.ai.insight_service import InsightService, build_insight_provider
from ledenadmin.services.category_service import CategoryService
from ledenadmin.services.kvk_service import build_kvk_lookup
from ledenadmin.services.mail_service import build_mail_transport
from ledenadmin.services.organization_data_service import OrganizationDataService
from ledenadmin.services.organization_service import ensure_default_organization
from ledenadmin.web import platform as web_platform
from ledenadmin.web import routes as web_routes
from ledenadmin.web import users as web_users
from ledenadmin.web.security import SecurityMiddleware
from ledenadmin.web.templating import STATIC_DIR, build_templates

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, database: Database | None = None) -> FastAPI:
    """Applicatiefabriek; start met `uvicorn --factory ledenadmin.main:create_app`."""
    settings = settings or get_settings()
    database = database or Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        with database.session() as session:
            app.state.organization_id = ensure_default_organization(session)
            if purged := OrganizationDataService(session).purge_expired():
                logger.info("%s verwijderde organisatie(s) definitief gewist", purged)
        if settings.seed_default_categories:
            with database.session(app.state.organization_id) as session:
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
    app.state.kvk_lookup = build_kvk_lookup(settings.kvk_api_key, settings.kvk_api_url)
    app.state.mail_transport = build_mail_transport(
        settings.brevo_api_key, settings.mail_sender_email, settings.mail_sender_name
    )

    app.add_middleware(AuditMiddleware)
    app.add_middleware(SecurityMiddleware, secure_cookies=settings.is_production)
    register_error_handlers(app)

    # Gegevens per organisatie: web en API onder /o/{org}/...; health blijft globaal.
    app.include_router(system.public_router, prefix="/api/v1")
    org = APIRouter(prefix="/o/{org}")
    api = APIRouter(prefix="/api/v1")
    for module in (system, members, categories, donations, reports):
        api.include_router(module.router)
    org.include_router(api)
    org.include_router(web_routes.router)
    org.include_router(web_users.org_router)
    app.include_router(org)
    app.include_router(web_users.public_router)
    app.include_router(web_platform.router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
