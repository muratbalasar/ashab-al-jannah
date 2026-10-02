from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from ledenadmin.api.deps import Services, require
from ledenadmin.auth.principal import Principal
from ledenadmin.domain.enums import Permission
from ledenadmin.schemas.donations import DonationCreate, DonationRead

router = APIRouter(prefix="/donations", tags=["donaties"])

CanRead = Annotated[Principal, Depends(require(Permission.DONATIONS_READ))]
CanWrite = Annotated[Principal, Depends(require(Permission.DONATIONS_WRITE))]


@router.post("", response_model=DonationRead, status_code=status.HTTP_201_CREATED)
def register_donation(
    data: DonationCreate, services: Services, principal: CanWrite
) -> DonationRead:
    return DonationRead.from_entity(services.donations.register(data, actor=principal.name))


@router.get("", response_model=list[DonationRead])
def recent_donations(
    services: Services,
    _: CanRead,
    member_id: Annotated[int | None, Query(gt=0)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[DonationRead]:
    return [DonationRead.from_entity(d) for d in services.donations.recent(limit, member_id)]


@router.get("/{donation_id}", response_model=DonationRead)
def get_donation(donation_id: int, services: Services, _: CanRead) -> DonationRead:
    return DonationRead.from_entity(services.donations.get(donation_id))
