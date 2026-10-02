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
