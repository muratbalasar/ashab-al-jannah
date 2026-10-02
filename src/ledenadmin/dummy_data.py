"""Vult een (lokale) database met dummy leden en donaties voor demo en ontwikkeling.

Gebruik: python -m ledenadmin.dummy_data   (leest DATABASE_URL)
"""

import os
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ledenadmin.db import Database
from ledenadmin.domain.enums import MemberStatus
from ledenadmin.domain.models import Donation, Member, Subcategory
from ledenadmin.services.category_service import CategoryService

DUMMY_DOMAIN = "voorbeeld.nl"
DUMMY_CREATED_BY = "dummy-data"
FIRST_NAMES = [
    "Ahmed", "Fatima", "Yusuf", "Ayşe", "Mohamed", "Khadija", "Ibrahim", "Zeynep",
    "Omar", "Meryem", "Bilal", "Samira", "Hamza", "Nadia", "Emre", "Hatice",
    "Karim", "Leila", "Mustafa", "Salma",
]  # fmt: skip
LAST_NAMES = ["El Amrani", "Bouzid", "Demir", "Yılmaz", "Ouali", "Kaya"]
DUMMY_MEMBERS = [f"{first} {last}" for last in LAST_NAMES for first in FIRST_NAMES]


def _email(name: str) -> str:
    plain = name.lower().translate(str.maketrans("şçıöüğ", "scioug")).replace(" ", ".")
    return f"{plain}.dummy@{DUMMY_DOMAIN}"


def seed(session: Session, now: datetime | None = None, seed_value: int = 42) -> tuple[int, int]:
    """Voegt 120 dummy leden met donaties toe; bestaande dummy leden worden overgeslagen.

    Geeft (aantal nieuwe leden, aantal nieuwe donaties) terug.
    """
    now = now or datetime.now(UTC)
    rng = random.Random(seed_value)
    CategoryService(session).ensure_defaults()
    subcategories = list(
        session.scalars(select(Subcategory).where(Subcategory.is_active.is_(True)))
    )
    if not subcategories:
        raise RuntimeError("Geen actieve subcategorieën gevonden.")
    existing = set(session.scalars(select(Member.email)))

    members_added = donations_added = 0
    for index, name in enumerate(DUMMY_MEMBERS):
        email = _email(name)
        if email in existing:
            continue
        member = Member(
            name=name,
            email=email,
            # Eén inactief lid om ook die weergave te kunnen zien.
            status=(MemberStatus.INACTIVE if index % 10 == 9 else MemberStatus.ACTIVE),
            created_by=DUMMY_CREATED_BY,
        )
        session.add(member)
        members_added += 1
        for _ in range(rng.randint(3, 6)):
            # Verspreid over de afgelopen ~18 maanden, op een uur overdag.
            day = now - timedelta(days=rng.randint(0, 540))
            donated_at = day.replace(
                hour=rng.randint(9, 20), minute=rng.choice([0, 15, 30, 45]), second=0, microsecond=0
            )
            session.add(
                Donation(
                    member=member,
                    subcategory=rng.choice(subcategories),
                    amount_cents=rng.choice([500, 1000, 1500, 2500, 5000, 7500, 10000, 25000]),
                    donated_at=min(donated_at, now),
                    description="Dummy donatie",
                    created_by=DUMMY_CREATED_BY,
                )
            )
            donations_added += 1
    session.commit()
    return members_added, donations_added


def main() -> None:
    url = os.environ.get("DATABASE_URL", "sqlite:///./ledenadmin.db")
    database = Database(url)
    with database.session() as session:
        members, donations = seed(session)
    print(f"Dummy data: {members} leden en {donations} donaties toegevoegd.")


if __name__ == "__main__":
    main()
