"""E-mail versturen via Brevo, met een daglimiet; zonder sleutel wordt er niets verstuurd."""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.orm import Session

from ledenadmin.domain.models import MailCounter

logger = logging.getLogger(__name__)

BREVO_URL = "https://api.brevo.com/v3/smtp/email"
WARNING_RATIO = 0.8
TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class Mail:
    to: str
    subject: str
    text: str


class MailTransport(Protocol):
    enabled: bool

    def send(self, mail: Mail) -> bool: ...


class NoMailTransport:
    enabled = False

    def send(self, mail: Mail) -> bool:
        return False


class BrevoTransport:
    enabled = True

    def __init__(self, api_key: str, sender_email: str, sender_name: str) -> None:
        self._api_key = api_key
        self._sender = {"email": sender_email, "name": sender_name}

    def send(self, mail: Mail) -> bool:
        body = {
            "sender": self._sender,
            "to": [{"email": mail.to}],
            "subject": mail.subject,
            "textContent": mail.text,
        }
        request = Request(  # noqa: S310 - vaste https-URL
            BREVO_URL,
            data=json.dumps(body).encode(),
            headers={
                "api-key": self._api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # nosec B310
                return 200 <= response.status < 300
        except (URLError, TimeoutError):
            logger.exception("Versturen via Brevo mislukt")
            return False


class RecordingTransport:
    """Voor tests: bewaart de mails in plaats van ze te versturen."""

    enabled = True

    def __init__(self) -> None:
        self.sent: list[Mail] = []

    def send(self, mail: Mail) -> bool:
        self.sent.append(mail)
        return True


def build_mail_transport(api_key: str | None, sender_email: str, sender_name: str):
    return BrevoTransport(api_key, sender_email, sender_name) if api_key else NoMailTransport()


@dataclass(frozen=True)
class MailQuota:
    sent: int
    limit: int

    @property
    def remaining(self) -> int:
        return max(self.limit - self.sent, 0)

    @property
    def warning(self) -> bool:
        return self.sent >= self.limit * WARNING_RATIO

    @property
    def exhausted(self) -> bool:
        return self.sent >= self.limit


class MailService:
    """Telt verstuurde mails per dag over het hele platform (de limiet van Brevo is globaal)."""

    def __init__(self, session: Session, transport: MailTransport, daily_limit: int) -> None:
        self._session = session
        self._transport = transport
        self._limit = daily_limit

    @property
    def enabled(self) -> bool:
        return self._transport.enabled

    @staticmethod
    def _today() -> str:
        return datetime.now(UTC).date().isoformat()

    def quota(self) -> MailQuota:
        counter = self._session.scalar(select(MailCounter).where(MailCounter.day == self._today()))
        return MailQuota(counter.sent if counter else 0, self._limit)

    def send(self, mail: Mail) -> bool:
        """Verstuurt de mail als dat kan; False betekent: deel de link zelf."""
        if not self._transport.enabled or self.quota().exhausted:
            return False
        if not self._transport.send(mail):
            return False
        counter = self._session.get(MailCounter, self._today())
        if counter is None:
            counter = MailCounter(day=self._today(), sent=0)
            self._session.add(counter)
        counter.sent += 1
        self._session.commit()
        return True
