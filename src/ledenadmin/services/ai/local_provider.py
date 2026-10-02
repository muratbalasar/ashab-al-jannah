from decimal import Decimal

from ledenadmin.domain.money import format_eur
from ledenadmin.services.ai.base import InsightInput


class RuleBasedInsightProvider:
    """Lokale, deterministische samenvatting zonder externe dienst."""

    name = "lokaal"
    external = False

    def generate(self, data: InsightInput) -> str:
        bullets = [
            f"In de periode {data.period} zijn {data.count} donaties ontvangen, "
            f"samen {format_eur(data.total)}"
            + (f" (gemiddeld {format_eur(data.average)})." if data.average else ".")
        ]
        if data.by_category and data.total > 0:
            top = data.by_category[0]
            share = top.total / data.total * 100
            bullets.append(
                f"Grootste categorie is '{top.label}' met {format_eur(top.total)} "
                f"({share:.0f}% van het totaal)."
            )
        bullets.extend(self._month_trend(data))
        return "\n".join(f"- {line}" for line in bullets)

    @staticmethod
    def _month_trend(data: InsightInput) -> list[str]:
        months = data.by_month
        if len(months) < 2:
            return ["Te weinig maanden voor een trendvergelijking."]
        best = max(months, key=lambda m: m.total)
        previous, last = months[-2], months[-1]
        lines = [f"Sterkste maand is {best.label} met {format_eur(best.total)}."]
        if previous.total > 0:
            change = (last.total - previous.total) / previous.total * Decimal(100)
            direction = "stijging" if change >= 0 else "daling"
            lines.append(
                f"{last.label} ten opzichte van {previous.label}: {direction} van "
                f"{abs(change):.0f}%."
            )
        return lines
