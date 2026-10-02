from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ledenadmin.domain.errors import ConflictError, NotFoundError
from ledenadmin.domain.models import Category, Subcategory
from ledenadmin.repositories.categories import CategoryRepository

DEFAULT_CATEGORIES: dict[str, list[str]] = {
    "Contributie": ["Jaarlijks", "Maandelijks"],
    "Donatie": ["Algemeen", "Project"],
    "Sponsoring": ["MKB", "Particulier"],
}


class CategoryService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._categories = CategoryRepository(session)

    def list(self, include_inactive: bool = False) -> list[Category]:
        return self._categories.list(include_inactive=include_inactive)

    def get_category(self, category_id: int) -> Category:
        category = self._categories.get(category_id)
        if category is None:
            raise NotFoundError(f"Categorie {category_id} bestaat niet")
        return category

    def get_subcategory(self, subcategory_id: int) -> Subcategory:
        subcategory = self._categories.get_subcategory(subcategory_id)
        if subcategory is None:
            raise NotFoundError(f"Subcategorie {subcategory_id} bestaat niet")
        return subcategory

    def create_category(self, name: str) -> Category:
        if self._categories.get_by_name(name) is not None:
            raise ConflictError(f"Categorie '{name}' bestaat al", field="name")
        category = Category(name=name)
        self._categories.add(category)
        self._commit(f"Categorie '{name}' bestaat al")
        return category

    def create_subcategory(self, category_id: int, name: str) -> Subcategory:
        category = self.get_category(category_id)
        if self._categories.get_subcategory_by_name(category.id, name) is not None:
            raise ConflictError(f"Subcategorie '{name}' bestaat al in '{category.name}'", "name")
        subcategory = Subcategory(category_id=category.id, name=name)
        self._categories.add(subcategory)
        self._commit(f"Subcategorie '{name}' bestaat al")
        return subcategory

    def update_category(
        self, category_id: int, name: str | None = None, is_active: bool | None = None
    ) -> Category:
        category = self.get_category(category_id)
        if name is not None and name != category.name:
            existing = self._categories.get_by_name(name)
            if existing is not None and existing.id != category.id:
                raise ConflictError(f"Categorie '{name}' bestaat al", field="name")
            category.name = name
        if is_active is not None:
            category.is_active = is_active
        self._commit(f"Categorie '{name}' bestaat al")
        return category

    def update_subcategory(
        self,
        category_id: int,
        subcategory_id: int,
        name: str | None = None,
        is_active: bool | None = None,
    ) -> Subcategory:
        subcategory = self.get_subcategory(subcategory_id)
        if subcategory.category_id != category_id:
            raise NotFoundError(
                f"Subcategorie {subcategory_id} hoort niet bij categorie {category_id}"
            )
        if name is not None and name != subcategory.name:
            existing = self._categories.get_subcategory_by_name(category_id, name)
            if existing is not None and existing.id != subcategory.id:
                raise ConflictError(
                    f"Subcategorie '{name}' bestaat al in '{subcategory.category.name}'", "name"
                )
            subcategory.name = name
        if is_active is not None:
            subcategory.is_active = is_active
        self._commit(f"Subcategorie '{name}' bestaat al")
        return subcategory

    def used_subcategory_ids(self) -> set[int]:
        return self._categories.used_subcategory_ids()

    def delete_category(self, category_id: int) -> None:
        """Verwijdert een categorie met haar subcategorieën, maar alleen zonder donaties."""
        category = self.get_category(category_id)
        used = self.used_subcategory_ids()
        if any(s.id in used for s in category.subcategories):
            raise ConflictError(
                f"Categorie '{category.name}' is al gebruikt bij donaties; deactiveer haar."
            )
        for subcategory in list(category.subcategories):
            self._categories.delete(subcategory)
        self._categories.delete(category)
        self._commit_delete(category.name)

    def delete_subcategory(self, category_id: int, subcategory_id: int) -> None:
        subcategory = self.get_subcategory(subcategory_id)
        if subcategory.category_id != category_id:
            raise NotFoundError(
                f"Subcategorie {subcategory_id} hoort niet bij categorie {category_id}"
            )
        if subcategory.id in self.used_subcategory_ids():
            raise ConflictError(
                f"Subcategorie '{subcategory.name}' is al gebruikt bij donaties; deactiveer haar."
            )
        self._categories.delete(subcategory)
        self._commit_delete(subcategory.name)

    def _commit_delete(self, name: str) -> None:
        # De database (RESTRICT) blijft de laatste vangnet als er net een donatie bij kwam.
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(f"'{name}' is al gebruikt bij donaties; deactiveer haar.") from exc

    def ensure_defaults(self) -> bool:
        """Vult standaardcategorieën als er nog geen categorieën zijn. Idempotent."""
        if self._categories.list(include_inactive=True):
            return False
        for category_name, subcategory_names in DEFAULT_CATEGORIES.items():
            category = Category(name=category_name)
            self._categories.add(category)
            for subcategory_name in subcategory_names:
                self._categories.add(Subcategory(category_id=category.id, name=subcategory_name))
        self._session.commit()
        return True

    def _commit(self, conflict_message: str) -> None:
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(conflict_message, field="name") from exc
