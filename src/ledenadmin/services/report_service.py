from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy.orm import Session

from ledenadmin.domain.models import Donation
from ledenadmin.domain.money import from_cents
from ledenadmin.repositories.donations import DonationQuery, DonationRepository
from ledenadmin.schemas.donations import DonationRead
from ledenadmin.schemas.reports import Breakdown, Report, ReportFilter

COLUMNS = [
    "id",
    "member_id",
    "member_name",
    "category_id",
    "category",
    "subcategory_id",
    "subcategory",
    "amount_cents",
    "donated_at_local",
]


class ReportService:
    """Filtert in de database en aggregeert met pandas."""

    def __init__(self, session: Session, tz: ZoneInfo) -> None:
        self._donations = DonationRepository(session)
        self._tz = tz

    def build(self, report_filter: ReportFilter) -> Report:
        donations = self._donations.find(self._to_query(report_filter))
        frame = self.to_dataframe(donations)
        total_cents = int(frame["amount_cents"].sum()) if not frame.empty else 0
        count = len(frame)
        return Report(
            filter=report_filter,
            timezone=self._tz.key,
            total=from_cents(total_cents),
            count=count,
            average=from_cents(round(total_cents / count)) if count else None,
            by_category=self._breakdown(frame, "category_id", "category"),
            by_subcategory=self._breakdown(frame, "subcategory_id", "subcategory", "category"),
            by_month=self._by_month(frame),
            by_member=self._breakdown(frame, "member_id", "member_name"),
            donations=[DonationRead.from_entity(d) for d in donations],
        )

    def to_dataframe(self, donations: list[Donation]) -> pd.DataFrame:
        rows = [
            {
                "id": d.id,
                "member_id": d.member_id,
                "member_name": d.member.name,
                "category_id": d.category.id,
                "category": d.category.name,
                "subcategory_id": d.subcategory_id,
                "subcategory": d.subcategory.name,
                "amount_cents": d.amount_cents,
                "donated_at_local": d.donated_at.astimezone(self._tz),
            }
            for d in donations
        ]
        return pd.DataFrame(rows, columns=COLUMNS)

    def utc_bounds(self, start: date | None, end: date | None) -> tuple[datetime | None, ...]:
        """Zet inclusieve lokale datums om naar een UTC-interval [start, eind)."""
        start_utc = self._local_midnight_utc(start) if start else None
        end_utc = self._local_midnight_utc(end + timedelta(days=1)) if end else None
        return start_utc, end_utc

    def _to_query(self, report_filter: ReportFilter) -> DonationQuery:
        start_utc, end_utc = self.utc_bounds(report_filter.start_date, report_filter.end_date)
        return DonationQuery(
            start_utc=start_utc,
            end_utc=end_utc,
            member_id=report_filter.member_id,
            category_id=report_filter.category_id,
            subcategory_id=report_filter.subcategory_id,
        )

    def _local_midnight_utc(self, day: date) -> datetime:
        return datetime.combine(day, time.min, tzinfo=self._tz).astimezone(UTC)

    @staticmethod
    def _breakdown(
        frame: pd.DataFrame, key: str, label: str, parent: str | None = None
    ) -> list[Breakdown]:
        if frame.empty:
            return []
        group_keys = [key, label] + ([parent] if parent else [])
        grouped = (
            frame.groupby(group_keys, sort=False)["amount_cents"]
            .agg(["sum", "count"])
            .reset_index()
            .sort_values(["sum", label], ascending=[False, True])
        )
        return [
            Breakdown(
                key=str(row[key]),
                label=f"{row[parent]} / {row[label]}" if parent else str(row[label]),
                total=from_cents(int(row["sum"])),
                count=int(row["count"]),
            )
            for _, row in grouped.iterrows()
        ]

    @staticmethod
    def _by_month(frame: pd.DataFrame) -> list[Breakdown]:
        if frame.empty:
            return []
        months = frame["donated_at_local"].map(lambda value: value.strftime("%Y-%m"))
        grouped = frame.assign(month=months).groupby("month")["amount_cents"].agg(["sum", "count"])
        return [
            Breakdown(
                key=month,
                label=month,
                total=from_cents(int(row["sum"])),
                count=int(row["count"]),
            )
            for month, row in grouped.sort_index().iterrows()
        ]
