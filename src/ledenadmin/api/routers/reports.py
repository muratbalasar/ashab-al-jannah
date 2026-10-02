from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from ledenadmin.api.deps import Services, require
from ledenadmin.auth.principal import Principal
from ledenadmin.domain.enums import Permission
from ledenadmin.schemas.reports import Insight, Report, ReportFilter

router = APIRouter(tags=["rapportage"])

CanReadReports = Annotated[Principal, Depends(require(Permission.REPORTS_READ))]
Filter = Annotated[ReportFilter, Query()]


@router.get("/reports/summary", response_model=Report)
def report_summary(report_filter: Filter, services: Services, principal: CanReadReports) -> Report:
    return services.visible_report(principal, report_filter)


@router.get("/reports/members/{member_id}", response_model=Report)
def member_report(
    member_id: int,
    services: Services,
    _: Annotated[Principal, Depends(require(Permission.REPORTS_MEMBER_READ))],
    start_date: date | None = None,
    end_date: date | None = None,
) -> Report:
    services.members.get(member_id)
    report_filter = ReportFilter(start_date=start_date, end_date=end_date, member_id=member_id)
    return services.reports.build(report_filter)


@router.get("/reports/export.csv", response_class=Response)
def export_csv(
    report_filter: Filter,
    services: Services,
    _: Annotated[Principal, Depends(require(Permission.EXPORT))],
) -> Response:
    report = services.reports.build(report_filter)
    exporter = services.csv_exporter
    return Response(
        content=exporter.export(report),
        media_type=exporter.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="donaties.{exporter.file_extension}"'
        },
    )


@router.post("/insights", response_model=Insight)
def generate_insight(
    report_filter: ReportFilter,
    services: Services,
    principal: Annotated[Principal, Depends(require(Permission.INSIGHTS_READ))],
) -> Insight:
    return services.insights.generate(services.visible_report(principal, report_filter))
