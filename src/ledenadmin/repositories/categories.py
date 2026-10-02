from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ledenadmin.domain.models import Category, Donation, Subcategory


class CategoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self, include_inactive: bool = False) -> list[Category]:
        stmt = (
            select(Category).options(selectinload(Category.subcategories)).order_by(Category.name)
        )
        if not include_inactive:
            stmt = stmt.where(Category.is_active.is_(True))
        return list(self._session.scalars(stmt))

    def get(self, category_id: int) -> Category | None:
        return self._session.get(Category, category_id)

    def get_by_name(self, name: str) -> Category | None:
        return self._session.scalar(select(Category).where(Category.name == name))

    def get_subcategory(self, subcategory_id: int) -> Subcategory | None:
        return self._session.get(Subcategory, subcategory_id)

    def get_subcategory_by_name(self, category_id: int, name: str) -> Subcategory | None:
        return self._session.scalar(
            select(Subcategory).where(
                Subcategory.category_id == category_id, Subcategory.name == name
            )
        )

    def add(self, entity: Category | Subcategory) -> None:
        self._session.add(entity)
        self._session.flush()

    def delete(self, entity: Category | Subcategory) -> None:
        self._session.delete(entity)
        self._session.flush()

    def used_subcategory_ids(self) -> set[int]:
        """Subcategorieën waar al donaties op geboekt zijn (die mogen niet weg)."""
        return set(self._session.scalars(select(Donation.subcategory_id).distinct()))
