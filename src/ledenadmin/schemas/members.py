from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

from ledenadmin.domain.enums import MemberStatus

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class MemberCreate(BaseModel):
    name: Name
    email: EmailStr
    status: MemberStatus = MemberStatus.ACTIVE

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class MemberUpdate(BaseModel):
    name: Name | None = None
    email: EmailStr | None = None
    status: MemberStatus | None = None

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str | None) -> str | None:
        return value.strip().lower() if value else value


class MemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    status: MemberStatus
    created_at: datetime
    updated_at: datetime


class MemberSearch(BaseModel):
    q: str | None = Field(default=None, max_length=200)
    status: MemberStatus | None = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
