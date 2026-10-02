# Ashab al-Jannah <span lang="ar" dir="rtl">أَصْحَابُ الْجَنَّةِ</span>

**Ledenadministratie met AI.** Ashab al-Jannah is een eenvoudige, responsieve webapp voor
ledenadministratie en donatieregistratie van een vereniging. Beheerders, penningmeesters en bestuurders gebruiken de applicatie vanaf
mobiel, tablet of laptop. Registratie, rapportage en trendinzichten zitten in de MVP.
Boekhoudkoppelingen en het inlezen van bankafschriften volgen later via de bestaande
uitbreidingspunten.

| Document | Inhoud |
|---|---|
| [1-UserStories](./1-UserStories) | User stories en acceptatiecriteria (US01–US10) |
| [2-TestScenarios](./2-TestScenarios) | Gherkin-scenario's, 1-op-1 geautomatiseerd in [tests/functional](./tests/functional) |
| [.env.example](./.env.example) | Alle configuratie-instellingen |

## Over de naam

*Ashab al-Jannah* (أَصْحَابُ الْجَنَّةِ) betekent letterlijk "de metgezellen van de tuin" en
wordt in de Koran vooral gebruikt voor de bewoners van het Paradijs (bijv. 59:20). De
naam staat centraal in de code (`APP_NAME` in
[`__init__.py`](./src/ledenadmin/__init__.py)), zodat UI, API-titel en paginatitels
consistent blijven. De Python-package heet intern `ledenadmin`.

## Snel starten (lokaal)

Vereist: Python 3.12 of hoger.

```powershell
cd ashab-al-jannah
.\start.ps1 -Install        # venv + dependencies, migraties, server op http://127.0.0.1:8000
```

- Web-UI: <http://127.0.0.1:8000>
- API-documentatie (OpenAPI): <http://127.0.0.1:8000/api/docs>

`start.ps1` zet `AUTH_MODE=dev`: iedereen is dan automatisch aangemeld met alle rollen.
Gebruik dit alleen lokaal; met `APP_ENV=production` weigert de applicatie te starten.

## Techstack

| Laag | Keuze | Waarom |
|---|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2 | Licht, snel, automatische validatie en OpenAPI; Python past bij AI/data |
| UI | Jinja2 + HTMX + Chart.js + Pico CSS (gevendord) | Minimale, responsieve UI zonder build-stap of SPA; één deployment; strikte CSP |
| Data | SQLAlchemy 2 + Alembic | Typed ORM, migraties; SQLite lokaal, Azure SQL in productie |
| Rapportage | pandas | Aggregaties per categorie, subcategorie, maand en lid; CSV-export |
| AI | Provider-interface: lokaal (standaard), OpenAI/Azure OpenAI, Anthropic | Werkt zonder externe dienst; alleen geaggregeerde data naar buiten |
| Auth | Azure Container Apps-authenticatie (Easy Auth, Entra ID) + rollen in de app | Geen eigen wachtwoordbeheer; autorisatie server-side |
| Hosting | Azure Container Apps + Azure SQL Database (free offer) | Scale-to-zero, HTTPS; [gratis SQL-tegoed](https://learn.microsoft.com/en-us/azure/azure-sql/database/free-offer) |
| Tests | pytest (unit/API/web), Robot Framework (acceptatie, Gherkin-stijl) | Snelle feedback + gebruikersgerichte scenario's |
| CI/CD | GitHub Actions, ghcr.io, OIDC-login naar Azure | Zie [ci-cd.yml](./.github/workflows/ci-cd.yml) |

Bewust níet gekozen: **seaborn** (statische plaatjes passen niet bij interactieve
filters; Chart.js rendert in de browser) en **scikit-learn** (weinig meerwaarde bij de
datavolumes van een vereniging, zware dependency met trage cold starts). Beide kunnen
later worden toegevoegd, bijvoorbeeld voor PDF-rapporten of voorspellingen.

## Architectuur

```
src/ledenadmin/
├── main.py              Applicatiefabriek (create_app): wiring, middleware, routers
├── config.py            Settings (omgevingsvariabelen) + veiligheidscontroles
├── db.py                Database-klasse, UTC-datetimetype, naamconventies
├── container.py         ServiceContainer: stelt per request de services samen
├── domain/              ORM-modellen, enums (rollen/rechten), domeinfouten, geldfuncties
├── repositories/        Data-toegang per aggregaat (leden, categorieën, donaties)
├── schemas/             Pydantic-contracten voor in- en uitvoer
├── services/            Bedrijfslogica
│   ├── member_service.py, donation_service.py, category_service.py, report_service.py
│   ├── ai/              InsightProvider-protocol + lokaal/OpenAI/Anthropic + InsightService
│   └── exporters/       ReportExporter-protocol + CSV (later Moneybird/Exact Online)
├── auth/                Principal, rol→rechten, Easy Auth- en dev-provider
├── api/                 REST API /api/v1 (routers, dependencies, foutafhandeling)
└── web/                 Server-side UI (routes, templates, CSRF/CSP, statische bestanden)
migrations/              Alembic-migraties
tests/unit/              pytest: services, auth, API, web, migraties
tests/functional/        Robot Framework-suites per user story
```

Principes:

- **Lagen**: routes (API én web) valideren invoer en vertalen naar HTTP. Services bevatten
  de regels. Repositories doen de data-toegang. API en web delen dezelfde services.
- **Uitbreidbaar via interfaces**: `InsightProvider` voor AI, `ReportExporter` voor exports
  en `AuthProvider` voor identiteit. Een nieuwe leverancier is een nieuwe klasse; de
  domeinlogica verandert niet.
- **Geld** wordt opgeslagen als integer centen en getoond als `Decimal` (geen
  float-afrondingsfouten).
- **Tijd** wordt opgeslagen in UTC en getoond in `Europe/Amsterdam`. Een periodefilter
  "t/m 28-02" bevat alles tot en met 28-02 23:59 lokale tijd.
- **Tekst** is Unicode (`NVARCHAR` op SQL Server), zodat namen als "Ayşe Öztürk" correct
  blijven.

## Gebruikers en autorisatie

| Recht | Beheerder | Penningmeester | Bestuurder |
|---|:-:|:-:|:-:|
| Leden inzien | ✔ | ✔ | |
| Leden aanmaken/wijzigen | ✔ | | |
| Donaties inzien | ✔ | ✔ | |
| Donaties registreren, categorieën beheren | | ✔ | |
| Rapportage (totalen, grafieken) | ✔ | ✔ | ✔ |
| Rapportage per lid / met namen | ✔ | ✔ | |
| AI-analyse | | ✔ | ✔ |
| CSV-export | | ✔ | |

De rechten staan centraal in [principal.py](./src/ledenadmin/auth/principal.py) en worden
server-side afgedwongen. De UI toont alleen toegestane acties. Een bestuurder krijgt
rapporten zonder uitsplitsing per lid en zonder losse donaties. Deze verdeling is een
startpunt dat met het bestuur moet worden bevestigd.

## Functionele requirements

### Leden (US01)

- Een lid heeft een uniek ID, een naam, een uniek e-mailadres (case-insensitive, opgeslagen
  in kleine letters), een status (actief/inactief) en aanmaak-/wijzigingsgegevens.
- Zoeken op naam en e-mail, en filteren op status (live via HTMX).
- Inactief zetten verwijdert niets; de donatiehistorie blijft gekoppeld.

### Donaties (US02)

- Een donatie heeft een bestaand lid, een subcategorie (en daarmee een categorie), een
  bedrag > 0 met maximaal 2 decimalen, een datum/tijd (standaard nu) en een optionele
  omschrijving.
- Bedragen in Nederlandse notatie worden geaccepteerd ("€ 1.234,50").
- Datums in de toekomst worden geweigerd (5 minuten speling).
- Nieuwe donaties voor inactieve leden worden standaard geweigerd. Instelbaar met
  `ALLOW_DONATIONS_FOR_INACTIVE_MEMBERS`.
- Standaardcategorieën: Contributie (Jaarlijks, Maandelijks), Donatie (Algemeen, Project)
  en Sponsoring (MKB, Particulier). Uitbreiden kan via `POST /api/v1/categories`.

### Rapportage (US04–US06)

- Filters: begin- en einddatum (beide inclusief), lid, categorie en subcategorie.
  Standaard: dit kalenderjaar tot vandaag.
- Totaal, aantal en gemiddelde, met uitsplitsing per categorie, subcategorie, maand en lid.
  Tabellen en grafieken gebruiken exact dezelfde selectie.
- Een lege selectie toont "Geen gegevens voor deze periode", zonder grafiek.
- CSV-export (puntkomma, decimale komma, UTF-8 met BOM voor Excel). Waarden die met
  `=`, `+`, `-` of `@` beginnen worden geneutraliseerd tegen formule-injectie.

### AI-inzichten (US07)

- De gebruiker start een analyse expliciet. Die volgt de actieve rapportfilters.
- De provider ontvangt **alleen aggregaties** (totalen per categorie en maand), nooit namen,
  e-mailadressen of omschrijvingen. Dit is met tests geborgd.
- Zonder data wordt de provider niet aangeroepen. Als een externe dienst faalt, valt de
  app terug op de lokale analyse en meldt dat.
- `AI_PROVIDER=local` (standaard) gebruikt een deterministische, regelgebaseerde
  samenvatting. Voor `openai` (ook Azure OpenAI via `OPENAI_BASE_URL`) en `anthropic`
  zijn `AI_MODEL` en een API-sleutel verplicht.

## Niet-functionele requirements

- **Responsive en toegankelijk**: labels bij alle velden, `aria-invalid` en
  `aria-describedby` bij fouten, een skip-link, grotere aanraakdoelen op touchscreens en
  geen horizontaal scrollen op mobiel.
- **Beveiliging**: CSRF-token (double submit) op alle formulieren, Content Security Policy
  zonder inline scripts/styles, `X-Frame-Options`, secure cookies in productie, geheimen
  alleen via omgevingsvariabelen/Container Apps-secrets en geen persoonsgegevens in logs.
- **Betrouwbaarheid**: transacties per actie, databaseconstraints (uniek e-mailadres,
  bedrag > 0, foreign keys met `RESTRICT`) en migraties die met tests worden gecontroleerd.
- **Productieveiligheid**: de app start niet met `APP_ENV=production` in combinatie met
  `AUTH_MODE=dev` of SQLite (tenzij `ALLOW_SQLITE_IN_PRODUCTION=true`).

## Configuratie

Alle instellingen staan in [.env.example](./.env.example). De belangrijkste:

| Variabele | Standaard | Toelichting |
|---|---|---|
| `APP_ENV` | `development` | `production` activeert de veiligheidscontroles en secure cookies |
| `DATABASE_URL` | `sqlite:///./ledenadmin.db` | SQLAlchemy-URL; zie Azure SQL hieronder |
| `AUTH_MODE` | `easyauth` | `dev` alleen lokaal; rollen via `DEV_USER_ROLES` of de header `X-Dev-Roles` |
| `ROLE_CLAIM_TYPE` | `roles` | Claim met de Entra ID-app-rollen |
| `TIMEZONE` | `Europe/Amsterdam` | Weergave en periodegrenzen |
| `AI_PROVIDER` | `local` | `local`, `openai` of `anthropic` |

## Tests en kwaliteit

```powershell
.\kwaliteitscontrole.ps1          # black, isort, flake8, pytest + coverage (≥ 90%)
.\kwaliteitscontrole.ps1 -Fix     # formatteert eerst
.\functionele-tests.ps1           # Robot Framework tegen een verse database en server
.\functionele-tests.ps1 -Include US02
```

- **pytest** ([tests/unit](./tests/unit)) test services, randgevallen (tijdzones,
  afronding, privacy), autorisatie, API-contracten, web-formulieren met CSRF en
  migraties (upgrade/downgrade en schema gelijk aan de modellen).
- **Robot Framework** ([tests/functional](./tests/functional)): elke testnaam en
  Given/When/Then-stap komt overeen met een scenario in [2-TestScenarios](./2-TestScenarios).
  Tags koppelen aan user stories (`US01` … `US08`); `smoke` draait ook na een deploy.
- De UI is handmatig gecontroleerd op desktop en mobiel (390 px). Geautomatiseerde
  browsertests (robotframework-browser) zijn een mogelijke volgende stap.

## Deployment naar Azure

De workflow [ci-cd.yml](./.github/workflows/ci-cd.yml) voert bij
elke push of PR uit: kwaliteit en unit tests, pip-audit, Robot-tests,
een Docker-build met containerrooktest (inclusief de ODBC-driver). Op `main` wordt het
image daarna naar ghcr.io gepusht. Deployen gebeurt handmatig via *Run workflow*
met `deploy_azure`.

Voor de eerste deployment zijn deze eenmalige stappen nodig:

1. **Azure SQL Database** (free offer) aanmaken en alleen Entra ID-authenticatie gebruiken.
2. **GitHub OIDC**: maak een app-registratie met een federated credential voor
   environment `production` en geef die Contributor op de resource group. Zet
   `AZURE_CLIENT_ID`, `AZURE_TENANT_ID` en `AZURE_SUBSCRIPTION_ID` als secrets.
3. **Secrets**: `GHCR_PULL_TOKEN` (PAT met alleen `read:packages`) en `DATABASE_URL`:

   ```text
   mssql+pyodbc:///?odbc_connect=Driver%3D%7BODBC+Driver+18+for+SQL+Server%7D%3BServer%3Dtcp%3A<server>.database.windows.net%2C1433%3BDatabase%3D<db>%3BEncrypt%3Dyes%3BAuthentication%3DActiveDirectoryMsi%3BConnection+Timeout%3D60
   ```

4. **Database-toegang voor de managed identity** (na de eerste deploy, als Entra-admin):

   ```sql
   CREATE USER [ashab-al-jannah] FROM EXTERNAL PROVIDER;
   ALTER ROLE db_datareader ADD MEMBER [ashab-al-jannah];
   ALTER ROLE db_datawriter ADD MEMBER [ashab-al-jannah];
   ALTER ROLE db_ddladmin ADD MEMBER [ashab-al-jannah];  -- voor migraties bij het opstarten
   ```

5. **Aanmelden (Easy Auth)**: koppel een Entra ID-app-registratie met app-rollen
   `beheerder`, `penningmeester` en `bestuurder`. Wijs gebruikers rollen toe. Vereis
   aanmelding en sluit alleen de health-check uit:

   ```bash
   az containerapp auth microsoft update -n ashab-al-jannah -g rg-ashab-al-jannah \
     --client-id <app-id> --client-secret <secret> --issuer https://login.microsoftonline.com/<tenant>/v2.0
   az containerapp auth update -n ashab-al-jannah -g rg-ashab-al-jannah \
     --unauthenticated-client-action RedirectToLoginPage --excluded-paths /api/v1/health
   ```

Aandachtspunten: door scale-to-zero en het automatisch pauzeren van Azure SQL kan de
eerste request na rust tot ongeveer een minuut duren. Migraties draaien bij het opstarten
(`RUN_MIGRATIONS=true`). Gebruik daarom maximaal twee replica's of draai migraties als
aparte stap. Controleer vóór ingebruikname de actuele limieten, kosten en regio van de
gratis tegoeden.

## Uitbreidingen na de MVP

- **Boekhouding (US09)**: implementeer `ReportExporter` voor Moneybird of Exact Online,
  met een preview en expliciete bevestiging. Herhaalde exports mogen geen dubbele
  boekingen veroorzaken.
- **Bankafschriften (US10)**: begin bij voorkeur met CAMT.053- of CSV-exports van de bank
  (betrouwbaarder dan PDF); pdfplumber kan als fallback. AI mag matches voorstellen,
  maar definitief koppelen gebeurt altijd na menselijke bevestiging.
- Donaties corrigeren of crediteren met een audittrail, beheer van categorieën in de UI
  en geautomatiseerde browsertests.

## Open besluiten

1. Definitieve rolverdeling en of donaties voor inactieve leden zijn toegestaan.
2. Bewaartermijnen, back-up/herstel (Azure SQL PITR) en AVG-procedures.
3. Keuze en kostenlimiet voor een externe AI-provider, en of verwerking in de EU vereist is.
4. Boekhoudpakket en bankformaat voor de integraties.
