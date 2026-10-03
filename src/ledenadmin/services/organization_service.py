import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ledenadmin.db import utcnow
from ledenadmin.domain.enums import Role
from ledenadmin.domain.errors import BusinessRuleError, ConflictError
from ledenadmin.domain.models import Membership, Organization, User
from ledenadmin.services.kvk_service import KvkLookup, is_valid_format, normalize_kvk
from ledenadmin.tenancy import as_platform

logger = logging.getLogger(__name__)

DEFAULT_SLUG = "standaard"
DEFAULT_NAME = "Standaard"
# Slugs die met vaste routes zouden botsen.
RESERVED_SLUGS = frozenset({"api", "static", "platform", "aanmelden", "uitnodiging", "o"})
CREATE_INTERVAL = timedelta(hours=24)


def ensure_default_organization(session: Session) -> int:
    """Geeft de standaardorganisatie terug en maakt haar zo nodig aan. Idempotent."""
    as_platform(session)
    organization = session.scalar(select(Organization).where(Organization.slug == DEFAULT_SLUG))
    if organization is None:
        organization = Organization(slug=DEFAULT_SLUG, name=DEFAULT_NAME)
        session.add(organization)
        session.commit()
    return organization.id


def slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug[:60].strip("-") or "stichting"


@dataclass(frozen=True)
class NewOrganization:
    name: str
    kvk_number: str
    contact_email: str
    city: str | None = None


class OrganizationService:
    """Aanmelden van nieuwe organisaties (self-service). Werkt met een platformsessie."""

    def __init__(self, session: Session, kvk: KvkLookup, max_per_user: int = 3) -> None:
        self._session = as_platform(session)
        self._kvk = kvk
        self._max_per_user = max_per_user

    def create(self, user: User, data: NewOrganization) -> Organization:
        kvk_number = normalize_kvk(data.kvk_number)
        name = data.name.strip()
        if not name:
            raise BusinessRuleError("Naam is verplicht", field="name")
        if not is_valid_format(kvk_number):
            raise BusinessRuleError("Een KVK-nummer bestaat uit 8 cijfers", field="kvk_number")
        if "@" not in data.contact_email:
            raise BusinessRuleError("Vul een geldig e-mailadres in", field="contact_email")
        self._ensure_kvk_free(kvk_number)
        self._ensure_within_limit(user)

        result = self._kvk.lookup(kvk_number)
        if not result.found:
            raise BusinessRuleError(
                "Dit KVK-nummer is niet gevonden in het Handelsregister", field="kvk_number"
            )
        organization = Organization(
            slug=self._unique_slug(slugify(name)),
            name=name[:200],
            kvk_number=kvk_number,
            contact_email=data.contact_email.strip()[:320],
            city=(data.city or result.city or "").strip()[:100] or None,
            kvk_verified_at=utcnow() if result.verified else None,
            created_by_user_id=user.id,
        )
        self._session.add(organization)
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(_kvk_taken_message(), field="kvk_number") from exc
        self._session.add(
            Membership(user_id=user.id, organization_id=organization.id, role=Role.BEHEERDER.value)
        )
        self._session.commit()
        logger.info("Organisatie %s aangemaakt door gebruiker %s", organization.slug, user.id)
        return organization

    def _ensure_kvk_free(self, kvk_number: str) -> None:
        if self._session.scalar(
            select(Organization.id).where(Organization.kvk_number == kvk_number)
        ):
            raise ConflictError(_kvk_taken_message(), field="kvk_number")

    def _ensure_within_limit(self, user: User) -> None:
        created = list(
            self._session.scalars(
                select(Organization.created_at).where(Organization.created_by_user_id == user.id)
            )
        )
        if len(created) >= self._max_per_user:
            raise BusinessRuleError(
                f"U kunt maximaal {self._max_per_user} organisaties aanmaken. "
                "Neem contact op met de beheerder van het platform."
            )
        if any(utcnow() - moment < CREATE_INTERVAL for moment in created):
            raise BusinessRuleError("U kunt één organisatie per 24 uur aanmaken.")

    def _unique_slug(self, base: str) -> str:
        if base in RESERVED_SLUGS:
            base = f"{base}-stichting"
        taken = set(
            self._session.scalars(
                select(Organization.slug).where(
                    (Organization.slug == base) | Organization.slug.like(f"{base}-%")
                )
            )
        )
        slug, counter = base, 2
        while slug in taken:
            slug, counter = f"{base}-{counter}", counter + 1
        return slug

    def count(self) -> int:
        return self._session.scalar(select(func.count(Organization.id))) or 0


def _kvk_taken_message() -> str:
    return (
        "Er is al een organisatie met dit KVK-nummer. "
        "Vraag de beheerder van die organisatie om u uit te nodigen."
    )
