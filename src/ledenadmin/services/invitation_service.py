"""Uitnodigingen en rolbeheer binnen één organisatie."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ledenadmin.db import utcnow
from ledenadmin.domain.enums import Role
from ledenadmin.domain.errors import BusinessRuleError, ConflictError, NotFoundError
from ledenadmin.domain.models import Invitation, Member, Membership, Organization, User

INVITATION_VALIDITY = timedelta(days=7)
INVALID_LINK = "Deze uitnodiging is ongeldig, verlopen of al gebruikt."


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class CreatedInvitation:
    invitation: Invitation
    token: str


@dataclass(frozen=True)
class UserRoles:
    user: User
    roles: list[Membership]


class InvitationService:
    """Werkt met expliciete organization_id-filters; tabellen hier zijn geen tenantdata."""

    def __init__(self, session: Session, organization_id: int) -> None:
        self._session = session
        self._organization_id = organization_id

    # --- uitnodigen -------------------------------------------------------------------------

    def create(
        self, email: str, role: Role, actor: str, member_id: int | None = None
    ) -> CreatedInvitation:
        email = email.strip().lower()
        if "@" not in email or len(email) > 320:
            raise BusinessRuleError("Vul een geldig e-mailadres in", field="email")
        if role == Role.LID:
            if member_id is None:
                raise BusinessRuleError("Een uitnodiging als lid hoort bij een ledenrecord")
            member = self._session.get(Member, member_id)
            if member is None or member.organization_id != self._organization_id:
                raise NotFoundError(f"Lid {member_id} bestaat niet")
        else:
            member_id = None
        token = secrets.token_urlsafe(32)
        invitation = Invitation(
            organization_id=self._organization_id,
            email=email,
            role=role.value,
            member_id=member_id,
            token_hash=hash_token(token),
            expires_at=utcnow() + INVITATION_VALIDITY,
            created_by=actor[:200],
        )
        self._session.add(invitation)
        self._session.commit()
        return CreatedInvitation(invitation, token)

    def open_invitations(self) -> list[Invitation]:
        return list(
            self._session.scalars(
                select(Invitation)
                .where(
                    Invitation.organization_id == self._organization_id,
                    Invitation.accepted_at.is_(None),
                    Invitation.expires_at > utcnow(),
                )
                .order_by(Invitation.created_at.desc())
            )
        )

    def revoke(self, invitation_id: int) -> None:
        invitation = self._session.get(Invitation, invitation_id)
        if invitation is None or invitation.organization_id != self._organization_id:
            raise NotFoundError("Uitnodiging niet gevonden")
        self._session.delete(invitation)
        self._session.commit()

    # --- rollen -----------------------------------------------------------------------------

    def users(self) -> list[UserRoles]:
        rows = self._session.execute(
            select(User, Membership)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.organization_id == self._organization_id)
            .order_by(User.display_name, Membership.role)
        ).all()
        grouped: dict[int, UserRoles] = {}
        for user, membership in rows:
            grouped.setdefault(user.id, UserRoles(user, [])).roles.append(membership)
        return list(grouped.values())

    def remove_role(self, membership_id: int) -> None:
        membership = self._session.get(Membership, membership_id)
        if membership is None or membership.organization_id != self._organization_id:
            raise NotFoundError("Rol niet gevonden")
        if membership.role == Role.BEHEERDER.value and self._beheerder_count() <= 1:
            raise BusinessRuleError("Er moet altijd minstens één beheerder overblijven.")
        self._session.delete(membership)
        self._session.commit()

    def _beheerder_count(self) -> int:
        return (
            self._session.scalar(
                select(func.count(Membership.id)).where(
                    Membership.organization_id == self._organization_id,
                    Membership.role == Role.BEHEERDER.value,
                )
            )
            or 0
        )


def find_open_invitation(session: Session, token: str) -> Invitation | None:
    invitation = session.scalar(
        select(Invitation).where(Invitation.token_hash == hash_token(token))
    )
    if (
        invitation is None
        or invitation.accepted_at is not None
        or invitation.expires_at <= utcnow()
    ):
        return None
    return invitation


def accept_invitation(session: Session, token: str, user: User) -> Organization:
    """Koppelt de rol aan de gebruiker als het token geldig is en het e-mailadres klopt."""
    invitation = find_open_invitation(session, token)
    if invitation is None:
        raise BusinessRuleError(INVALID_LINK)
    if (user.email or "").strip().lower() != invitation.email:
        raise BusinessRuleError(
            f"Deze uitnodiging is verstuurd naar {invitation.email}. "
            "Meld u aan met dat e-mailadres."
        )
    organization = session.get(Organization, invitation.organization_id)
    if organization is None:
        raise BusinessRuleError(INVALID_LINK)
    existing = session.scalar(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.organization_id == invitation.organization_id,
            Membership.role == invitation.role,
        )
    )
    if existing is None:
        session.add(
            Membership(
                user_id=user.id,
                organization_id=invitation.organization_id,
                role=invitation.role,
                member_id=invitation.member_id,
            )
        )
    elif invitation.member_id is not None:
        existing.member_id = invitation.member_id
    invitation.accepted_at = utcnow()
    invitation.accepted_by_user_id = user.id
    try:
        session.commit()
    except Exception as exc:  # pragma: no cover - gelijktijdig accepteren
        session.rollback()
        raise ConflictError(INVALID_LINK) from exc
    return organization
