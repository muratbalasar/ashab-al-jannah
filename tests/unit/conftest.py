from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ledenadmin.config import AuthMode, Settings
from ledenadmin.db import Database
from ledenadmin.main import create_app
from ledenadmin.services.category_service import CategoryService
from ledenadmin.services.organization_service import ensure_default_organization
from ledenadmin.web.security import CSRF_COOKIE


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="sqlite://",
        auth_mode=AuthMode.DEV,
        dev_user_name="tester",
        dev_user_roles="beheerder,penningmeester,bestuurder",
    )


@pytest.fixture
def database(settings: Settings) -> Iterator[Database]:
    db = Database(settings.database_url)
    db.create_all()
    yield db
    db.engine.dispose()


@pytest.fixture
def organization_id(database: Database) -> int:
    with database.session() as s:
        return ensure_default_organization(s)


@pytest.fixture
def session(database: Database, organization_id: int) -> Iterator[Session]:
    with database.session(organization_id) as s:
        CategoryService(s).ensure_defaults()
        yield s


@pytest.fixture
def client(settings: Settings, database: Database) -> Iterator[TestClient]:
    with TestClient(create_app(settings, database)) as test_client:
        yield test_client


@pytest.fixture
def csrf_client(client: TestClient) -> TestClient:
    """Client met een geldig CSRF-cookie; token beschikbaar als `client.csrf`."""
    client.get("/")
    client.csrf = client.cookies[CSRF_COOKIE]
    return client
