from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel

from ledenadmin.schemas.reports import Report

SYSTEM_PROMPT = (
    "Je bent een financieel analist voor een vereniging. Je krijgt uitsluitend "
    "geaggregeerde donatiecijfers in JSON. Schrijf in het Nederlands maximaal vijf korte "
    "bullets over opvallende trends, verschuivingen tussen categorieën en maandpatronen. "
    "Baseer je alleen op de gegeven cijfers, verzin niets, geef geen financieel of "
    "fiscaal advies en noem geen personen."
)


class AggregateLine(BaseModel):
    label: str
    total: Decimal
    count: int


class InsightInput(BaseModel):
    """Privacy-veilige invoer: alleen aggregaties, geen namen, e-mail of omschrijvingen."""

    period: str
    currency: str = "EUR"
    total: Decimal
    count: int
    average: Decimal | None
    by_category: list[AggregateLine]
    by_subcategory: list[AggregateLine]
    by_month: list[AggregateLine]
    filtered_on_single_member: bool
    filtered_on_category: bool

    @classmethod
    def from_report(cls, report: Report) -> "InsightInput":
        def lines(items) -> list[AggregateLine]:
            return [AggregateLine(label=b.label, total=b.total, count=b.count) for b in items]

        return cls(
            period=report.filter.describe_period(),
            total=report.total,
            count=report.count,
            average=report.average,
            by_category=lines(report.by_category),
            by_subcategory=lines(report.by_subcategory),
            by_month=lines(report.by_month),
            filtered_on_single_member=report.filter.member_id is not None,
            filtered_on_category=bool(report.filter.category_id or report.filter.subcategory_id),
        )


class InsightProvider(Protocol):
    name: str
    external: bool

    def generate(self, data: InsightInput) -> str: ...
