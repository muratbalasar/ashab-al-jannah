from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def alembic_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.attributes["database_url"] = database_url
    return config


def test_migrations_match_models_and_are_reversible(tmp_path) -> None:
    config = alembic_config(f"sqlite:///{tmp_path / 'migraties.db'}")

    command.upgrade(config, "head")
    command.check(config)
    command.downgrade(config, "base")
    command.upgrade(config, "head")


def test_existing_data_moves_to_default_organization(tmp_path) -> None:
    url = f"sqlite:///{tmp_path / 'bestaand.db'}"
    config = alembic_config(url)
    command.upgrade(config, "0003")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO members (id, name, email, status, created_at, updated_at, created_by) "
                "VALUES (1, 'Jan', 'jan@x.nl', 'actief', '2026-01-01', '2026-01-01', 't')"
            )
        )
        conn.execute(text("INSERT INTO categories (id, name, is_active) VALUES (1, 'Zakat', 1)"))
        conn.execute(
            text(
                "INSERT INTO audit_log (at, user, action, method, path) "
                "VALUES ('2026-01-01', 'x', 'weergave', 'GET', '/')"
            )
        )

    command.upgrade(config, "head")

    with engine.begin() as conn:
        assert conn.execute(text("SELECT slug FROM organizations")).scalars().all() == ["standaard"]
        for table in ("members", "categories", "audit_log"):
            assert conn.execute(text(f"SELECT organization_id FROM {table}")).scalar() == 1
        conn.execute(
            text(
                "INSERT INTO organizations (id, slug, name, status, created_at) "
                "VALUES (2, 'b', 'B', 'actief', '2026-01-01')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO members (name, email, status, created_at, updated_at, created_by, "
                "organization_id) VALUES ('Jan', 'jan@x.nl', 'actief', '2026-01-01', '2026-01-01', "
                "'t', 2)"
            )
        )
    engine.dispose()
