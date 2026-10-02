from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from ledenadmin.api.deps import Services, require
from ledenadmin.auth.principal import Principal
from ledenadmin.domain.enums import Permission
from ledenadmin.schemas.donations import DonationRead
from ledenadmin.schemas.members import MemberCreate, MemberRead, MemberSearch, MemberUpdate

router = APIRouter(prefix="/members", tags=["leden"])

CanRead = Annotated[Principal, Depends(require(Permission.MEMBERS_READ))]
CanWrite = Annotated[Principal, Depends(require(Permission.MEMBERS_WRITE))]


@router.get("", response_model=list[MemberRead])
def search_members(
    services: Services, _: CanRead, params: Annotated[MemberSearch, Query()]
) -> list[MemberRead]:
    members = services.members.search(params.q, params.status, params.limit, params.offset)
    return [MemberRead.model_validate(m) for m in members]


@router.post("", response_model=MemberRead, status_code=status.HTTP_201_CREATED)
def create_member(data: MemberCreate, services: Services, principal: CanWrite) -> MemberRead:
    return MemberRead.model_validate(services.members.create(data, actor=principal.name))


@router.get("/{member_id}", response_model=MemberRead)
def get_member(member_id: int, services: Services, _: CanRead) -> MemberRead:
    return MemberRead.model_validate(services.members.get(member_id))


@router.patch("/{member_id}", response_model=MemberRead)
def update_member(
    member_id: int, data: MemberUpdate, services: Services, _: CanWrite
) -> MemberRead:
    return MemberRead.model_validate(services.members.update(member_id, data))


@router.get("/{member_id}/donations", response_model=list[DonationRead])
def member_donations(
    member_id: int,
    services: Services,
    _: Annotated[Principal, Depends(require(Permission.DONATIONS_READ))],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[DonationRead]:
    services.members.get(member_id)
    return [DonationRead.from_entity(d) for d in services.donations.recent(limit, member_id)]
