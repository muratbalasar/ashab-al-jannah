from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from ledenadmin.domain.models import Donation, Member, Subcategory
from ledenadmin.services.category_service import CategoryService


def subcategory(session: Session, category: str, name: str) -> Subcategory:
    return next(
        s
        for c in CategoryService(session).list()
        if c.name == category
        for s in c.subcategories
        if s.name == name
    )


def add_member(session: Session, name: str = "Jan Jansen", email: str | None = None) -> Member:
    member = Member(name=name, email=email or f"{name.split()[0].lower()}@example.nl")
    session.add(member)
    session.commit()
    return member


def add_donation(
    session: Session,
    member: Member,
    amount: str,
    when: datetime,
    category: str = "Sponsoring",
    sub: str = "MKB",
    description: str | None = None,
) -> Donation:
    donation = Donation(
        member_id=member.id,
        subcategory_id=subcategory(session, category, sub).id,
        amount_cents=int(Decimal(amount) * 100),
        donated_at=when.astimezone(UTC),
        description=description,
    )
    session.add(donation)
    session.commit()
    return donation
