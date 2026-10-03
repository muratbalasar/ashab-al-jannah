from sqlalchemy import select
from sqlalchemy.orm import Session

from ledenadmin.domain.models import Organization
from ledenadmin.tenancy import as_platform

DEFAULT_SLUG = "standaard"
DEFAULT_NAME = "Standaard"


def ensure_default_organization(session: Session) -> int:
    """Geeft de standaardorganisatie terug en maakt haar zo nodig aan. Idempotent.

    Tot de aanmeldflow er is (fase 3), werkt de hele app binnen deze ene organisatie.
    """
    as_platform(session)
    organization = session.scalar(select(Organization).where(Organization.slug == DEFAULT_SLUG))
    if organization is None:
        organization = Organization(slug=DEFAULT_SLUG, name=DEFAULT_NAME)
        session.add(organization)
        session.commit()
    return organization.id
