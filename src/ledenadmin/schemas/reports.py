from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from ledenadmin.schemas.donations import DonationRead


class ReportFilter(BaseModel):
    """Rapportagefilter; begin- en einddatum zijn beide inclusief."""

    start_date: date | None = None
    end_date: date | None = None
    member_id: int | None = Field(default=None, gt=0)
    category_id: int | None = Field(default=None, gt=0)
    subcategory_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _check_period(self) -> "ReportFilter":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("De einddatum mag niet vóór de begindatum liggen")
        return self

    def describe_period(self) -> str:
        start = self.start_date.strftime("%d-%m-%Y") if self.start_date else "begin"
        end = self.end_date.strftime("%d-%m-%Y") if self.end_date else "heden"
        return f"{start} t/m {end}"


class Breakdown(BaseModel):
    key: str
    label: str
    total: Decimal
    count: int


class Report(BaseModel):
    filter: ReportFilter
    timezone: str
    total: Decimal
    count: int
    average: Decimal | None
    by_category: list[Breakdown]
    by_subcategory: list[Breakdown]
    by_month: list[Breakdown]
    by_member: list[Breakdown]
    donations: list[DonationRead]
    includes_member_details: bool = True

    @property
    def is_empty(self) -> bool:
        return self.count == 0

    def without_member_details(self) -> "Report":
        """Versie zonder persoonsgegevens, voor rollen die alleen totalen mogen zien."""
        return self.model_copy(
            update={"by_member": [], "donations": [], "includes_member_details": False}
        )


class Insight(BaseModel):
    provider: str
    external: bool
    period: str
    text: str
    warning: str | None = None
