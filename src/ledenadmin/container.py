from functools import cached_property

from sqlalchemy.orm import Session

from ledenadmin.auth.errors import PermissionDeniedError
from ledenadmin.auth.principal import Principal
from ledenadmin.config import Settings
from ledenadmin.domain.enums import Permission
from ledenadmin.schemas.reports import Report, ReportFilter
from ledenadmin.services.ai.insight_service import InsightService
from ledenadmin.services.category_service import CategoryService
from ledenadmin.services.donation_service import DonationService
from ledenadmin.services.exporters.base import ReportExporter
from ledenadmin.services.exporters.csv_exporter import CsvDonationExporter
from ledenadmin.services.member_field_service import MemberFieldService
from ledenadmin.services.member_service import MemberService
from ledenadmin.services.report_service import ReportService


class ServiceContainer:
    """Stelt per request de services samen; gedeeld door API en web-UI."""

    def __init__(self, session: Session, settings: Settings, insights: InsightService) -> None:
        self._session = session
        self._settings = settings
        self.insights = insights
        self.csv_exporter: ReportExporter = CsvDonationExporter()

    @cached_property
    def members(self) -> MemberService:
        return MemberService(self._session)

    @cached_property
    def member_fields(self) -> MemberFieldService:
        return MemberFieldService(self._session)

    @cached_property
    def categories(self) -> CategoryService:
        return CategoryService(self._session)

    @cached_property
    def donations(self) -> DonationService:
        return DonationService(
            self._session,
            tz=self._settings.tz,
            allow_inactive_members=self._settings.allow_donations_for_inactive_members,
        )

    @cached_property
    def reports(self) -> ReportService:
        return ReportService(self._session, tz=self._settings.tz)

    def visible_report(self, principal: Principal, report_filter: ReportFilter) -> Report:
        """Bouwt een rapport en verwijdert persoonsgegevens voor rollen zonder ledeninzage."""
        may_see_members = principal.can(Permission.REPORTS_MEMBER_READ)
        if report_filter.member_id is not None and not may_see_members:
            raise PermissionDeniedError("Je hebt geen rechten voor rapportage per lid")
        report = self.reports.build(report_filter)
        return report if may_see_members else report.without_member_details()
