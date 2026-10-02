from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Integer,
    Unicode,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ledenadmin.db import Base, UTCDateTime, utcnow
from ledenadmin.domain.enums import MemberStatus
from ledenadmin.domain.money import from_cents


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False
    )
    created_by: Mapped[str] = mapped_column(Unicode(200), nullable=False, default="systeem")


class Member(TimestampMixin, Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(200), nullable=False, index=True)
    email: Mapped[str] = mapped_column(Unicode(320), nullable=False, unique=True)
    status: Mapped[MemberStatus] = mapped_column(
        Enum(
            MemberStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=MemberStatus.ACTIVE,
    )

    donations: Mapped[list["Donation"]] = relationship(back_populates="member")

    @property
    def is_active(self) -> bool:
        return self.status == MemberStatus.ACTIVE


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(100), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    subcategories: Mapped[list["Subcategory"]] = relationship(
        back_populates="category", order_by="Subcategory.name"
    )


class Subcategory(Base):
    __tablename__ = "subcategories"
    __table_args__ = (
        UniqueConstraint("category_id", "name", name="uq_subcategories_category_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Unicode(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    category: Mapped[Category] = relationship(back_populates="subcategories")


class Donation(TimestampMixin, Base):
    __tablename__ = "donations"
    __table_args__ = (CheckConstraint("amount_cents > 0", name="amount_positive"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[int] = mapped_column(
        ForeignKey("members.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    subcategory_id: Mapped[int] = mapped_column(
        ForeignKey("subcategories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    donated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Unicode(500), nullable=True)

    member: Mapped[Member] = relationship(back_populates="donations")
    subcategory: Mapped[Subcategory] = relationship()

    @property
    def amount(self) -> Decimal:
        return from_cents(self.amount_cents)

    @property
    def category(self) -> Category:
        return self.subcategory.category


class MemberField(Base):
    """Door de beheerder gedefinieerd extra veld voor leden (bijv. telefoon of nieuwsbrief)."""

    __tablename__ = "member_fields"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(Unicode(100), nullable=False, unique=True)
    field_type: Mapped[str] = mapped_column(Unicode(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class MemberFieldValue(Base):
    __tablename__ = "member_field_values"

    member_id: Mapped[int] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), primary_key=True
    )
    field_id: Mapped[int] = mapped_column(
        ForeignKey("member_fields.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    value: Mapped[str] = mapped_column(Unicode(500), nullable=False)


class AuditLog(Base):
    """Logboek van alle gebruikersacties (aanmelden, bekijken, klikken, wijzigen, verwijderen)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False, index=True)
    user: Mapped[str] = mapped_column(Unicode(200), nullable=False, index=True)
    action: Mapped[str] = mapped_column(Unicode(20), nullable=False, index=True)
    method: Mapped[str] = mapped_column(Unicode(10), nullable=False)
    path: Mapped[str] = mapped_column(Unicode(500), nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[str | None] = mapped_column(Unicode(2000), nullable=True)
    ip: Mapped[str | None] = mapped_column(Unicode(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Unicode(300), nullable=True)
