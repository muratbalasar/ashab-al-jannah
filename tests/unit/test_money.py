from decimal import Decimal

import pytest

from ledenadmin.domain.money import format_eur, from_cents, to_cents


@pytest.mark.parametrize(
    ("amount", "cents"),
    [("50", 5000), ("0.01", 1), ("19.995", 2000), ("1234.5", 123450)],
)
def test_to_cents_rounds_half_up(amount: str, cents: int) -> None:
    assert to_cents(Decimal(amount)) == cents


def test_from_cents_returns_two_decimals() -> None:
    assert from_cents(5) == Decimal("0.05")
    assert str(from_cents(123450)) == "1234.50"


def test_format_eur_uses_dutch_notation() -> None:
    assert format_eur(Decimal("1234.5")) == "€ 1.234,50"
    assert format_eur(Decimal("0")) == "€ 0,00"
