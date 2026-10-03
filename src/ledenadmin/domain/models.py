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
from ledenadmin.tenancy import TenantMixin


class Organization(Base):
    """Een stichting of vereniging; alle gegevens hangen onder precies één organisatie."""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(Unicode(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Unicode(200), nullable=False)
    kvk_number: Mapped[str | None] = mapped_column(Unicode(8), nullable=True, unique=True)
    status: Mapped[str] = mapped_column(Unicode(20), nullable=False, default="actief")
    contact_email: Mapped[str | None] = mapped_column(Unicode(320), nullable=True)
    city: Mapped[str | None] = mapped_column(Unicode(100), nullable=True)
    kvk_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    # Bewust geen foreign key (zie migratie 0006); alleen voor de aanmaaklimiet per gebruiker.
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    # Versleuteld met SECRET_ENCRYPTION_KEY; nooit leesbaar in de database.
    mollie_api_key_encrypted: Mapped[str | None] = mapped_column(Unicode(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class User(Base):
    """Een aangemelde persoon, herkend aan issuer + subject van de identity provider."""

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("issuer", "subject"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issuer: Mapped[str] = mapped_column(Unicode(300), nullable=False)
    subject: Mapped[str] = mapped_column(Unicode(200), nullable=False)
    email: Mapped[str | None] = mapped_column(Unicode(320), nullable=True, index=True)
    display_name: Mapped[str] = mapped_column(Unicode(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class Membership(Base):
    """Rol van een gebruiker binnen één organisatie; één rij per rol."""

    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "organization_id", "role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(Unicode(20), nullable=False)
    # Alleen bij rol 'lid': het ledenrecord van deze gebruiker.
    member_id: Mapped[int | None] = mapped_column(
        ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False
    )
    created_by: Mapped[str] = mapped_column(Unicode(200), nullable=False, default="systeem")


class Member(TenantMixin, TimestampMixin, Base):
    __tablename__ = "members"
    __table_args__ = (UniqueConstraint("organization_id", "email"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(200), nullable=False, index=True)
    email: Mapped[str] = mapped_column(Unicode(320), nullable=False)
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


class Category(TenantMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    subcategories: Mapped[list["Subcategory"]] = relationship(
        back_populates="category", order_by="Subcategory.name"
    )


class Subcategory(TenantMixin, Base):
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


class Donation(TenantMixin, TimestampMixin, Base):
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


class MemberField(TenantMixin, Base):
    """Door de beheerder gedefinieerd extra veld voor leden (bijv. telefoon of nieuwsbrief)."""

    __tablename__ = "member_fields"
    __table_args__ = (UniqueConstraint("organization_id", "label"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(Unicode(100), nullable=False)
    field_type: Mapped[str] = mapped_column(Unicode(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class MemberFieldValue(TenantMixin, Base):
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
    # Leeg bij verzoeken buiten een organisatie (bijv. platformbeheer).
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False, index=True)
    user: Mapped[str] = mapped_column(Unicode(200), nullable=False, index=True)
    action: Mapped[str] = mapped_column(Unicode(20), nullable=False, index=True)
    method: Mapped[str] = mapped_column(Unicode(10), nullable=False)
    path: Mapped[str] = mapped_column(Unicode(500), nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[str | None] = mapped_column(Unicode(2000), nullable=True)
    ip: Mapped[str | None] = mapped_column(Unicode(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Unicode(300), nullable=True)


class Payment(TenantMixin, TimestampMixin, Base):
    """Online betaling via Mollie; wordt een donatie zodra Mollie 'paid' meldt."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mollie_id: Mapped[str | None] = mapped_column(Unicode(40), nullable=True, unique=True)
    member_id: Mapped[int] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subcategory_id: Mapped[int] = mapped_column(
        ForeignKey("subcategories.id", ondelete="RESTRICT"), nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Unicode(20), nullable=False, default="open")
    donation_id: Mapped[int | None] = mapped_column(
        ForeignKey("donations.id", ondelete="SET NULL"), nullable=True
    )

    @property
    def amount(self) -> Decimal:
        return from_cents(self.amount_cents)


class Invitation(Base):
    """Uitnodiging voor een rol in een organisatie; alleen de hash van het token wordt bewaard."""

    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(Unicode(320), nullable=False)
    role: Mapped[str] = mapped_column(Unicode(20), nullable=False)
    member_id: Mapped[int | None] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), nullable=True
    )
    token_hash: Mapped[str] = mapped_column(Unicode(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    accepted_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[str] = mapped_column(Unicode(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class MailCounter(Base):
    """Aantal verstuurde mails per dag (UTC), voor de daglimiet van de maildienst."""

    __tablename__ = "mail_counters"

    day: Mapped[str] = mapped_column(Unicode(10), primary_key=True)
    sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
