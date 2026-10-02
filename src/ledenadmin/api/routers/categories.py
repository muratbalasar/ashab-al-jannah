from typing import Annotated

from fastapi import APIRouter, Depends, status

from ledenadmin.api.deps import CurrentPrincipal, Services, require
from ledenadmin.auth.principal import Principal
from ledenadmin.domain.enums import Permission
from ledenadmin.schemas.categories import (
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
    SubcategoryCreate,
    SubcategoryRead,
    SubcategoryUpdate,
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


@router.patch("/{category_id}", response_model=CategoryRead)
def update_category(
    category_id: int, data: CategoryUpdate, services: Services, _: CanWrite
) -> CategoryRead:
    category = services.categories.update_category(category_id, data.name, data.is_active)
    return CategoryRead.model_validate(category)


@router.patch("/{category_id}/subcategories/{subcategory_id}", response_model=SubcategoryRead)
def update_subcategory(
    category_id: int,
    subcategory_id: int,
    data: SubcategoryUpdate,
    services: Services,
    _: CanWrite,
) -> SubcategoryRead:
    subcategory = services.categories.update_subcategory(
        category_id, subcategory_id, data.name, data.is_active
    )
    return SubcategoryRead.model_validate(subcategory)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, services: Services, _: CanWrite) -> None:
    services.categories.delete_category(category_id)


@router.delete(
    "/{category_id}/subcategories/{subcategory_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_subcategory(
    category_id: int, subcategory_id: int, services: Services, _: CanWrite
) -> None:
    services.categories.delete_subcategory(category_id, subcategory_id)
