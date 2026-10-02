import hashlib
from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.templating import Jinja2Templates

from ledenadmin import APP_NAME, APP_NAME_ARABIC, APP_TAGLINE
from ledenadmin.domain.enums import Permission
from ledenadmin.domain.money import format_eur
from ledenadmin.web.dates import iso_to_nl_date, iso_to_nl_datetime

TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


@lru_cache(maxsize=64)
def _file_hash(path: Path, mtime_ns: int, size: int) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:10]


def asset_version(path: str) -> str:
    """Versie op basis van de inhoud, voor `?v=` achter statische bestanden.

    Zo haalt de browser na een wijziging altijd de nieuwe CSS/JS op in plaats van een
    oude kopie uit de cache.
    """
    file = STATIC_DIR / path
    try:
        stat = file.stat()
    except OSError:
        return "0"
    return _file_hash(file, stat.st_mtime_ns, stat.st_size)


def build_templates(tz: ZoneInfo) -> Jinja2Templates:
    templates = Jinja2Templates(directory=TEMPLATE_DIR)

    def localdt(value: datetime | None, fmt: str = "%d-%m-%Y %H:%M") -> str:
        return value.astimezone(tz).strftime(fmt) if value else ""

    def eur(value: Decimal | None) -> str:
        return format_eur(value) if value is not None else "–"

    templates.env.filters["localdt"] = localdt
    templates.env.filters["eur"] = eur
    templates.env.filters["nl_date"] = iso_to_nl_date
    templates.env.filters["nl_datetime"] = iso_to_nl_datetime
    templates.env.globals["Permission"] = Permission
    templates.env.globals["asset_version"] = asset_version
    templates.env.globals["app_name"] = APP_NAME
    templates.env.globals["app_name_arabic"] = APP_NAME_ARABIC
    templates.env.globals["app_tagline"] = APP_TAGLINE
    return templates
