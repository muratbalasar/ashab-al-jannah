"""Omzetting tussen de Nederlandse notatie in formulieren en ISO 8601 voor de validatie.

Onbekende invoer wordt ongewijzigd teruggegeven, zodat de schema-validatie een nette
foutmelding geeft. ISO-invoer (bijv. uit links of de API) blijft daardoor ook werken.
"""

import re
from datetime import date, datetime

_NL_DATE = r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})"
_NL_DATE_RE = re.compile(rf"^{_NL_DATE}$")
_NL_DATETIME_RE = re.compile(rf"^{_NL_DATE}(?:\s+|T)(\d{{1,2}})[:.](\d{{2}})$")
_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_ISO_DATETIME_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::\d{2})?$")


def nl_date_to_iso(text: str) -> str:
    """'7-3-2026' of '07/03/2026' → '2026-03-07'."""
    match = _NL_DATE_RE.match(text.strip())
    if not match:
        return text
    day, month, year = map(int, match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return text


def nl_datetime_to_iso(text: str) -> str:
    """'14-02-2026 10:30' → '2026-02-14T10:30'."""
    match = _NL_DATETIME_RE.match(text.strip())
    if not match:
        return text
    day, month, year, hour, minute = map(int, match.groups())
    try:
        return datetime(year, month, day, hour, minute).strftime("%Y-%m-%dT%H:%M")
    except ValueError:
        return text


def iso_to_nl_date(text: str) -> str:
    """Weergave als dd-mm-jjjj: '2026-03-07' of '7-3-2026' → '07-03-2026'.

    Ongeldige tekst blijft zoals ingevoerd, zodat de gebruiker die kan verbeteren.
    """
    match = _ISO_DATE_RE.match(nl_date_to_iso(text or ""))
    return f"{match[3]}-{match[2]}-{match[1]}" if match else (text or "")


def iso_to_nl_datetime(text: str) -> str:
    """Weergave als dd-mm-jjjj uu:mm: '2026-02-14T10:30' → '14-02-2026 10:30'."""
    match = _ISO_DATETIME_RE.match(nl_datetime_to_iso(text or ""))
    if not match:
        return text or ""
    return f"{match[3]}-{match[2]}-{match[1]} {match[4]}:{match[5]}"
