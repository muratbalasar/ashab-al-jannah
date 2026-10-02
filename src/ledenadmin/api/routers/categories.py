from typing import Annotated

from fastapi import APIRouter, Depends, status

from ledenadmin.api.deps import CurrentPrincipal, Services, require
from ledenadmin.auth.principal import Principal
from ledenadmin.domain.enums import Permission
from ledenadmin.schemas.categories import (
    CategoryCreate,
    CategoryRead,
    SubcategoryCreate,
    SubcategoryRead,
)

router = APIRouter(prefix="/categories", tags=["categorieën"])

CanWrite = Annotated[Principal, Depends(require(Permission.CATEGORIES_WRITE))]


@router.get("", response_model=list[CategoryRead])
def list_categories(
    services: Services, _: CurrentPrincipal, include_inactive: bool = False
) -> list[CategoryRead]:
    return [CategoryRead.model_validate(c) for c in services.categories.list(include_inactive)]


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(data: CategoryCreate, services: Services, _: CanWrite) -> CategoryRead:
    category = services.categories.create_category(data.name)
    return CategoryRead(id=category.id, name=category.name, is_active=True, subcategories=[])


@router.post(
    "/{category_id}/subcategories",
    response_model=SubcategoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_subcategory(
    category_id: int, data: SubcategoryCreate, services: Services, _: CanWrite
) -> SubcategoryRead:
    subcategory = services.categories.create_subcategory(category_id, data.name)
    return SubcategoryRead.model_validate(subcategory)
