from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, delete, func, select
from sqlalchemy.orm import Session, joinedload

from ledenadmin.domain.models import Donation, Subcategory


@dataclass(frozen=True)
class DonationQuery:
    """Filter met UTC-grenzen: `start_utc` inclusief, `end_utc` exclusief."""

    start_utc: datetime | None = None
    end_utc: datetime | None = None
    member_id: int | None = None
    category_id: int | None = None
    subcategory_id: int | None = None


class DonationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, donation: Donation) -> Donation:
        self._session.add(donation)
        self._session.flush()
        return donation

    def get(self, donation_id: int) -> Donation | None:
        stmt = self._with_relations(select(Donation)).where(Donation.id == donation_id)
        return self._session.scalar(stmt)

    def find(self, query: DonationQuery, limit: int | None = None) -> list[Donation]:
        stmt = self._apply(self._with_relations(select(Donation)), query)
        stmt = stmt.order_by(Donation.donated_at.desc(), Donation.id.desc())
        if limit:
            stmt = stmt.limit(limit)
        return list(self._session.scalars(stmt).unique())

    def count(self, member_id: int | None = None) -> int:
        stmt = select(func.count(Donation.id))
        if member_id is not None:
            stmt = stmt.where(Donation.member_id == member_id)
        return self._session.scalar(stmt) or 0

    def delete_many(self, donation_ids: list[int]) -> int:
        if not donation_ids:
            return 0
        result = self._session.execute(delete(Donation).where(Donation.id.in_(donation_ids)))
        return result.rowcount or 0

    @staticmethod
    def _with_relations(stmt: Select) -> Select:
        return stmt.options(
            joinedload(Donation.member),
            joinedload(Donation.subcategory).joinedload(Subcategory.category),
        )

    @staticmethod
    def _apply(stmt: Select, query: DonationQuery) -> Select:
        if query.start_utc is not None:
            stmt = stmt.where(Donation.donated_at >= query.start_utc)
        if query.end_utc is not None:
            stmt = stmt.where(Donation.donated_at < query.end_utc)
        if query.member_id is not None:
            stmt = stmt.where(Donation.member_id == query.member_id)
        if query.subcategory_id is not None:
            stmt = stmt.where(Donation.subcategory_id == query.subcategory_id)
        if query.category_id is not None:
            stmt = stmt.join(Donation.subcategory).where(
                Subcategory.category_id == query.category_id
            )
        return stmt
