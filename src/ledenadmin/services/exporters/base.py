from typing import Protocol

from ledenadmin.schemas.reports import Report


class ReportExporter(Protocol):
    """Contract voor exports; adapters voor bijv. Moneybird of Exact Online implementeren dit."""

    media_type: str
    file_extension: str

    def export(self, report: Report) -> bytes: ...
