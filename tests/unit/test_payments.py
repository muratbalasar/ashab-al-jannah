"""Fase 7: online doneren via Mollie (eigen API-sleutel per stichting)."""

from decimal import Decimal

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from test_my import add_member, link_lid
from test_users import add_org, grant

from ledenadmin.domain.enums import Role
from ledenadmin.domain.models import Donation, Organization, Payment, Subcategory
from ledenadmin.services.payment_service import MolliePayment, SecretBox
from ledenadmin.tenancy import as_platform
from ledenadmin.web.security import CSRF_COOKIE

LID = {"X-Dev-User": "lid", "X-Dev-Roles": ""}
BAAS = {"X-Dev-User": "baas", "X-Dev-Roles": ""}
KEY = "test_" + "a" * 30


class FakeMollie:
    def __init__(self) -> None:
        self.valid = True
        self.payments: dict[str, MolliePayment] = {}
        self.created: list[dict] = []

    def check_key(self, api_key):
        return self.valid

    def create_payment(self, api_key, amount, description, redirect_url, webhook_url, metadata):
        pid = f"tr_{len(self.payments) + 1}"
        self.payments[pid] = MolliePayment(
            pid, "open", f"https://mollie.test/{pid}", amount, metadata
        )
        self.created.append({"redirect": redirect_url, "webhook": webhook_url, "key": api_key})
        return self.payments[pid]

    def get_payment(self, api_key, payment_id):
        return self.payments[payment_id]

    def set(self, pid, status, amount=None):
        old = self.payments[pid]
        self.payments[pid] = MolliePayment(
            pid, status, None, old.amount if amount is None else amount, old.metadata
        )


@pytest.fixture
def mollie(client) -> FakeMollie:
    fake = FakeMollie()
    client.app.state.mollie_api = fake
    client.app.state.secret_box = SecretBox(Fernet.generate_key().decode())
    return fake


@pytest.fixture
def org(database) -> int:
    org = add_org(database, "stichting-p")
    grant(database, "baas", org, Role.BEHEERDER)
    return org


def csrf(client) -> str:
    client.get("/aanmelden")
    return client.cookies[CSRF_COOKIE]


def connect(client, key=KEY):
    return client.post(
        "/o/stichting-p/instellingen/mollie",
        data={"api_key": key, "csrf_token": csrf(client)},
        headers=BAAS,
        follow_redirects=False,
    )


def subcategory(database, org) -> int:
    with database.session(org) as session:
        return session.scalars(select(Subcategory)).first().id


def donate(client, sub, amount="25,00", headers=LID):
    return client.post(
        "/o/stichting-p/mijn/doneren",
        data={"amount": amount, "subcategory_id": str(sub), "csrf_token": csrf(client)},
        headers=headers,
        follow_redirects=False,
    )


def donations(database, org) -> list[Donation]:
    with database.session(org) as session:
        return list(session.scalars(select(Donation)))


def test_connect_validates_and_encrypts_key(client, database, org, mollie) -> None:
    assert connect(client, "geheim").status_code == 422
    mollie.valid = False
    assert connect(client).status_code == 422
    mollie.valid = True
    response = connect(client)
    assert response.status_code == 303 and "mollie-gekoppeld" in response.headers["location"]
    with database.session() as session:
        stored = as_platform(session).get(Organization, org).mollie_api_key_encrypted
    assert stored and KEY not in stored
    assert "testmodus" in client.get("/o/stichting-p/instellingen", headers=BAAS).text

    client.post(
        "/o/stichting-p/instellingen/mollie/ontkoppelen",
        data={"csrf_token": csrf(client)},
        headers=BAAS,
    )
    with database.session() as session:
        assert as_platform(session).get(Organization, org).mollie_api_key_encrypted is None


def test_settings_without_encryption_key(client, org) -> None:
    client.app.state.secret_box = SecretBox(None)
    html = client.get("/o/stichting-p/instellingen", headers=BAAS).text
    assert "nog niet ingeschakeld" in html


def test_donate_form_only_when_connected(client, database, org, mollie) -> None:
    link_lid(database, org, add_member(database, org, "Eigen Lid"))
    assert "Online doneren" not in client.get("/o/stichting-p/mijn", headers=LID).text
    connect(client)
    assert "Online doneren" in client.get("/o/stichting-p/mijn", headers=LID).text


def test_full_payment_flow_is_idempotent(client, database, org, mollie) -> None:
    member = add_member(database, org, "Eigen Lid")
    link_lid(database, org, member)
    connect(client)
    sub = subcategory(database, org)

    response = donate(client, sub)
    assert response.status_code == 303
    assert response.headers["location"] == "https://mollie.test/tr_1"
    assert mollie.created[0]["key"] == KEY

    mollie.set("tr_1", "paid")
    for _ in range(2):
        assert (
            client.post("/betalingen/webhook/stichting-p", data={"id": "tr_1"}).status_code == 200
        )
    found = donations(database, org)
    assert len(found) == 1
    assert found[0].member_id == member and found[0].amount == Decimal("25.00")

    with database.session(org) as session:
        payment_id = session.scalars(select(Payment)).one().id
    html = client.get(f"/o/stichting-p/mijn/betaling/{payment_id}", headers=LID).text
    assert "Hartelijk dank" in html
    assert len(donations(database, org)) == 1


def test_amount_mismatch_creates_no_donation(client, database, org, mollie) -> None:
    link_lid(database, org, add_member(database, org, "Eigen Lid"))
    connect(client)
    donate(client, subcategory(database, org))
    mollie.set("tr_1", "paid", Decimal("1.00"))
    client.post("/betalingen/webhook/stichting-p", data={"id": "tr_1"})
    assert donations(database, org) == []


@pytest.mark.parametrize(
    "slug,data",
    [("onbekend", {"id": "tr_1"}), ("stichting-p", {"id": "x"}), ("stichting-p", {"id": "tr_9"})],
)
def test_webhook_unknown_returns_200(client, org, mollie, slug, data) -> None:
    assert client.post(f"/betalingen/webhook/{slug}", data=data).status_code == 200


@pytest.mark.parametrize("amount", ["0", "abc", "20000", "1,234"])
def test_invalid_amount(client, database, org, mollie, amount) -> None:
    link_lid(database, org, add_member(database, org, "Eigen Lid"))
    connect(client)
    response = donate(client, subcategory(database, org), amount)
    assert response.headers["location"].endswith("/mijn?fout=amount")
    assert mollie.created == []


def test_other_members_payment_is_hidden(client, database, org, mollie) -> None:
    link_lid(database, org, add_member(database, org, "Eigen Lid"))
    connect(client)
    other = add_member(database, org, "Ander")
    sub = subcategory(database, org)
    with database.session(org) as session:
        payment = Payment(mollie_id="tr_x", member_id=other, subcategory_id=sub, amount_cents=500)
        session.add(payment)
        session.commit()
        payment_id = payment.id
    response = client.get(f"/o/stichting-p/mijn/betaling/{payment_id}", headers=LID)
    assert response.status_code == 404


def test_treasurer_cannot_donate_as_member(client, database, org, mollie) -> None:
    connect(client)
    grant(database, "penning", org, Role.PENNINGMEESTER)
    headers = {"X-Dev-User": "penning", "X-Dev-Roles": ""}
    assert donate(client, subcategory(database, org), headers=headers).status_code == 403
