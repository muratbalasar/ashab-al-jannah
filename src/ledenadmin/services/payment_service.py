"""Online doneren via Mollie, met de eigen API-sleutel van elke stichting.

Het geld gaat rechtstreeks naar de Mollie-rekening van de stichting; het platform bewaart alleen
de (versleutelde) sleutel en de betaalstatus.
"""

import json
import logging
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from ledenadmin.db import utcnow
from ledenadmin.domain.errors import BusinessRuleError, NotFoundError
from ledenadmin.domain.models import Donation, Member, Organization, Payment, Subcategory
from ledenadmin.domain.money import to_cents

logger = logging.getLogger(__name__)

KEY_PATTERN = re.compile(r"^(live|test)_[A-Za-z0-9]{20,}$")
MIN_AMOUNT = Decimal("1.00")
MAX_AMOUNT = Decimal("10000.00")
TIMEOUT_SECONDS = 10
PAID = "paid"
FINAL_FAILED = {"canceled", "expired", "failed"}
ONLINE_DESCRIPTION = "Online betaald (Mollie)"


class MollieError(Exception):
    pass


# ── Versleuteling van de sleutel ─────────────────────────────────────────────


class SecretBox:
    def __init__(self, key: str | None) -> None:
        self._fernet = Fernet(key.encode()) if key else None

    @property
    def enabled(self) -> bool:
        return self._fernet is not None

    def encrypt(self, value: str) -> str:
        if self._fernet is None:
            raise BusinessRuleError(
                "Online betalen is op dit platform nog niet ingeschakeld "
                "(SECRET_ENCRYPTION_KEY ontbreekt). Neem contact op met de platformbeheerder."
            )
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, token: str) -> str | None:
        if self._fernet is None:
            return None
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken:
            logger.error("Mollie-sleutel kan niet worden ontsleuteld (andere sleutel?)")
            return None


# ── Mollie API ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MolliePayment:
    id: str
    status: str
    checkout_url: str | None
    amount: Decimal
    metadata: dict


class MollieApi(Protocol):
    def create_payment(
        self,
        api_key: str,
        amount: Decimal,
        description: str,
        redirect_url: str,
        webhook_url: str | None,
        metadata: dict,
    ) -> MolliePayment: ...

    def get_payment(self, api_key: str, payment_id: str) -> MolliePayment: ...

    def check_key(self, api_key: str) -> bool: ...


class HttpMollieApi:
    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")

    def _call(self, api_key: str, method: str, path: str, body: dict | None = None) -> dict:
        request = Request(  # noqa: S310 - vaste https-URL uit de configuratie
            f"{self._base}{path}",
            data=json.dumps(body).encode() if body is not None else None,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method=method,
        )
        try:
            with urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
                return json.loads(response.read())
        except HTTPError as exc:
            logger.warning("Mollie gaf status %s op %s %s", exc.code, method, path)
            raise MollieError(str(exc.code)) from exc
        except (URLError, TimeoutError, ValueError) as exc:
            raise MollieError("onbereikbaar") from exc

    @staticmethod
    def _parse(data: dict) -> MolliePayment:
        return MolliePayment(
            id=data["id"],
            status=data["status"],
            checkout_url=((data.get("_links") or {}).get("checkout") or {}).get("href"),
            amount=Decimal(data["amount"]["value"]),
            metadata=data.get("metadata") or {},
        )

    def create_payment(self, api_key, amount, description, redirect_url, webhook_url, metadata):
        body = {
            "amount": {"currency": "EUR", "value": f"{amount:.2f}"},
            "description": description,
            "redirectUrl": redirect_url,
            "metadata": metadata,
        }
        if webhook_url:
            body["webhookUrl"] = webhook_url
        return self._parse(self._call(api_key, "POST", "/payments", body))

    def get_payment(self, api_key, payment_id):
        return self._parse(self._call(api_key, "GET", f"/payments/{payment_id}"))

    def check_key(self, api_key):
        try:
            self._call(api_key, "GET", "/methods")
            return True
        except MollieError:
            return False


# ── Service ──────────────────────────────────────────────────────────────────


class PaymentService:
    """Werkt met een sessie die aan de organisatie gebonden is."""

    def __init__(
        self, session: Session, organization: Organization, api: MollieApi, box: SecretBox
    ) -> None:
        self._session = session
        self._organization = organization
        self._api = api
        self._box = box

    # --- configuratie (beheerder) ----------------------------------------------------------

    def api_key(self) -> str | None:
        encrypted = self._organization.mollie_api_key_encrypted
        return self._box.decrypt(encrypted) if encrypted else None

    @property
    def enabled(self) -> bool:
        return self.api_key() is not None

    @property
    def mode(self) -> str | None:
        key = self.api_key()
        return key.split("_", 1)[0] if key else None

    def set_api_key(self, organization: Organization, key: str) -> None:
        """`organization` moet uit een platformsessie komen, zodat de wijziging wordt bewaard."""
        key = key.strip()
        if not KEY_PATTERN.match(key):
            raise BusinessRuleError(
                "Een Mollie API-sleutel begint met live_ of test_.", field="api_key"
            )
        if not self._api.check_key(key):
            raise BusinessRuleError(
                "Mollie accepteert deze sleutel niet. Controleer of u de volledige sleutel "
                "heeft gekopieerd.",
                field="api_key",
            )
        organization.mollie_api_key_encrypted = self._box.encrypt(key)

    # --- doneren (lid) ----------------------------------------------------------------------

    def start(
        self, member_id: int, subcategory_id: int, amount: Decimal, base_url: str, actor: str
    ) -> str:
        """Maakt een betaling aan en geeft de checkout-URL van Mollie terug."""
        key = self.api_key()
        if key is None:
            raise BusinessRuleError("Online doneren is bij deze stichting niet ingeschakeld.")
        if not MIN_AMOUNT <= amount <= MAX_AMOUNT or amount != amount.quantize(Decimal("0.01")):
            raise BusinessRuleError(
                f"Kies een bedrag tussen \u20ac {MIN_AMOUNT} en \u20ac {MAX_AMOUNT}.",
                field="amount",
            )
        member = self._session.get(Member, member_id)
        subcategory = self._session.get(Subcategory, subcategory_id)
        if member is None:
            raise NotFoundError("Lid niet gevonden")
        if subcategory is None or not subcategory.is_active or not subcategory.category.is_active:
            raise BusinessRuleError("Kies een categorie.", field="subcategory_id")
        payment = Payment(
            member_id=member.id,
            subcategory_id=subcategory.id,
            amount_cents=to_cents(amount),
            created_by=actor[:200],
        )
        self._session.add(payment)
        self._session.flush()
        slug = self._organization.slug
        base = base_url.rstrip("/")
        # Mollie kan localhost niet bereiken; zonder publieke URL alleen de redirect.
        webhook = None if "localhost" in base else f"{base}/betalingen/webhook/{slug}"
        try:
            remote = self._api.create_payment(
                key,
                amount,
                f"Donatie {subcategory.category.name} - {self._organization.name}"[:255],
                f"{base}/o/{slug}/mijn/betaling/{payment.id}",
                webhook,
                {"payment_id": payment.id, "organization": slug},
            )
        except MollieError as exc:
            self._session.rollback()
            raise BusinessRuleError(
                "Mollie is op dit moment niet bereikbaar. Probeer het later opnieuw."
            ) from exc
        payment.mollie_id = remote.id
        payment.status = remote.status
        self._session.commit()
        if not remote.checkout_url:
            raise BusinessRuleError("Mollie gaf geen betaalpagina terug.")
        return remote.checkout_url

    # --- status bijwerken (webhook en terugkeer) --------------------------------------------

    def refresh(self, payment: Payment) -> Payment:
        """Haalt de status op bij Mollie (nooit uit het verzoek zelf) en boekt bij 'paid'."""
        key = self.api_key()
        if key is None or payment.mollie_id is None or payment.status == PAID:
            return payment
        remote = self._api.get_payment(key, payment.mollie_id)
        if remote.amount != payment.amount:
            logger.error("Bedrag van Mollie-betaling %s wijkt af", payment.mollie_id)
            return payment
        payment.status = remote.status
        if remote.status == PAID and payment.donation_id is None:
            donation = Donation(
                member_id=payment.member_id,
                subcategory_id=payment.subcategory_id,
                amount_cents=payment.amount_cents,
                donated_at=utcnow(),
                description=ONLINE_DESCRIPTION,
                created_by="mollie",
            )
            self._session.add(donation)
            self._session.flush()
            payment.donation_id = donation.id
        self._session.commit()
        return payment

    def by_mollie_id(self, mollie_id: str) -> Payment | None:
        return self._session.scalar(select(Payment).where(Payment.mollie_id == mollie_id))

    def get_for_member(self, payment_id: int, member_id: int) -> Payment:
        payment = self._session.get(Payment, payment_id)
        if payment is None or payment.member_id != member_id:
            raise NotFoundError("Betaling niet gevonden")
        return payment
