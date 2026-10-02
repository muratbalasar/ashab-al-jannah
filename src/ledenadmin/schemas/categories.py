from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

CategoryName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]


class CategoryCreate(BaseModel):
    name: CategoryName


class SubcategoryCreate(BaseModel):
    name: CategoryName


class SubcategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool
    subcategories: list[SubcategoryRead]
