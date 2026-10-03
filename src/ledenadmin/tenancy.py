"""Scheiding van gegevens tussen organisaties (stichtingen).

Elke sessie hoort bij precies één organisatie (`session.info["organization_id"]`). Alle
ORM-queries op tabellen met `TenantMixin` krijgen automatisch een filter op die organisatie,
en nieuwe rijen krijgen automatisch de juiste `organization_id`. Een sessie zonder organisatie
mag alleen tenant-tabellen raken als hij expliciet als platformsessie is gemarkeerd.
"""

from sqlalchemy import ForeignKey, Integer, event
from sqlalchemy.orm import (
    Mapped,
    ORMExecuteState,
    Session,
    declared_attr,
    mapped_column,
    with_loader_criteria,
)

ORG_KEY = "organization_id"
PLATFORM_KEY = "platform"


class TenantContextError(RuntimeError):
    """Een query op organisatiegegevens zonder organisatiecontext; altijd een programmeerfout."""


class TenantMixin:
    @declared_attr
    def organization_id(cls) -> Mapped[int]:
        return mapped_column(
            Integer,
            ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        )


def bind(session: Session, organization_id: int) -> Session:
    session.info[ORG_KEY] = organization_id
    session.info.pop(PLATFORM_KEY, None)
    return session


def as_platform(session: Session) -> Session:
    """Sessie voor platformtaken (beheer van organisaties, opschonen) over alle organisaties."""
    session.info.pop(ORG_KEY, None)
    session.info[PLATFORM_KEY] = True
    return session


def current_organization_id(session: Session) -> int | None:
    return session.info.get(ORG_KEY)


def _touches_tenant_data(state: ORMExecuteState) -> bool:
    return any(
        isinstance(m.class_, type) and issubclass(m.class_, TenantMixin) for m in state.all_mappers
    )


@event.listens_for(Session, "do_orm_execute")
def _filter_on_organization(state: ORMExecuteState) -> None:
    if not (state.is_select or state.is_update or state.is_delete):
        return
    organization_id = state.session.info.get(ORG_KEY)
    if organization_id is None:
        if state.session.info.get(PLATFORM_KEY) or not _touches_tenant_data(state):
            return
        raise TenantContextError("Query op organisatiegegevens zonder organisatiecontext")
    state.statement = state.statement.options(
        with_loader_criteria(
            TenantMixin,
            lambda cls: cls.organization_id == organization_id,
            include_aliases=True,
            track_closure_variables=True,
        )
    )


@event.listens_for(Session, "before_flush")
def _stamp_organization(session: Session, _context, _instances) -> None:
    organization_id = session.info.get(ORG_KEY)
    for obj in list(session.new) + list(session.dirty):
        if not isinstance(obj, TenantMixin):
            continue
        if organization_id is None:
            if session.info.get(PLATFORM_KEY) and obj.organization_id is not None:
                continue
            raise TenantContextError("Opslaan van organisatiegegevens zonder organisatiecontext")
        if obj.organization_id is None:
            obj.organization_id = organization_id
        elif obj.organization_id != organization_id:
            raise TenantContextError(
                "Gegevens van een andere organisatie mogen niet worden opgeslagen"
            )
