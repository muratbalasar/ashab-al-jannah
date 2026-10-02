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


def test_rename_and_deactivate(session) -> None:
    service = CategoryService(session)
    donatie = next(c for c in service.list() if c.name == "Donatie")
    project = next(s for s in donatie.subcategories if s.name == "Project")

    service.update_category(donatie.id, name="Giften")
    service.update_subcategory(donatie.id, project.id, name="Bouwproject", is_active=False)
    service.update_category(donatie.id, is_active=False)

    assert "Giften" not in {c.name for c in service.list()}
    giften = next(c for c in service.list(include_inactive=True) if c.name == "Giften")
    assert not giften.is_active
    assert {(s.name, s.is_active) for s in giften.subcategories} == {
        ("Algemeen", True),
        ("Bouwproject", False),
    }


def test_rename_to_own_name_is_allowed(session) -> None:
    service = CategoryService(session)
    sponsoring = next(c for c in service.list() if c.name == "Sponsoring")
    mkb = next(s for s in sponsoring.subcategories if s.name == "MKB")

    assert service.update_category(sponsoring.id, name="Sponsoring").name == "Sponsoring"
    assert service.update_subcategory(sponsoring.id, mkb.id, name="MKB").name == "MKB"


def test_rename_conflicts_and_wrong_parent(session) -> None:
    service = CategoryService(session)
    by_name = {c.name: c for c in service.list()}
    sponsoring, contributie = by_name["Sponsoring"], by_name["Contributie"]
    mkb = next(s for s in sponsoring.subcategories if s.name == "MKB")

    with pytest.raises(ConflictError):
        service.update_category(sponsoring.id, name="Contributie")
    with pytest.raises(ConflictError):
        service.update_subcategory(sponsoring.id, mkb.id, name="Particulier")
    with pytest.raises(NotFoundError):
        service.update_subcategory(contributie.id, mkb.id, is_active=False)
    with pytest.raises(NotFoundError):
        service.update_category(999, is_active=False)


def test_delete_only_when_unused(session) -> None:
    from datetime import UTC, datetime

    from factories import add_donation, add_member, subcategory

    service = CategoryService(session)
    add_donation(session, add_member(session), "10", datetime(2026, 1, 1, tzinfo=UTC))
    mkb = subcategory(session, "Sponsoring", "MKB")
    particulier = subcategory(session, "Sponsoring", "Particulier")
    donatie = next(c for c in service.list() if c.name == "Donatie")

    with pytest.raises(ConflictError, match="al gebruikt"):
        service.delete_subcategory(mkb.category_id, mkb.id)
    with pytest.raises(ConflictError, match="al gebruikt"):
        service.delete_category(mkb.category_id)
    with pytest.raises(NotFoundError):
        service.delete_subcategory(donatie.id, particulier.id)

    service.delete_subcategory(particulier.category_id, particulier.id)
    service.delete_category(donatie.id)

    names = {c.name: [s.name for s in c.subcategories] for c in service.list(True)}
    assert "Donatie" not in names
    assert names["Sponsoring"] == ["MKB"]
