from zoneinfo import ZoneInfo

import pandas as pd

from ledenadmin.schemas.reports import Report

CSV_COLUMNS = [
    "donatie_id",
    "datum",
    "lid_id",
    "lid_naam",
    "categorie",
    "subcategorie",
    "bedrag",
    "omschrijving",
]


class CsvDonationExporter:
    """CSV voor Nederlandse spreadsheets: puntkomma, decimale komma en UTF-8 met BOM."""

    media_type = "text/csv; charset=utf-8"
    file_extension = "csv"

    def export(self, report: Report) -> bytes:
        tz = ZoneInfo(report.timezone)
        rows = [
            {
                "donatie_id": d.id,
                "datum": d.donated_at.astimezone(tz).strftime("%Y-%m-%d %H:%M"),
                "lid_id": d.member_id,
                "lid_naam": _safe(d.member_name),
                "categorie": _safe(d.category),
                "subcategorie": _safe(d.subcategory),
                "bedrag": f"{d.amount:.2f}".replace(".", ","),
                "omschrijving": _safe(d.description or ""),
            }
            for d in report.donations
        ]
        frame = pd.DataFrame(rows, columns=CSV_COLUMNS)
        return frame.to_csv(sep=";", index=False, lineterminator="\r\n").encode("utf-8-sig")


def _safe(value: str) -> str:
    """Voorkomt formule-injectie wanneer de CSV in een spreadsheet wordt geopend."""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value
