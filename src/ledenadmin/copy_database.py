"""Kopieert alle gegevens van de ene database naar de andere, bijv. van Azure SQL naar SQLite.

    python -m ledenadmin.copy_database BRON_URL DOEL_URL

Maak het doel eerst aan met het actuele schema (`alembic upgrade head` met DATABASE_URL=DOEL).
Het doel mag nog geen leden, donaties of gebruikers bevatten; overige startgegevens (zoals de
organisatie 'standaard') worden vervangen door die uit de bron.
"""

import sys

from sqlalchemy import create_engine, delete, func, insert, select

import ledenadmin.domain.models  # noqa: F401  (registreert alle tabellen)
from ledenadmin.db import Base, Database

BATCH_SIZE = 500
# Zitten hier al rijen in, dan is het doel in gebruik en stoppen we.
GUARDED_TABLES = ("members", "donations", "users")


class TargetNotEmptyError(RuntimeError):
    pass


def copy_database(source_url: str, target_url: str) -> dict[str, int]:
    """Geeft het aantal gekopieerde rijen per tabel terug."""
    source = create_engine(source_url)
    target = Database(target_url).engine
    tables = Base.metadata.sorted_tables
    copied: dict[str, int] = {}
    try:
        with target.begin() as dst:
            for name in GUARDED_TABLES:
                table = Base.metadata.tables[name]
                if dst.scalar(select(func.count()).select_from(table)):
                    raise TargetNotEmptyError(f"De doeldatabase bevat al gegevens in '{name}'")
            for table in reversed(tables):
                dst.execute(delete(table))
            with source.connect() as src:
                for table in tables:
                    rows = [dict(r._mapping) for r in src.execute(select(table))]
                    for start in range(0, len(rows), BATCH_SIZE):
                        dst.execute(insert(table), rows[start : start + BATCH_SIZE])
                    copied[table.name] = len(rows)
    finally:
        source.dispose()
        target.dispose()
    return copied


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    try:
        copied = copy_database(argv[0], argv[1])
    except TargetNotEmptyError as exc:
        print(f"Gestopt: {exc}.", file=sys.stderr)
        return 1
    for name, count in copied.items():
        print(f"{name}: {count}")
    print("Klaar.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
