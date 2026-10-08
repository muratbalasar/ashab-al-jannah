"""Controle van KVK-nummers: altijd op formaat, en via de KVK-API als er een sleutel is."""

import json
import logging
import re
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ledenadmin.services.http import validate_https_url

logger = logging.getLogger(__name__)

KVK_PATTERN = re.compile(r"^\d{8}$")
TIMEOUT_SECONDS = 8


@dataclass(frozen=True)
class KvkResult:
    found: bool
    name: str | None = None
    city: str | None = None
    # True als de KVK-API is geraadpleegd (en niet alleen het formaat is gecontroleerd).
    verified: bool = False


class KvkLookup(Protocol):
    def lookup(self, kvk_number: str) -> KvkResult: ...


def normalize_kvk(value: str) -> str:
    return re.sub(r"[\s.-]", "", value or "")


def is_valid_format(kvk_number: str) -> bool:
    return bool(KVK_PATTERN.match(kvk_number))


class FormatOnlyLookup:
    """Gratis variant: alleen het formaat; het nummer wordt als bestaand beschouwd."""

    def lookup(self, kvk_number: str) -> KvkResult:
        return KvkResult(found=is_valid_format(kvk_number))


class KvkApiLookup:
    """KVK API 'Zoeken'. Bij een storing valt de controle terug op alleen het formaat."""

    def __init__(self, api_key: str, url: str) -> None:
        self._api_key = api_key
        self._url = validate_https_url(url)

    def lookup(self, kvk_number: str) -> KvkResult:
        if not is_valid_format(kvk_number):
            return KvkResult(found=False)
        request = Request(
            f"{self._url}?{urlencode({'kvkNummer': kvk_number})}",
            headers={"apikey": self._api_key, "Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # nosec B310
                data = json.loads(response.read())
        except HTTPError as exc:
            if exc.code == 404:
                return KvkResult(found=False, verified=True)
            logger.warning("KVK-API gaf status %s; alleen formaatcontrole", exc.code)
            return KvkResult(found=True)
        except (URLError, TimeoutError, ValueError):
            logger.warning("KVK-API niet bereikbaar; alleen formaatcontrole")
            return KvkResult(found=True)
        items = data.get("resultaten") or []
        if not items:
            return KvkResult(found=False, verified=True)
        first = items[0]
        address = (first.get("adres") or {}).get("binnenlandsAdres") or {}
        return KvkResult(
            found=True,
            name=first.get("naam"),
            city=address.get("plaats"),
            verified=True,
        )


def build_kvk_lookup(api_key: str | None, url: str) -> KvkLookup:
    return KvkApiLookup(api_key, url) if api_key else FormatOnlyLookup()
