from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def to_cents(amount: Decimal) -> int:
    return int((amount.quantize(CENT, rounding=ROUND_HALF_UP) * 100).to_integral_value())


def from_cents(cents: int) -> Decimal:
    return (Decimal(cents) / 100).quantize(CENT)


def format_eur(amount: Decimal) -> str:
    """Formatteert een bedrag Nederlands, bijv. € 1.234,50."""
    text = f"{amount.quantize(CENT):,.2f}"
    return "€ " + text.replace(",", "_").replace(".", ",").replace("_", ".")
