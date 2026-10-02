import pytest

from ledenadmin.domain.errors import ConflictError, NotFoundError
from ledenadmin.services.category_service import DEFAULT_CATEGORIES, CategoryService


def test_defaults_are_seeded_once(session) -> None:
    service = CategoryService(session)

    assert service.ensure_defaults() is False
    assert {c.name for c in service.list()} == set(DEFAULT_CATEGORIES)
    sponsoring = next(c for c in service.list() if c.name == "Sponsoring")
    assert [s.name for s in sponsoring.subcategories] == ["MKB", "Particulier"]


def test_create_category_and_subcategory(session) -> None:
    service = CategoryService(session)

    category = service.create_category("Evenementen")
    sub = service.create_subcategory(category.id, "Iftar")

    assert sub.category.name == "Evenementen"


def test_duplicate_category_and_subcategory_conflict(session) -> None:
    service = CategoryService(session)
    contributie = next(c for c in service.list() if c.name == "Contributie")

    with pytest.raises(ConflictError):
        service.create_category("Contributie")
    with pytest.raises(ConflictError):
        service.create_subcategory(contributie.id, "Jaarlijks")


def test_unknown_category_raises_not_found(session) -> None:
    with pytest.raises(NotFoundError):
        CategoryService(session).create_subcategory(999, "X")
    with pytest.raises(NotFoundError):
        CategoryService(session).get_subcategory(999)
