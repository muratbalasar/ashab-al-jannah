from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ledenadmin.domain.enums import MemberStatus
from ledenadmin.domain.models import Member


class MemberRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, member_id: int) -> Member | None:
        return self._session.get(Member, member_id)

    def get_by_email(self, email: str) -> Member | None:
        return self._session.scalar(select(Member).where(Member.email == email))

    def add(self, member: Member) -> Member:
        self._session.add(member)
        self._session.flush()
        return member

    def search(
        self,
        text: str | None = None,
        status: MemberStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Member]:
        stmt = select(Member)
        if text:
            pattern = f"%{text.strip().lower()}%"
            stmt = stmt.where(
                or_(func.lower(Member.name).like(pattern), func.lower(Member.email).like(pattern))
            )
        if status:
            stmt = stmt.where(Member.status == status)
        stmt = stmt.order_by(Member.name, Member.id).limit(limit).offset(offset)
        return list(self._session.scalars(stmt))
