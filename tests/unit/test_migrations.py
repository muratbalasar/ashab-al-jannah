from pathlib import Path

from alembic import command
from alembic.config import Config

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
