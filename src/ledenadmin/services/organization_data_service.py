"""AVG: export van alle gegevens van een organisatie, zacht verwijderen, herstellen en wissen."""

import csv
import io
import json
import logging
import zipfile
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ledenadmin.db import utcnow
from ledenadmin.domain.enums import OrganizationStatus
from ledenadmin.domain.errors import BusinessRuleError, NotFoundError
from ledenadmin.domain.models import (
    AuditLog,
    Category,
    Donation,
    Invitation,
    Member,
    MemberField,
    MemberFieldValue,
    Membership,
    Organization,
    Subcategory,
    User,
)
from ledenadmin.tenancy import as_platform

logger = logging.getLogger(__name__)

DELETE_GRACE = timedelta(days=30)
# Volgorde van wissen: eerst wat naar andere tabellen verwijst.
TENANT_TABLES = (MemberFieldValue, Donation, MemberField, Subcategory, Category, Member)


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value else ""


def _csv(rows: list[dict]) -> str:
    buffer = io.StringIO()
    if rows:
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    # BOM zodat Excel de UTF-8-tekens goed toont.
    return "\ufeff" + buffer.getvalue()


class OrganizationDataService:
    """Werkt met een platformsessie en filtert overal expliciet op organization_id."""

    def __init__(self, session: Session) -> None:
        self._session = as_platform(session)

    def _organization(self, organization_id: int) -> Organization:
        organization = self._session.get(Organization, organization_id)
        if organization is None:
            raise NotFoundError("Organisatie niet gevonden")
        return organization

    # --- export -----------------------------------------------------------------------------

    def export(self, organization_id: int) -> bytes:
        """ZIP met één CSV per onderwerp en alles samen in export.json."""
        organization = self._organization(organization_id)
        s, org = self._session, organization_id

        def rows(model):
            return list(s.scalars(select(model).where(model.organization_id == org)))

        categories = {c.id: c.name for c in rows(Category)}
        subcategories = rows(Subcategory)
        sub_names = {sc.id: (categories.get(sc.category_id, ""), sc.name) for sc in subcategories}
        fields = rows(MemberField)
        field_labels = {f.id: f.label for f in fields}
        values: dict[int, dict[str, str]] = {}
        for v in rows(MemberFieldValue):
            values.setdefault(v.member_id, {})[
                field_labels.get(v.field_id, str(v.field_id))
            ] = v.value
        data = {
            "organisatie": {
                "naam": organization.name,
                "slug": organization.slug,
                "kvk_nummer": organization.kvk_number,
                "plaats": organization.city,
                "contact_email": organization.contact_email,
                "aangemaakt": _iso(organization.created_at),
                "geexporteerd": _iso(utcnow()),
            },
            "leden": [
                {
                    "id": m.id,
                    "naam": m.name,
                    "email": m.email,
                    "status": m.status.value,
                    "aangemaakt": _iso(m.created_at),
                    **{f"veld: {k}": v for k, v in values.get(m.id, {}).items()},
                }
                for m in rows(Member)
            ],
            "donaties": [
                {
                    "id": d.id,
                    "lid_id": d.member_id,
                    "categorie": sub_names.get(d.subcategory_id, ("", ""))[0],
                    "subcategorie": sub_names.get(d.subcategory_id, ("", ""))[1],
                    "bedrag": str(d.amount),
                    "datum": _iso(d.donated_at),
                    "omschrijving": d.description or "",
                    "geregistreerd_door": d.created_by,
                }
                for d in rows(Donation)
            ],
            "categorieen": [
                {
                    "categorie": categories.get(sc.category_id, ""),
                    "subcategorie": sc.name,
                    "actief": sc.is_active,
                }
                for sc in subcategories
            ],
            "ledenvelden": [
                {"label": f.label, "type": f.field_type, "actief": f.is_active} for f in fields
            ],
            "gebruikers": [
                {"naam": u.display_name, "email": u.email or "", "rol": m.role}
                for u, m in s.execute(
                    select(User, Membership)
                    .join(Membership, Membership.user_id == User.id)
                    .where(Membership.organization_id == org)
                    .order_by(User.display_name)
                )
            ],
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("export.json", json.dumps(data, ensure_ascii=False, indent=2))
            for key in ("leden", "donaties", "categorieen", "ledenvelden", "gebruikers"):
                archive.writestr(f"{key}.csv", _csv(data[key]))
        return buffer.getvalue()

    # --- verwijderen ------------------------------------------------------------------------

    def soft_delete(self, organization_id: int) -> Organization:
        organization = self._organization(organization_id)
        organization.status = OrganizationStatus.DELETED.value
        organization.deleted_at = utcnow()
        self._session.commit()
        logger.info("Organisatie %s zacht verwijderd", organization.slug)
        return organization

    def restore(self, organization_id: int) -> None:
        organization = self._organization(organization_id)
        if organization.status != OrganizationStatus.DELETED:
            raise BusinessRuleError("Deze organisatie is niet verwijderd")
        organization.status = OrganizationStatus.ACTIVE.value
        organization.deleted_at = None
        self._session.commit()

    def purge(self, organization_id: int) -> None:
        """Wist de organisatie en al haar gegevens definitief."""
        organization = self._organization(organization_id)
        if organization.status != OrganizationStatus.DELETED:
            raise BusinessRuleError("Alleen een verwijderde organisatie kan worden gewist")
        s = self._session
        s.execute(delete(Invitation).where(Invitation.organization_id == organization_id))
        s.execute(delete(Membership).where(Membership.organization_id == organization_id))
        for model in TENANT_TABLES:
            s.execute(delete(model).where(model.organization_id == organization_id))
        s.execute(delete(AuditLog).where(AuditLog.organization_id == organization_id))
        s.delete(organization)
        s.commit()
        logger.info("Organisatie %s definitief gewist", organization.slug)

    def purge_expired(self, now: datetime | None = None) -> int:
        cutoff = (now or utcnow()) - DELETE_GRACE
        expired = list(
            self._session.scalars(
                select(Organization.id).where(
                    Organization.status == OrganizationStatus.DELETED,
                    Organization.deleted_at < cutoff,
                )
            )
        )
        for organization_id in expired:
            self.purge(organization_id)
        return len(expired)

    # --- platformoverzicht ------------------------------------------------------------------

    def overview(self) -> list[dict]:
        """Per organisatie alleen aantallen en data; geen persoonsgegevens."""
        users = (
            select(func.count(func.distinct(Membership.user_id)))
            .where(Membership.organization_id == Organization.id)
            .scalar_subquery()
        )
        members = (
            select(func.count(Member.id))
            .where(Member.organization_id == Organization.id)
            .scalar_subquery()
        )
        last_activity = (
            select(func.max(AuditLog.at))
            .where(AuditLog.organization_id == Organization.id)
            .scalar_subquery()
        )
        rows = self._session.execute(
            select(Organization, users, members, last_activity).order_by(Organization.name)
        ).all()
        return [
            {
                "id": o.id,
                "slug": o.slug,
                "name": o.name,
                "kvk_number": o.kvk_number,
                "kvk_verified": o.kvk_verified_at is not None,
                "city": o.city,
                "status": o.status,
                "created_at": o.created_at,
                "deleted_at": o.deleted_at,
                "purge_at": o.deleted_at + DELETE_GRACE if o.deleted_at else None,
                "users": user_count,
                "members": member_count,
                "last_activity": last,
            }
            for o, user_count, member_count, last in rows
        ]
