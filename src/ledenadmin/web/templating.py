from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.templating import Jinja2Templates

from ledenadmin import APP_NAME, APP_NAME_ARABIC, APP_TAGLINE
from ledenadmin.domain.enums import Permission
from ledenadmin.domain.money import format_eur

TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


def build_templates(tz: ZoneInfo) -> Jinja2Templates:
    templates = Jinja2Templates(directory=TEMPLATE_DIR)

    def localdt(value: datetime | None, fmt: str = "%d-%m-%Y %H:%M") -> str:
        return value.astimezone(tz).strftime(fmt) if value else ""

    def eur(value: Decimal | None) -> str:
        return format_eur(value) if value is not None else "–"

    templates.env.filters["localdt"] = localdt
    templates.env.filters["eur"] = eur
    templates.env.globals["Permission"] = Permission
    templates.env.globals["app_name"] = APP_NAME
    templates.env.globals["app_name_arabic"] = APP_NAME_ARABIC
    templates.env.globals["app_tagline"] = APP_TAGLINE
    return templates
