from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

Amount = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class DonationCreate(BaseModel):
    member_id: int = Field(gt=0)
    subcategory_id: int = Field(gt=0)
    amount: Amount
    donated_at: datetime | None = Field(
        default=None,
        description="Tijdstip; zonder tijdzone geldt de ingestelde tijdzone. Leeg = nu.",
    )
    description: Description | None = None


class DonationUpdate(DonationCreate):
    """Correctie van een bestaande donatie; alle velden worden opnieuw opgegeven."""

    donated_at: datetime


class DonationRead(BaseModel):
    id: int
    member_id: int
    member_name: str
    category_id: int
    category: str
    subcategory_id: int
    subcategory: str
    amount: Decimal
    donated_at: datetime
    description: str | None
    created_by: str
    created_at: datetime

    @classmethod
    def from_entity(cls, donation) -> "DonationRead":
        return cls(
            id=donation.id,
            member_id=donation.member_id,
            member_name=donation.member.name,
            category_id=donation.category.id,
            category=donation.category.name,
            subcategory_id=donation.subcategory_id,
            subcategory=donation.subcategory.name,
            amount=donation.amount,
            donated_at=donation.donated_at,
            description=donation.description,
            created_by=donation.created_by,
            created_at=donation.created_at,
        )
