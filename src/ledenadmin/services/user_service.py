from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ledenadmin.auth.principal import Identity, Principal
from ledenadmin.db import utcnow
from ledenadmin.domain.enums import OrganizationStatus, Role
from ledenadmin.domain.models import Membership, Organization, User
from ledenadmin.services.organization_service import DEFAULT_SLUG

# Niet bij elk verzoek schrijven: 'laatst aangemeld' alleen bijwerken na deze tijd.
LOGIN_TOUCH_INTERVAL = timedelta(minutes=5)


class UserService:
    """Gebruikers en hun rollen per organisatie. Werkt met een platformsessie (geen tenant)."""

    def __init__(self, session: Session, superadmins: frozenset[str] = frozenset()) -> None:
        self._session = session
        self._superadmins = superadmins

    def upsert(self, identity: Identity) -> User:
        user = self._session.scalar(
            select(User).where(User.issuer == identity.issuer, User.subject == identity.subject)
        )
        now = utcnow()
        if user is None:
            user = User(
                issuer=identity.issuer,
                subject=identity.subject,
                email=identity.email,
                display_name=identity.name[:200],
                last_login_at=now,
            )
            self._session.add(user)
        else:
            if identity.email and user.email != identity.email:
                user.email = identity.email
            if user.display_name != identity.name[:200]:
                user.display_name = identity.name[:200]
            if user.last_login_at is None or now - user.last_login_at > LOGIN_TOUCH_INTERVAL:
                user.last_login_at = now
        self._session.flush()
        return user

    def roles_in(self, user: User, organization_id: int) -> frozenset[Role]:
        values = self._session.scalars(
            select(Membership.role).where(
                Membership.user_id == user.id, Membership.organization_id == organization_id
            )
        )
        known = {r.value: r for r in Role}
        return frozenset(known[v] for v in values if v in known)

    def grant(self, user: User, organization_id: int, roles: frozenset[Role]) -> None:
        existing = self.roles_in(user, organization_id)
        for role in roles - existing:
            self._session.add(
                Membership(user_id=user.id, organization_id=organization_id, role=role.value)
            )
        self._session.flush()

    def organizations(self, user: User) -> list[Organization]:
        """Actieve organisaties waar de gebruiker een rol heeft, op naam gesorteerd."""
        return list(
            self._session.scalars(
                select(Organization)
                .join(Membership, Membership.organization_id == Organization.id)
                .where(
                    Membership.user_id == user.id,
                    Organization.status == OrganizationStatus.ACTIVE,
                )
                .distinct()
                .order_by(Organization.name)
            )
        )

    def is_superadmin(self, identity: Identity) -> bool:
        return identity.key in self._superadmins

    def principal(self, identity: Identity, organization: Organization | None) -> Principal:
        """Bouwt de principal voor `organization`; rollen komen uit de lidmaatschappen.

        Uitzondering: rollen uit het token (Entra app-rollen, of de dev-headers) gelden in de
        standaardorganisatie en worden daar vastgelegd, zodat een bestaande installatie na
        de migratie blijft werken. Voor andere organisaties tellen alleen lidmaatschappen.
        """
        user = self.upsert(identity)
        roles: frozenset[Role] = frozenset()
        member_id: int | None = None
        if organization is not None:
            if identity.claimed_roles and organization.slug == DEFAULT_SLUG:
                self.grant(user, organization.id, identity.claimed_roles)
                roles = identity.claimed_roles
            else:
                roles = self.roles_in(user, organization.id)
            member_id = self.member_id_in(user, organization.id)
        self._session.commit()
        return Principal(
            name=identity.name,
            roles=roles,
            user_id=user.id,
            organization_id=organization.id if organization else None,
            is_superadmin=self.is_superadmin(identity),
            member_id=member_id,
        )

    def member_id_in(self, user: User, organization_id: int) -> int | None:
        return self._session.scalar(
            select(Membership.member_id).where(
                Membership.user_id == user.id,
                Membership.organization_id == organization_id,
                Membership.role == Role.LID.value,
                Membership.member_id.is_not(None),
            )
        )
