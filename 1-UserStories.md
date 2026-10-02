# User stories en acceptatiecriteria

Deze stories beschrijven het MVP-gedrag (US01–US08) en de geplande uitbreidingen
(US09–US10). De scenario's staan in [`2-TestScenarios`](./2-TestScenarios); techniek en
rollen staan in [`README.md`](./README.md).

| Story | Status | Geautomatiseerde tests |
|---|---|---|
| US01 Leden beheren | Gebouwd | `02_ledenbeheer.robot`, `test_member_service.py` |
| US02 Donaties registreren | Gebouwd | `03_donaties.robot`, `test_donation_service.py` |
| US03 Alle apparaten | Gebouwd (handmatig gecontroleerd) | `test_web.py` |
| US04–US06 Rapportage en filters | Gebouwd | `04_rapportage.robot`, `test_report_service.py` |
| US07 AI-inzicht | Gebouwd (lokale provider standaard) | `05_ai_analyse.robot`, `test_insight_service.py` |
| US08 Gegevens veilig beheren | Gebouwd | `06_autorisatie.robot`, `test_auth.py`, `test_api.py` |
| US09 Boekhoudexport | CSV-export gebouwd; pakketkoppeling na MVP | `test_api.py` (CSV) |
| US10 Bankafschrift | Na MVP | – |

## US01 - Leden beheren

Als beheerder wil ik leden aanmaken, bekijken, zoeken en wijzigen, zodat de
ledenadministratie actueel blijft.

**Acceptatiecriteria**

- Een lid heeft een uniek ID, naam, uniek e-mailadres, status (actief/inactief)
  en aanmaak-/wijzigingsdatum.
- Naam en e-mailadres zijn verplicht; e-mail wordt gevalideerd en dubbele
  adressen worden afgewezen met een begrijpelijke fout.
- Bevoegde gebruikers kunnen leden zoeken en filteren op naam, e-mail en status.
- Een lid inactief maken bewaart het lid en alle gekoppelde donaties.
- Ledenformulieren zijn bruikbaar met toetsenbord en touch en tonen
  veldspecifieke validatiefouten.

## US02 - Donaties registreren

Als penningmeester wil ik een donatie aan een lid koppelen met categorie,
subcategorie, bedrag en datum/tijd, zodat de financiële administratie klopt.

**Acceptatiecriteria**

- Een donatie heeft een uniek ID en verwijst naar een bestaand lid.
- Bedrag is groter dan nul; invoer wordt als geldbedrag (standaard EUR)
  opgeslagen en getoond.
- Categorie, subcategorie en datum/tijd zijn verplicht; categorieën zijn
  consistent en voorbeelden zijn Contributie en Sponsoring.
- Datum/tijd staat standaard op het huidige moment en kan worden aangepast.
- Een foutieve invoer slaat geen gedeeltelijke donatie op en geeft een
  begrijpelijke melding.
- Donaties van inactieve leden blijven in historische overzichten beschikbaar.
  Nieuwe donaties voor inactieve leden worden standaard geweigerd; instelbaar via
  `ALLOW_DONATIONS_FOR_INACTIVE_MEMBERS` totdat het bestuur hierover besluit.

## US03 - Ledenadministratie raadplegen op alle apparaten

Als gebruiker wil ik de belangrijkste formulieren en overzichten op mobiel,
tablet en laptop kunnen gebruiken, zodat ik de administratie op locatie en
kantoor kan bijwerken.

**Acceptatiecriteria**

- Layout en invoervelden passen zich aan het scherm aan en werken met touch en
  toetsenbord.
- Alle acties zijn met toetsenbord te bedienen en formulieren hebben duidelijke
  labels en foutmeldingen.
- De interface toont een bevestiging na opslaan en voorkomt onbedoeld dubbel
  versturen.

## US04 - Financiële rapportage per periode

Als bestuurder wil ik donaties over een gekozen periode bekijken, zodat ik
inkomsten en trends kan volgen.

**Acceptatiecriteria**

- Gebruiker kan begin- en einddatum kiezen; beide datums zijn inclusief.
- Een einddatum vóór de begindatum wordt afgewezen.
- Rapportage toont totaalbedrag en aantal donaties, met uitsplitsing per
  categorie en subcategorie.
- Tabel en grafiek gebruiken dezelfde filters en totalen.
- Een periode zonder donaties toont een duidelijke lege status, geen foutieve
  totalen of misleidende grafiek.

## US05 - Rapportage per lid

Als beheerder of penningmeester wil ik donaties van één lid binnen een gekozen
periode bekijken, zodat ik vragen over diens bijdragen kan beantwoorden.

**Acceptatiecriteria**

- Gebruiker kan een lid combineren met begin- en einddatum.
- Resultaten tonen datum/tijd, categorie, subcategorie en bedrag per donatie,
  plus een totaal voor de selectie.
- Alleen donaties van het gekozen lid binnen de inclusieve periode worden
  getoond; historische donaties van inactieve leden blijven zichtbaar.

## US06 - Grafieken filteren

Als bestuurder wil ik rapportagegrafieken filteren op periode, lid en
categorie, zodat ik relevante uitsplitsingen kan vergelijken.

**Acceptatiecriteria**

- Filters kunnen afzonderlijk en gecombineerd worden toegepast en gereset.
- De grafiek en samenvatting worden bijgewerkt op basis van exact dezelfde
  selectie.
- Grafiekreeksen, assen en bedragen zijn begrijpelijk gelabeld; lege selecties
  worden expliciet weergegeven.

## US07 - AI-inzicht opvragen

Als bestuurder wil ik voor de getoonde periode een korte trendanalyse kunnen
opvragen, zodat opvallende veranderingen sneller zichtbaar zijn.

**Acceptatiecriteria**

- Analyse wordt alleen op expliciet verzoek gestart en volgt de actieve
  rapportagefilters.
- De samenvatting noemt de geanalyseerde periode en is gebaseerd op de getoonde
  aggregaties; onvoldoende data wordt duidelijk gemeld.
- Rapportage blijft bruikbaar als AI niet is geconfigureerd of tijdelijk niet
  beschikbaar is.
- Direct identificerende persoonsgegevens worden niet naar een externe
  provider gestuurd; provider en foutstatus zijn transparant.

## US08 - Gegevens veilig beheren

Als beheerder wil ik dat alleen bevoegde gebruikers persoonsgegevens en
financiële gegevens kunnen inzien of wijzigen, zodat ledengegevens beschermd
zijn.

**Acceptatiecriteria**

- Productiegebruik vereist authenticatie; rechten worden server-side
  gecontroleerd.
- Geheimen staan niet in broncode of logs en productieverbindingen gebruiken
  TLS.
- Wijzigingen aan leden en financiële gegevens laten geen gedeeltelijk
  opgeslagen records achter.
- De definitieve rolverdeling, bewaartermijn en auditvereisten worden vóór
  productie vastgesteld.

## US09 - Boekhoudgegevens exporteren (na MVP)

Als penningmeester wil ik gecontroleerde financiële gegevens naar een
boekhoudpakket kunnen exporteren, zodat overtypen niet nodig is.

**Acceptatiecriteria**

- Een adapter kan gegevens omzetten naar het afgesproken formaat/API van het
  gekozen pakket zonder domeinlogica aan die leverancier te koppelen.
- Gebruiker ziet een preview en bevestigt verzending/boeking expliciet.
- Mislukte of herhaalde exports veroorzaken geen ongemerkte dubbele boekingen;
  fouten zijn zichtbaar en opnieuw proberen is veilig.
- Exact Online, Moneybird en het exportformaat zijn voorbeelden, geen gekozen
  MVP-integraties.

## US10 - Bankafschrift-PDF verwerken (na MVP)

Als penningmeester wil ik regels uit een PDF-bankafschrift laten herkennen en
voorgestelde donatiematches beoordelen, zodat invoer sneller gaat zonder
controle te verliezen.

**Acceptatiecriteria**

- PDF-tekstextractie is een afzonderlijke stap (bijvoorbeeld met pdfplumber).
- Herkende velden en onzekerheden worden vóór import getoond.
- AI mag matches voorstellen, maar boekt of koppelt nooit definitief zonder
  menselijke bevestiging.
- Herhaalde import van hetzelfde bestand maakt geen dubbele transacties.
