"""Rondleiding met Playwright: organisatie aanmelden, leden en donaties registreren, uitnodigen.

Draait tegen een server met AUTH_MODE=dev; start die met `demo.ps1`. Gebruikers worden
gesimuleerd met de dev-headers X-Dev-User en X-Dev-Roles. X-Dev-Roles is een onbekende rol
('geen'), zodat de gebruiker geen rollen krijgt in de standaardorganisatie; een lege header
stuurt de browser niet mee.

    python demo/demo_playwright.py --base-url http://127.0.0.1:8770 --pauze 2
"""

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta

from playwright.sync_api import Browser, Locator, Page, Playwright, sync_playwright

ORGANISATIE = {
    "kvk_number": "87654321",
    "name": "Stichting Al-Noor Demo",
    "city": "Utrecht",
    "contact_email": "info@al-noor-demo.nl",
}
BEHEERDER = "aisha"
PENNINGMEESTER = "yusuf"
PLATFORMEIGENAAR = "platformeigenaar"


@dataclass(frozen=True)
class Donatie:
    subcategorie: str
    bedrag: str
    dagen_geleden: int
    omschrijving: str


LEDEN: list[tuple[str, str, list[Donatie]]] = [
    (
        "Fatima El Amrani",
        "fatima@example.nl",
        [
            Donatie("Zakat – Zakat al-Maal", "250,00", 60, "Jaarlijkse zakat"),
            Donatie("Ramadan – Iftar", "35,00", 20, "Iftar voor 5 personen"),
        ],
    ),
    (
        "Ahmed Yilmaz",
        "ahmed@example.nl",
        [Donatie("Sadaka – Waterput", "120,00", 45, "Waterput in Niger")],
    ),
    (
        "Khadija Bakker",
        "khadija@example.nl",
        [Donatie("Contributie – Maandelijks", "15,00", 5, "Contributie")],
    ),
]

# Toont de huidige stap als ondertitel; overleeft paginawissels via sessionStorage.
BANNER_SCRIPT = """
(() => {
  const render = () => {
    const text = sessionStorage.getItem('demo-stap');
    if (!text || !document.body) return;
    let el = document.getElementById('demo-stap');
    if (!el) {
      el = document.createElement('div');
      el.id = 'demo-stap';
      el.style.cssText = 'position:fixed;left:50%;bottom:24px;transform:translateX(-50%);' +
        'z-index:99999;max-width:90vw;padding:12px 22px;border-radius:999px;' +
        'background:rgba(20,40,60,.92);color:#fff;font:600 18px/1.3 system-ui,sans-serif;' +
        'box-shadow:0 6px 24px rgba(0,0,0,.35);pointer-events:none;text-align:center';
      document.body.appendChild(el);
    }
    el.textContent = text;
  };
  window.__demoStap = (text) => { sessionStorage.setItem('demo-stap', text); render(); };
  document.addEventListener('DOMContentLoaded', render);
})();
"""


class Regie:
    """Voert UI-acties zichtbaar uit, met een pauze tussen de stappen."""

    def __init__(self, page: Page, pauze: float, typsnelheid: int) -> None:
        self.page = page
        self.pauze = pauze
        self.typsnelheid = typsnelheid

    def wacht(self, factor: float = 1.0) -> None:
        self.page.wait_for_timeout(self.pauze * 1000 * factor)

    def stap(self, tekst: str) -> None:
        print(f"  > {tekst}", flush=True)
        self.page.evaluate("t => window.__demoStap(t)", tekst)
        self.wacht()

    def markeer(self, element: Locator) -> None:
        element.scroll_into_view_if_needed()
        element.evaluate(
            "el => { el.style.outline = '3px solid #e8590c'; el.style.outlineOffset = '3px'; }"
        )
        self.wacht(0.4)

    def klik(self, element: Locator) -> None:
        self.markeer(element)
        element.click()
        self.page.wait_for_load_state()
        self.wacht()

    def typ(self, element: Locator, tekst: str) -> None:
        self.markeer(element)
        element.fill("")
        element.press_sequentially(tekst, delay=self.typsnelheid)
        self.wacht(0.3)

    def kies(self, element: Locator, *, label: str | None = None, value: str | None = None) -> None:
        self.markeer(element)
        if label is not None:
            element.select_option(label=label)
        else:
            element.select_option(value=value)
        self.wacht(0.3)

    def ga_naar(self, url: str) -> None:
        self.page.goto(url)
        self.page.wait_for_load_state()
        self.wacht()

    def link(self, naam: str) -> Locator:
        # Knoppen als <a role="button"> hebben in de toegankelijkheidsboom de rol 'button', en
        # sommige krijgen via CSS een pictogram achter de tekst; daarom matchen op het begin.
        patroon = re.compile(rf"^{re.escape(naam)}\b")
        link = self.page.get_by_role("link", name=patroon)
        return link.or_(self.page.get_by_role("button", name=patroon)).first


def nieuw_venster(browser: Browser, base_url: str, gebruiker: str, rollen: str = "geen") -> Page:
    context = browser.new_context(
        base_url=base_url,
        viewport={"width": 1280, "height": 860},
        locale="nl-NL",
        extra_http_headers={"X-Dev-User": gebruiker, "X-Dev-Roles": rollen},
    )
    context.add_init_script(BANNER_SCRIPT)
    return context.new_page()


def datum(dagen_geleden: int) -> str:
    moment = datetime.now() - timedelta(days=dagen_geleden)
    return moment.replace(hour=10, minute=30).strftime("%d-%m-%Y %H:%M")


def organisatie_aanmaken(r: Regie) -> str:
    r.ga_naar("/")
    r.stap(f"Beheerder '{BEHEERDER}' logt in en heeft nog geen organisatie")
    r.klik(r.link("Nieuwe stichting aanmaken"))

    r.stap("Nieuwe stichting aanmelden: KVK-nummer, naam, plaats en contact-e-mail")
    for veld, waarde in ORGANISATIE.items():
        r.typ(r.page.locator(f"#{veld}"), waarde)
    r.klik(r.page.get_by_role("button", name="Organisatie aanmaken"))

    slug = r.page.url.split("/o/")[1].split("/")[0]
    r.stap(f"Organisatie aangemaakt (/o/{slug}); {BEHEERDER} is automatisch beheerder")
    return slug


def vul_donatie_in(r: Regie, donatie: Donatie) -> None:
    r.kies(r.page.locator("#subcategory_id"), label=donatie.subcategorie)
    r.typ(r.page.locator("#amount"), donatie.bedrag)
    r.typ(r.page.locator("#donated_at"), datum(donatie.dagen_geleden))
    r.typ(r.page.locator("#description"), donatie.omschrijving)
    r.klik(r.page.get_by_role("button", name="Donatie opslaan"))


def lid_met_donaties(r: Regie, naam: str, email: str, donaties: list[Donatie]) -> None:
    r.klik(r.link("Leden"))
    r.stap(f"Nieuw lid registreren: {naam}")
    r.klik(r.link("Nieuw lid"))
    r.typ(r.page.locator("#name"), naam)
    r.typ(r.page.locator("#email"), email)
    r.klik(r.page.get_by_role("button", name="Lid opslaan"))

    for donatie in donaties:
        r.stap(f"Donatie voor {naam}: € {donatie.bedrag} ({donatie.subcategorie})")
        r.klik(r.link("Donatie registreren"))
        vul_donatie_in(r, donatie)
        r.klik(r.link(naam))
    r.page.locator("#donaties-kop").scroll_into_view_if_needed()
    r.stap(f"Ledenpagina van {naam} met de recente donaties")


def donatie_via_zoeken(r: Regie, naam: str, donatie: Donatie) -> None:
    r.klik(r.link("Donaties"))
    r.stap(f"Donatie registreren vanuit het donatieoverzicht; lid zoeken: {naam}")
    r.klik(r.link("Donatie registreren"))
    zoekveld = r.page.locator("[data-member-search='member_id']")
    if zoekveld.is_visible():
        r.typ(zoekveld, naam.split()[0])
    optie = r.page.locator("#member_id option", has_text=naam).first
    r.kies(r.page.locator("#member_id"), value=optie.get_attribute("value"))
    vul_donatie_in(r, donatie)


def penningmeester_uitnodigen(r: Regie) -> str:
    r.klik(r.link("Gebruikers"))
    r.stap(f"Penningmeester uitnodigen: {PENNINGMEESTER}@dev.local")
    r.typ(r.page.locator("#email"), f"{PENNINGMEESTER}@dev.local")
    r.kies(r.page.locator("#role"), label="Penningmeester")
    r.klik(r.page.get_by_role("button", name="Uitnodiging maken"))
    link = r.page.get_by_label("Uitnodigingslink")
    r.markeer(link)
    r.stap("Zonder mailserver verschijnt de uitnodigingslink op het scherm om te delen")
    return link.input_value()


def uitnodiging_accepteren(r: Regie, link: str) -> None:
    r.ga_naar(link)
    r.stap(f"Tweede venster: '{PENNINGMEESTER}' opent de uitnodigingslink")
    r.klik(r.page.get_by_role("button", name="Uitnodiging accepteren"))
    r.stap(f"{PENNINGMEESTER} is nu penningmeester en ziet de rapportage van de stichting")


def demo(playwright: Playwright, args: argparse.Namespace) -> None:
    launch: dict = {"headless": args.headless}
    if args.browser != "chromium":
        launch["channel"] = args.browser
    browser = playwright.chromium.launch(**launch)

    def regie(gebruiker: str) -> Regie:
        return Regie(nieuw_venster(browser, args.base_url, gebruiker), args.pauze, args.typsnelheid)

    try:
        beheerder = regie(BEHEERDER)
        slug = organisatie_aanmaken(beheerder)

        for naam, email, donaties in LEDEN:
            lid_met_donaties(beheerder, naam, email, donaties)

        donatie_via_zoeken(
            beheerder,
            "Ahmed Yilmaz",
            Donatie("Onderwijs – Koranonderwijs", "50,00", 2, "Koranles kinderen"),
        )
        beheerder.stap("Overzicht van alle geregistreerde donaties")

        beheerder.klik(beheerder.link("Leden"))
        beheerder.stap("Ledenoverzicht van de nieuwe stichting")

        beheerder.klik(beheerder.link("Rapportage"))
        beheerder.stap("Rapportage: totalen per categorie, dit jaar tot en met vandaag")
        beheerder.page.mouse.wheel(0, 600)
        beheerder.wacht(1.5)

        uitnodigingslink = penningmeester_uitnodigen(beheerder)

        penningmeester = regie(PENNINGMEESTER)
        uitnodiging_accepteren(penningmeester, uitnodigingslink)
        donatie_via_zoeken(
            penningmeester,
            "Khadija Bakker",
            Donatie("Noodhulp – Natuurramp", "75,00", 1, "Noodhulp aardbeving"),
        )
        penningmeester.stap("De penningmeester heeft zelf een donatie geregistreerd")

        beheerder.page.bring_to_front()
        beheerder.ga_naar(f"/o/{slug}/gebruikers")
        beheerder.stap(f"Terug bij de beheerder: {PENNINGMEESTER} staat nu bij de gebruikers")

        if args.platform:
            platform = regie(PLATFORMEIGENAAR)
            platform.ga_naar("/platform")
            platform.stap("Platformeigenaar (superadmin) ziet de nieuwe stichting in het overzicht")

        beheerder.stap("Einde van de demo")
        if not args.headless and not args.sluit:
            print("Demo klaar. Sluit het browservenster om te stoppen.", flush=True)
            beheerder.page.wait_for_event("close", timeout=0)
    finally:
        browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://127.0.0.1:8770")
    parser.add_argument("--pauze", type=float, default=1.5, help="seconden tussen UI-acties")
    parser.add_argument("--typsnelheid", type=int, default=45, help="milliseconden per teken")
    parser.add_argument("--browser", default="msedge", help="msedge, chrome of chromium")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--platform", action="store_true", help="toon ook /platform (superadmin)")
    parser.add_argument("--sluit", action="store_true", help="browser na afloop direct sluiten")
    args = parser.parse_args()
    with sync_playwright() as playwright:
        demo(playwright, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
