from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ledenadmin.domain.enums import MemberStatus
from ledenadmin.domain.errors import ConflictError, NotFoundError
from ledenadmin.domain.models import Member
from ledenadmin.repositories.members import MemberRepository
from ledenadmin.schemas.members import MemberCreate, MemberUpdate

EMAIL_IN_USE = "Dit e-mailadres is al in gebruik door een ander lid"


class MemberService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._members = MemberRepository(session)

    def get(self, member_id: int) -> Member:
        member = self._members.get(member_id)
        if member is None:
            raise NotFoundError(f"Lid {member_id} bestaat niet")
        return member

    def search(
        self,
        text: str | None = None,
        status: MemberStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Member]:
        return self._members.search(text=text, status=status, limit=limit, offset=offset)

    def create(self, data: MemberCreate, actor: str) -> Member:
        self._ensure_email_free(data.email)
        member = Member(name=data.name, email=data.email, status=data.status, created_by=actor)
        self._members.add(member)
        self._commit()
        return member

    def update(self, member_id: int, data: MemberUpdate) -> Member:
        member = self.get(member_id)
        changes = data.model_dump(exclude_unset=True, exclude_none=True)
        if "email" in changes and changes["email"] != member.email:
            self._ensure_email_free(changes["email"])
        for field, value in changes.items():
            setattr(member, field, value)
        self._commit()
        return member

    def _ensure_email_free(self, email: str) -> None:
        if self._members.get_by_email(email) is not None:
            raise ConflictError(EMAIL_IN_USE, field="email")

    def _commit(self) -> None:
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(EMAIL_IN_USE, field="email") from exc
