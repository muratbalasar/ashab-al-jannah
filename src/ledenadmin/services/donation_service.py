from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from ledenadmin.domain.errors import BusinessRuleError, NotFoundError
from ledenadmin.domain.models import Donation, DonationChange, Payment
from ledenadmin.domain.money import format_eur, from_cents, to_cents
from ledenadmin.repositories.categories import CategoryRepository
from ledenadmin.repositories.donations import DonationQuery, DonationRepository
from ledenadmin.repositories.members import MemberRepository
from ledenadmin.schemas.donations import DonationCreate, DonationUpdate

FUTURE_TOLERANCE = timedelta(minutes=5)


@dataclass(frozen=True)
class DonationUpdateResult:
    changes: list[DonationChange]
    # Jaren (lokale tijd) van de oude en nieuwe datum; leeg als er niets is gewijzigd.
    years: frozenset[int]


def _minute(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(second=0, microsecond=0)


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

    # --- corrigeren -------------------------------------------------------------------------

    def is_online_payment(self, donation_id: int) -> bool:
        """True als de donatie uit een online betaling (Mollie) komt."""
        stmt = select(Payment.id).where(Payment.donation_id == donation_id)
        return self._session.scalar(stmt) is not None

    def changes(self, donation_id: int) -> list[DonationChange]:
        stmt = (
            select(DonationChange)
            .where(DonationChange.donation_id == donation_id)
            .order_by(DonationChange.changed_at.desc(), DonationChange.id.desc())
        )
        return list(self._session.scalars(stmt))

    def update(self, donation_id: int, data: DonationUpdate, actor: str) -> DonationUpdateResult:
        """Corrigeert een donatie en legt elk gewijzigd veld vast met de oude en nieuwe waarde.

        Bij een online betaling liggen lid, bedrag en datum vast: die komen van de betaling.
        """
        donation = self.get(donation_id)
        donated_at = self._resolve_timestamp(data.donated_at)
        # Het formulier kent alleen minuten; dezelfde minuut telt als ongewijzigd.
        if _minute(donated_at) == _minute(donation.donated_at):
            donated_at = donation.donated_at
        amount_cents = to_cents(data.amount)
        description = data.description or None

        member_changed = data.member_id != donation.member_id
        amount_changed = amount_cents != donation.amount_cents
        date_changed = donated_at != donation.donated_at
        if (member_changed or amount_changed or date_changed) and self.is_online_payment(
            donation_id
        ):
            raise BusinessRuleError(
                "Deze donatie is online betaald; lid, bedrag en datum liggen vast."
            )

        old = self._snapshot(donation)
        years = {self._local(donation.donated_at).year, self._local(donated_at).year}
        member = donation.member
        if member_changed:
            member = self._members.get(data.member_id)
            if member is None:
                raise BusinessRuleError("Kies een bestaand lid", field="member_id")
            if not member.is_active and not self._allow_inactive_members:
                raise BusinessRuleError(
                    f"Lid '{member.name}' is inactief; kies een actief lid", field="member_id"
                )
        subcategory = donation.subcategory
        if data.subcategory_id != donation.subcategory_id:
            subcategory = self._categories.get_subcategory(data.subcategory_id)
            if (
                subcategory is None
                or not subcategory.is_active
                or not subcategory.category.is_active
            ):
                raise BusinessRuleError(
                    "Kies een geldige categorie en subcategorie", "subcategory_id"
                )
        donation.member = member
        donation.subcategory = subcategory
        donation.amount_cents = amount_cents
        donation.donated_at = donated_at
        donation.description = description

        new = self._snapshot(donation)
        changes = [
            DonationChange(
                donation_id=donation.id,
                changed_by=actor[:200],
                field=field,
                old_value=old[field][:600],
                new_value=new[field][:600],
            )
            for field in old
            if old[field] != new[field]
        ]
        if not changes:
            self._session.rollback()
            return DonationUpdateResult([], frozenset())
        self._session.add_all(changes)
        self._session.commit()
        return DonationUpdateResult(changes, frozenset(years))

    def _local(self, value: datetime) -> datetime:
        return value.astimezone(self._tz)

    def _snapshot(self, donation: Donation) -> dict[str, str]:
        """Leesbare waarden per veld, zoals ze in de wijzigingsgeschiedenis komen."""
        return {
            "Lid": f"{donation.member.name} ({donation.member.id})",
            "Categorie": f"{donation.category.name} – {donation.subcategory.name}",
            "Bedrag": format_eur(from_cents(donation.amount_cents)),
            "Datum": self._local(donation.donated_at).strftime("%d-%m-%Y %H:%M"),
            "Omschrijving": donation.description or "–",
        }

    def _resolve_timestamp(self, value: datetime | None) -> datetime:
        now = self._clock()
        if value is None:
            return now
        if value.tzinfo is None:
            value = value.replace(tzinfo=self._tz)
        if value > now + FUTURE_TOLERANCE:
            raise BusinessRuleError("De datum mag niet in de toekomst liggen", field="donated_at")
        return value.astimezone(UTC)
