# Ashab al-Jannah <span lang="ar" dir="rtl">أَصْحَابُ الْجَنَّةِ</span>

**Ledenadministratie met AI.** Ashab al-Jannah is een eenvoudige, responsieve webapp voor
ledenadministratie en donatieregistratie van een vereniging. Beheerders, penningmeesters en bestuurders gebruiken de applicatie vanaf
mobiel, tablet of laptop. Registratie, rapportage en trendinzichten zitten in de MVP.
Boekhoudkoppelingen en het inlezen van bankafschriften volgen later via de bestaande
uitbreidingspunten.

| Document | Inhoud |
|---|---|
| [1-UserStories](./1-UserStories.md) | User stories en acceptatiecriteria (US01–US10) |
| [2-TestScenarios](./2-TestScenarios) | Gherkin-scenario's, 1-op-1 geautomatiseerd in [tests/functional](./tests/functional) |
| [.env.example](./.env.example) | Alle configuratie-instellingen |

## Over de naam

*Ashab al-Jannah* (أَصْحَابُ الْجَنَّةِ) betekent letterlijk "de metgezellen van de tuin" en
wordt in de Koran vooral gebruikt voor de bewoners van het Paradijs (bijv. 59:20). De
naam staat centraal in de code (`APP_NAME` in
[`__init__.py`](./src/ledenadmin/__init__.py)), zodat UI, API-titel en paginatitels
consistent blijven. De Python-package heet intern `ledenadmin`.

## Snel starten (lokaal)

Er zijn twee manieren: direct met Python via `start.ps1` (handig om te ontwikkelen) of
met de container-image via Docker (zonder Python op je machine).

### Optie A – Met Python en `start.ps1`

1. **Installeer de benodigdheden**
   - [Git](https://git-scm.com/downloads), bijv. `winget install Git.Git`.
   - [Python 3.12 of hoger](https://www.python.org/downloads/), bijv.
     `winget install Python.Python.3.12`. Vink bij de installer *Add python.exe to PATH* aan.
   - Op Linux/macOS: `git` en `python3` (met `venv`) via de pakketbeheerder. `start.ps1` is
     Windows-only; gebruik daar de commando's onder stap 3.
2. **Clone de repository**

   ```powershell
   git clone https://github.com/muratbalasar/ashab-al-jannah.git
   cd ashab-al-jannah
   ```

3. **Start de app** (de eerste keer duurt het installeren even):

   ```powershell
   .\start.ps1 -Install -InitWithDummyData   # venv + dependencies, migraties, demodata, server
   ```

   Weigert Windows het script, sta dan lokale scripts toe voor deze sessie:
   `Set-ExecutionPolicy -Scope Process RemoteSigned`.

   Linux/macOS (zelfde stappen als `start.ps1`):

   ```sh
   python3 -m venv .venv && . .venv/bin/activate
   pip install -r requirements-dev.txt && pip install -e . --no-deps
   export AUTH_MODE=dev DATABASE_URL=sqlite:///./ledenadmin.db
   alembic upgrade head
   python -m ledenadmin.dummy_data            # optioneel: demodata
   uvicorn --factory ledenadmin.main:create_app --reload --port 8000
   ```
4. **Open** <http://127.0.0.1:8000> (API-documentatie: <http://127.0.0.1:8000/api/docs>).
   Stoppen doe je met `Ctrl+C`. Daarna is `.\start.ps1` genoeg om opnieuw te starten.

`start.ps1` zet `AUTH_MODE=dev`: iedereen is dan automatisch aangemeld met alle rollen.
Met `.\start.ps1 -InitWithDummyData` worden 120 dummy leden (e-mail `*.dummy@voorbeeld.nl`)
met donaties verspreid over de afgelopen 18 maanden en alle subcategorieën toegevoegd. Bestaande
dummy leden worden overgeslagen, dus de optie kan veilig vaker worden gebruikt.
De lokale database (`ledenadmin.db`) blijft bewaard bij stoppen en herstarten. Met
`.\start.ps1 -ResetDatabase` begin je met een lege database (alleen voor SQLite). Combineer
met `-InitWithDummyData` voor een schone demo-omgeving.
Gebruik dit alleen lokaal; met `APP_ENV=production` weigert de applicatie te starten.

### Optie B – Container-image met Docker (Windows en Linux)

Installeer eerst Docker: op Windows [Docker Desktop](https://www.docker.com/products/docker-desktop/)
(met WSL 2), op Linux [Docker Engine](https://docs.docker.com/engine/install/).

#### B1 – Kant-en-klare image van GitHub (zonder clonen)

Elke push op `main` waarvan de tests slagen, publiceert de image als
[package op GitHub](https://github.com/muratbalasar/ashab-al-jannah/pkgs/container/ashab-al-jannah)
(`ghcr.io/muratbalasar/ashab-al-jannah:latest`). Docker haalt hem bij de eerste start
automatisch op; bijwerken naar de nieuwste versie doe je met
`docker pull ghcr.io/muratbalasar/ashab-al-jannah:latest`.

Linux (bash):

```sh
docker run --rm -p 8000:8000 \
  -e APP_ENV=development -e AUTH_MODE=dev \
  -e DATABASE_URL=sqlite:////home/app/ledenadmin.db \
  -v ashab-data:/home/app \
  --name ashab ghcr.io/muratbalasar/ashab-al-jannah:latest
```

Windows (PowerShell):

```powershell
docker run --rm -p 8000:8000 `
  -e APP_ENV=development -e AUTH_MODE=dev `
  -e DATABASE_URL=sqlite:////home/app/ledenadmin.db `
  -v ashab-data:/home/app `
  --name ashab ghcr.io/muratbalasar/ashab-al-jannah:latest
```

Open daarna <http://127.0.0.1:8000>. De instellingen worden hieronder bij B2, stap 3, uitgelegd.

#### B2 – Zelf bouwen vanuit de broncode

1. Clone de repository zoals bij optie A, stap 2.
2. **Bouw de image** (in de map `ashab-al-jannah`). De ODBC-driver voor Azure SQL is lokaal
   niet nodig en kan worden overgeslagen:

   ```sh
   docker build -t ashab-al-jannah --build-arg INSTALL_MSSQL_DRIVER=false .
   ```

3. **Start de container**. De image staat standaard op productie (echte aanmelding, geen
   SQLite). Voor lokaal gebruik zet je ontwikkelmodus aan en bewaar je de SQLite-database
   in een Docker-volume, zodat de gegevens een herstart overleven.

   Linux (bash):

   ```sh
   docker run --rm -p 8000:8000 \
     -e APP_ENV=development -e AUTH_MODE=dev \
     -e DATABASE_URL=sqlite:////home/app/ledenadmin.db \
     -v ashab-data:/home/app \
     --name ashab ashab-al-jannah
   ```

   Windows (PowerShell):

   ```powershell
   docker run --rm -p 8000:8000 `
     -e APP_ENV=development -e AUTH_MODE=dev `
     -e DATABASE_URL=sqlite:////home/app/ledenadmin.db `
     -v ashab-data:/home/app `
     --name ashab ashab-al-jannah
   ```

4. **Open** <http://127.0.0.1:8000>. Wil je demodata, voer dan in een tweede terminal uit:
   `docker exec ashab python -m ledenadmin.dummy_data`.
   Stoppen doe je met `Ctrl+C` of `docker stop ashab`. Een lege database krijg je met
   `docker volume rm ashab-data`.

#### Waar staan de gegevens?

De SQLite-database (`/home/app/ledenadmin.db`) staat niet in de container zelf, maar in het
Docker-volume `ashab-data` (`-v ashab-data:/home/app`). Docker beheert dat volume buiten de
container.

- **Stoppen en opnieuw starten:** `--rm` verwijdert de container bij het stoppen, maar het
  volume blijft bestaan. Start je opnieuw met hetzelfde commando, dan zijn alle leden en
  donaties er nog.
- **Nieuwe image (`docker pull`):** de gegevens blijven behouden. Bij het opstarten werkt
  de app het databaseschema automatisch bij (`RUN_MIGRATIONS=true`).
- **Gegevens kwijt:** als je `-v ashab-data:/home/app` weglaat (de database staat dan in de
  container en verdwijnt bij het stoppen), of na `docker volume rm ashab-data`.
- **Back-up maken** (Linux; gebruik in PowerShell `${PWD}`):

  ```sh
  docker run --rm -v ashab-data:/data -v "$PWD":/backup alpine cp /data/ledenadmin.db /backup/
  ```

Gebruik `AUTH_MODE=dev` nooit op een publiek bereikbare server: iedereen heeft dan alle
rechten. Zie [Configuratie](#configuratie) en [Deployment naar Azure](#deployment-naar-azure)
voor productie.

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
| Donaties registreren | ✔ | ✔ | |
| Donaties verwijderen | ✔ | | |
| Leden verwijderen (inclusief hun donaties) | ✔ | | |
| Categorieën en subcategorieën beheren | ✔ | | |
| Rapportage (totalen, grafieken) | ✔ | ✔ | ✔ |
| Rapportage per lid / met namen | ✔ | ✔ | |
| AI-analyse | ✔ | ✔ | ✔ |
| CSV-export | ✔ | ✔ | |
| Logboek inzien | ✔ | | |

De beheerder heeft alle rechten, ook rechten die later worden toegevoegd. De rechten staan
centraal in [principal.py](./src/ledenadmin/auth/principal.py) en worden
server-side afgedwongen. De UI toont alleen toegestane acties. Een bestuurder krijgt
rapporten zonder uitsplitsing per lid en zonder losse donaties. Deze verdeling is een
startpunt dat met het bestuur moet worden bevestigd.

### Ledenvelden

De beheerder kan op `/ledenvelden` zelf extra velden voor leden toevoegen. De types zijn
Tekst, Nummer, Mobiel nummer, IBAN en Ja/nee (bijv. Nieuwsbrief). De velden verschijnen
automatisch op het formulier voor een nieuw lid en op de detailpagina van een lid.
De waarden worden per type gecontroleerd en genormaliseerd:
- Mobiel nummer: 06-nummer of internationaal nummer.
- IBAN: met controle van het controlegetal; wordt opgeslagen in blokken van vier.
- Nummer: alleen cijfers.

Een veld deactiveren verbergt het, maar de waarden blijven bewaard. Verwijderen wist het
veld én alle ingevulde waarden. **Gevoelige gegevens worden geblokkeerd (AVG):**
- Veldnamen die duiden op BSN/sofinummer, ID-bewijs, wachtwoord/pincode, gezondheid,
  geloof, afkomst, seksuele geaardheid, politiek, vakbond, strafrecht of biometrie
  worden geweigerd.
- Waarden die de BSN-elfproef halen, worden in tekst- en nummervelden geweigerd.

### Logboek

Elke actie wordt vastgelegd in de tabel `audit_log` en via de logger `ledenadmin.audit`:
aanmeldingen (eerste verzoek per browsersessie), weergaven (GET), kliks (via
`/logboek/klik`), wijzigingen (POST/PUT/PATCH) en verwijderingen. Per regel worden het
tijdstip, de gebruiker, het verzoek, de status, het IP-adres en de details opgeslagen.
De details zijn de formulierdata of de zoekparameters, zonder CSRF-token. De beheerder
bekijkt het logboek op `/logboek` en kan filteren op gebruiker en actie.
Let op (AVG): de details kunnen persoonsgegevens bevatten, zoals namen en e-mailadressen.
Regels ouder dan 41 dagen (`RETENTION` in `audit.py`) worden automatisch verwijderd. Er is
geen aparte scheduler: na het opslaan van een nieuwe logregel ruimt de app op, hooguit één
keer per uur per instantie. Zonder verkeer wordt er dus niet opgeruimd, en na een herstart
gebeurt dat bij de eerstvolgende logregel.

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
  en Sponsoring (MKB, Particulier).

### Categorieën beheren

- Alleen de beheerder beheert categorieën en subcategorieën via de pagina **Categorieën**
  (`/categorieen`) of de API (`POST`/`PATCH /api/v1/categories`, en
  `/api/v1/categories/{id}/subcategories[/{sub_id}]`).
- Aanmaken, hernoemen en (de)activeren. Namen zijn uniek (subcategorieën binnen hun
  categorie), maximaal 100 tekens.
- Verwijderen kan alleen zolang er geen donaties op geboekt zijn (knop **Verwijderen**, met
  bevestiging; API `DELETE`). Een categorie wordt dan met haar subcategorieën verwijderd.
  Is een (sub)categorie al gebruikt, dan blijft alleen deactiveren over; bestaande donaties
  blijven zo aan hun (sub)categorie gekoppeld.
  Een inactieve categorie of subcategorie blijft zichtbaar in rapportages, maar is niet
  te kiezen bij nieuwe donaties. Een hernoeming geldt ook voor bestaande donaties.

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
| `ROLE_CLAIM_TYPE` | `roles` | Claim met de Entra ID-app-rollen (alleen voor de standaardorganisatie) |
| `SUPERADMIN_SUBJECTS` | leeg | Platformbeheerders als `issuer\|subject`, komma-gescheiden; geeft toegang tot `/platform` |
| `EASYAUTH_LOGIN_URL` | `/.auth/login/aad` | Inlogpagina van Easy Auth; inrichting van Entra External ID: zie [4-EntraExternalID.md](4-EntraExternalID.md) |
| `SUPERADMIN_EMAIL` | leeg | Ontvangt een mail bij elke nieuwe organisatie |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | Basis-URL voor uitnodigingslinks |
| `KVK_API_KEY` | leeg | Optioneel: KVK-nummer opzoeken in het Handelsregister bij aanmelden |
| `MAX_ORGANIZATIONS_PER_USER` | `3` | Maximaal aantal organisaties dat één gebruiker aanmaakt (en 1 per 24 uur) |
| `BREVO_API_KEY` | leeg | Optioneel: uitnodigingen mailen via Brevo; zonder sleutel alleen een kopieerbare link |
| `MAIL_SENDER_EMAIL` / `MAIL_SENDER_NAME` | `noreply@example.nl` / `Ashab al-Jannah` | Afzender van e-mails |
| `MAIL_DAILY_LIMIT` | `300` | E-mails per dag (gratis Brevo-limiet); waarschuwing vanaf 80% |
| `TIMEZONE` | `Europe/Amsterdam` | Weergave en periodegrenzen |
| `AI_PROVIDER` | `local` | `local`, `openai` of `anthropic` |
| `AI_MODEL` / `AI_TIMEOUT_SECONDS` | leeg / `20` | Model en time-out voor `openai`/`anthropic` |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `ANTHROPIC_API_KEY` | leeg | Sleutels/endpoint van de AI-provider |
| `KVK_API_URL` | `https://api.kvk.nl/api/v2/zoeken` | Endpoint van de KVK Zoeken-API |
| `SECRET_ENCRYPTION_KEY` | leeg | Fernet-sleutel voor de Mollie-sleutels van stichtingen; leeg = online doneren uit (zie *Online doneren*) |
| `MOLLIE_API_URL` | `https://api.mollie.com/v2` | Mollie-API |
| `ALLOW_DONATIONS_FOR_INACTIVE_MEMBERS` | `false` | Donaties toestaan voor inactieve leden |
| `SEED_DEFAULT_CATEGORIES` | `true` | Standaardcategorieën aanmaken bij een nieuwe organisatie |
| `ALLOW_SQLITE_IN_PRODUCTION` | `false` | SQLite toestaan bij `APP_ENV=production` |
| `DEV_USER_NAME` / `DEV_USER_ROLES` | `ontwikkelaar` / leeg | Alleen bij `AUTH_MODE=dev` |

### Checklist productie (alle fases)

1. **Fase 1–2** – `APP_ENV=production`, `DATABASE_URL` (Azure SQL/PostgreSQL), `AUTH_MODE=easyauth`.
2. **Fase 3** – `SUPERADMIN_SUBJECTS`, `SUPERADMIN_EMAIL`, `PUBLIC_BASE_URL` (publiek https-adres);
   optioneel `KVK_API_KEY`, `BREVO_API_KEY` + `MAIL_SENDER_EMAIL` (geverifieerd afzenderdomein in Brevo).
3. **Fase 4** – Entra External ID met Google/Microsoft/Apple/Facebook en Easy Auth: zie
   [4-EntraExternalID.md](4-EntraExternalID.md); `EASYAUTH_LOGIN_URL`.
4. **Fase 5–6** – geen extra instellingen (rol *lid*, export/verwijderen werken direct).
5. **Fase 7** – `SECRET_ENCRYPTION_KEY` genereren en veilig bewaren; elke stichting koppelt zelf
   Mollie in *Instellingen*.

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
een Docker-build met containerrooktest (inclusief de ODBC-driver) en security-tests:

| Soort | Tool | Wat |
|---|---|---|
| SCA | pip-audit, Trivy | Kwetsbare Python-packages; kwetsbaarheden in de container-image (HIGH/CRITICAL) |
| SAST | Bandit, CodeQL | Onveilige code in Python en JavaScript (resultaten onder *Security → Code scanning*) |
| Secrets | Gitleaks | Geheimen in code en git-historie |
| DAST | OWASP ZAP baseline | Passieve scan van de draaiende container; rapport als artifact (nog niet blokkerend) |

Op `main` wordt het image pas naar ghcr.io gepusht als alle tests en scans slagen.
Deployen gebeurt handmatig via *Run workflow* met `deploy_azure`.

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
- Donaties corrigeren of crediteren met een audittrail en geautomatiseerde browsertests.

## Open besluiten

1. Definitieve rolverdeling en of donaties voor inactieve leden zijn toegestaan.
2. Bewaartermijnen, back-up/herstel (Azure SQL PITR) en AVG-procedures.
3. Keuze en kostenlimiet voor een externe AI-provider, en of verwerking in de EU vereist is.
4. Boekhoudpakket en bankformaat voor de integraties.

## Licentie

Ashab al-Jannah valt onder de [PolyForm Noncommercial License 1.0.0](./LICENSE.md).
Kort samengevat (de Engelse licentietekst is bindend):

- **Gratis** voor goede doelen en andere organisaties zonder winstoogmerk, zoals een
  vakıf, dernek, stichting, vereniging, moskee, hafızlık-, Koran- of imam-hatipschool. Dat
  geldt ook als de organisatie inkomsten heeft uit donaties, contributie of kleine
  vergoedingen voor activiteiten (bijv. sadaka, zakat, waterputten, iftar, onderwijs).
- **Gratis** voor persoonlijk gebruik, studie, onderzoek en hobbyprojecten.
- Aanpassen en delen mag, mits de licentie en de copyrightregel (`Required Notice`)
  meegaan.
- **Niet toegestaan:** commercieel gebruik, zoals de software verkopen, als betaalde dienst
  (SaaS) aanbieden of inzetten in een bedrijf met winstoogmerk. Neem voor commercieel
  gebruik contact op via GitHub.

## Online doneren (Mollie)

Elke stichting koppelt haar eigen Mollie-account via **Instellingen → Online doneren**: Live API-sleutel (`live_...`) plakken. Het geld gaat rechtstreeks naar de stichting; het platform raakt geen geld aan.

| Variabele | Betekenis |
|---|---|
| `SECRET_ENCRYPTION_KEY` | Fernet-sleutel waarmee API-sleutels versleuteld worden opgeslagen. Leeg = online doneren uit. |
| `MOLLIE_API_URL` | Standaard `https://api.mollie.com/v2`. |
| `PUBLIC_BASE_URL` | Moet publiek bereikbaar zijn (https) zodat Mollie de webhook `/betalingen/webhook/{slug}` kan aanroepen. Bij `localhost` wordt de status pas bijgewerkt als het lid terugkeert. |

Leden (rol *lid*, gekoppeld aan een lidrecord) zien op *Mijn omgeving* een doneerformulier. Na betaling (`paid`) wordt automatisch een donatie geboekt.
