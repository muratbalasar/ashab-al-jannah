from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import DateTime, Engine, MetaData, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator

from ledenadmin.tenancy import bind

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UTCDateTime(TypeDecorator[datetime]):
    """Slaat tijdstippen op als UTC en geeft altijd tijdzonebewuste UTC-waarden terug."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Tijdstippen moeten tijdzonebewust zijn")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC)


def utcnow() -> datetime:
    return datetime.now(UTC)


class Database:
    """Beheert de engine en sessies; vervangbaar voor tests."""

    def __init__(self, url: str) -> None:
        self.url = url
        self.engine: Engine = self._create_engine(url)
        self._session_factory = sessionmaker(self.engine, expire_on_commit=False)

    @staticmethod
    def _create_engine(url: str) -> Engine:
        if url.startswith("sqlite"):
            kwargs: dict = {"connect_args": {"check_same_thread": False}}
            if ":memory:" in url or url in ("sqlite://", "sqlite+pysqlite://"):
                kwargs["poolclass"] = StaticPool
            engine = create_engine(url, **kwargs)

            in_memory = "poolclass" in kwargs

            @event.listens_for(engine, "connect")
            def _configure_sqlite(dbapi_connection, _record) -> None:
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                # Wachten in plaats van direct "database is locked" bij gelijktijdig schrijven.
                cursor.execute("PRAGMA busy_timeout=5000")
                if not in_memory:
                    # WAL: lezers en schrijver blokkeren elkaar niet; vereist voor Litestream.
                    cursor.execute("PRAGMA journal_mode=WAL")
                cursor.close()

            return engine
        # pool_pre_ping vangt verbroken verbindingen op bij een databaseserver (bijv. PostgreSQL).
        return create_engine(url, pool_pre_ping=True, pool_recycle=1800)

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)

    def new_session(self) -> Session:
        return self._session_factory()

    @contextmanager
    def session(self, organization_id: int | None = None) -> Iterator[Session]:
        """Sessie, optioneel gebonden aan een organisatie (zie `ledenadmin.tenancy`)."""
        session = self.new_session()
        if organization_id is not None:
            bind(session, organization_id)
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
