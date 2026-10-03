from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from ledenadmin.domain.errors import BusinessRuleError, NotFoundError
from ledenadmin.domain.models import Donation
from ledenadmin.domain.money import to_cents
from ledenadmin.repositories.categories import CategoryRepository
from ledenadmin.repositories.donations import DonationQuery, DonationRepository
from ledenadmin.repositories.members import MemberRepository
from ledenadmin.schemas.donations import DonationCreate

FUTURE_TOLERANCE = timedelta(minutes=5)


class DonationService:
    def __init__(
        self,
        session: Session,
        tz: ZoneInfo,
        allow_inactive_members: bool = False,
        clock=lambda: datetime.now(UTC),
    ) -> None:
        self._session = session
        self._tz = tz
        self._allow_inactive_members = allow_inactive_members
        self._clock = clock
        self._donations = DonationRepository(session)
        self._members = MemberRepository(session)
        self._categories = CategoryRepository(session)

    def get(self, donation_id: int) -> Donation:
        donation = self._donations.get(donation_id)
        if donation is None:
            raise NotFoundError(f"Donatie {donation_id} bestaat niet")
        return donation

    def recent(self, limit: int | None = 50, member_id: int | None = None) -> list[Donation]:
        return self._donations.find(DonationQuery(member_id=member_id), limit=limit)

    def count(self, member_id: int | None = None) -> int:
        return self._donations.count(member_id)

    def register(self, data: DonationCreate, actor: str) -> Donation:
        member = self._members.get(data.member_id)
        if member is None:
            raise BusinessRuleError("Kies een bestaand lid", field="member_id")
        if not member.is_active and not self._allow_inactive_members:
            raise BusinessRuleError(
                f"Lid '{member.name}' is inactief; nieuwe donaties zijn niet toegestaan",
                field="member_id",
            )

        subcategory = self._categories.get_subcategory(data.subcategory_id)
        if subcategory is None or not subcategory.is_active or not subcategory.category.is_active:
            raise BusinessRuleError("Kies een geldige categorie en subcategorie", "subcategory_id")

        donated_at = self._resolve_timestamp(data.donated_at)
        donation = Donation(
            member_id=member.id,
            subcategory_id=subcategory.id,
            amount_cents=to_cents(data.amount),
            donated_at=donated_at,
            description=data.description or None,
            created_by=actor,
        )
        self._donations.add(donation)
        self._session.commit()
        return self.get(donation.id)

    def delete_many(self, donation_ids: list[int]) -> int:
        """Verwijdert donaties definitief; onbekende ID's worden genegeerd."""
        count = self._donations.delete_many(donation_ids)
        self._session.commit()
        return count

    def _resolve_timestamp(self, value: datetime | None) -> datetime:
        now = self._clock()
        if value is None:
            return now
        if value.tzinfo is None:
            value = value.replace(tzinfo=self._tz)
        if value > now + FUTURE_TOLERANCE:
            raise BusinessRuleError("De datum mag niet in de toekomst liggen", field="donated_at")
        return value.astimezone(UTC)
