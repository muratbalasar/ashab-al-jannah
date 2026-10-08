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

#### Lokaal en multi-tenant

Lokaal hoeft u niets aan organisaties in te richten. Bij het starten wordt automatisch de
organisatie **`standaard`** aangemaakt; `http://localhost:8000/` en oude URL's zoals `/leden`
sturen door naar `/o/standaard/...`. De dev-gebruiker krijgt daar de rollen uit
`DEV_USER_ROLES` (standaard alle). Zonder `SECRET_ENCRYPTION_KEY`, `BREVO_API_KEY` en
`KVK_API_KEY` staan online doneren, mailen en de KVK-check uit; de rest werkt gewoon.

Meerdere organisaties of rollen lokaal testen:

- Nieuwe organisatie: ga naar `/aanmelden` (KVK-nummer alleen op formaat gecontroleerd).
- Andere gebruiker: klik op de **DEV**-badge rechtsboven (of ga naar `/dev/gebruiker`) en vul
  een naam of e-mailadres in. Zo accepteert u lokaal een uitnodiging: meld u aan met het
  e-mailadres waarvoor de uitnodiging is gemaakt (de uitnodigingspagina linkt er ook naar).
  Een gewisselde gebruiker krijgt geen rollen uit `DEV_USER_ROLES`, alleen die uit
  uitnodigingen; met **Terug naar …** wordt u weer de standaardgebruiker. De keuze geldt per
  browser (cookie); gebruik een privévenster om twee gebruikers naast elkaar te testen.
- Rollen via headers: stuur `X-Dev-User` en `X-Dev-Roles` mee (bijv. met een browserextensie),
  of zet `DEV_USER_NAME`/`DEV_USER_ROLES` en herstart. Uitnodigingslinks verschijnen op het
  scherm om te kopiëren.
- Superadmin (`/platform`): `SUPERADMIN_SUBJECTS=dev|ontwikkelaar` (zie hieronder).
- Mollie testen: zet `SECRET_ENCRYPTION_KEY` en koppel een `test_`-sleutel; zonder publieke
  URL wordt de status bijgewerkt als u terugkeert van de betaalpagina.

#### Platformbeheer en meerdere organisaties lokaal testen

1. **Start als superadmin** (stop eerst een draaiende server met `Ctrl+C`):

   ```powershell
   $env:SUPERADMIN_SUBJECTS = "dev|ontwikkelaar"   # meer: "dev|ontwikkelaar,dev|beheerder-a"
   .\start.ps1                                      # of: .\start.ps1 -ResetDatabase
   ```

   In het menu staat dan **Platform** (`/platform`).
2. **Maak organisaties aan met verschillende gebruikers.** Eén gebruiker mag één organisatie
   per 24 uur aanmaken (maximaal `MAX_ORGANIZATIONS_PER_USER`, standaard 3). Wissel daarom
   per organisatie van gebruiker via de **DEV**-badge (`/dev/gebruiker`), bijv. `beheerder-a`,
   `beheerder-b`, en meld een organisatie aan op `/aanmelden` met een eigen KVK-nummer van
   8 cijfers (`11111111`, `22222222`, …). Voeg eventueel leden en donaties toe. Met
   **Terug naar ontwikkelaar** bent u weer superadmin.
3. **Test op `/platform`:**

   | Functie | Hoe |
   |---|---|
   | Overzicht | KVK, plaats, gebruikers, leden, laatste activiteit, status; totalen en fouten (24 uur) |
   | Blokkeren / deblokkeren | Blokkeer, wissel naar de beheerder: `/o/<slug>/` geeft 404 |
   | Verwijderen en herstellen | Als beheerder: **Instellingen** → **Organisatie verwijderen** (typ de slug). Op `/platform` staat ze als verwijderd met de wisdatum; **Herstellen** of **Nu wissen** |
   | Privacy | Als superadmin zonder rol geeft `/o/<slug>/leden` een 404 |
   | Scheiding | Nodig `beheerder-a` uit in organisatie B: op `/` ziet hij beide, de gegevens blijven gescheiden |

   Gebruik een privévenster voor een tweede gebruiker naast het superadmin-venster. Dezelfde
   uitleg staat lokaal in de app onder **Help** → *Lokaal testen (ontwikkelmodus)*.

#### Demo met Playwright

`.\demo.ps1` geeft een geautomatiseerde rondleiding in de browser (Edge), met een ondertitel
per stap: een nieuwe stichting aanmelden, drie leden met donaties registreren, een donatie via
het zoekveld invoeren, de rapportage bekijken, een penningmeester uitnodigen die in een tweede
venster de uitnodiging accepteert en zelf een donatie invoert. De demo draait op poort 8770
met een eigen, verse database (`output\demo\demo.db`); `ledenadmin.db` en `.env` blijven
ongemoeid. Playwright wordt zo nodig geïnstalleerd (`requirements-demo.txt`).

```powershell
.\demo.ps1                    # 1,5 seconde tussen de acties
.\demo.ps1 -Pauze 3 -Platform # langzamer, en aan het eind /platform als superadmin
.\demo.ps1 -Browser chromium  # zonder Edge: installeert de Chromium van Playwright
```

### Optie B – Container-image met Docker (Windows en Linux)

#### Docker installeren

**Windows 10/11**

1. Zet WSL 2 aan (PowerShell als administrator), en herstart daarna de pc:

   ```powershell
   wsl --install
   ```

2. Installeer Docker Desktop:

   ```powershell
   winget install -e --id Docker.DockerDesktop
   ```

   Of download het via [docker.com](https://www.docker.com/products/docker-desktop/).
3. Start **Docker Desktop** en wacht tot onderin "Engine running" staat.
4. Controleer: `docker run --rm hello-world`.

**Linux (Ubuntu/Debian)**

```sh
curl -fsSL https://get.docker.com | sudo sh   # officieel installatiescript
sudo usermod -aG docker $USER                 # docker zonder sudo gebruiken
newgrp docker                                  # of opnieuw inloggen
docker run --rm hello-world                    # controle
```

Andere distributies: zie [Docker Engine installeren](https://docs.docker.com/engine/install/).

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
  -v ashab-data:/data \
  --name ashab ghcr.io/muratbalasar/ashab-al-jannah:latest
```

Windows (PowerShell):

```powershell
docker run --rm -p 8000:8000 `
  -e APP_ENV=development -e AUTH_MODE=dev `
  -v ashab-data:/data `
  --name ashab ghcr.io/muratbalasar/ashab-al-jannah:latest
```

Open daarna <http://127.0.0.1:8000>. De instellingen worden hieronder bij B2, stap 3, uitgelegd.

#### B2 – Zelf bouwen vanuit de broncode

1. Clone de repository zoals bij optie A, stap 2.
2. **Bouw de image** (in de map `ashab-al-jannah`):

   ```sh
   docker build -t ashab-al-jannah .
   ```

3. **Start de container**. De image staat standaard op productie (echte aanmelding, en
   SQLite alleen met een back-up via Litestream). Voor lokaal gebruik zet je ontwikkelmodus
   aan en bewaar je de SQLite-database (`/data/ledenadmin.db`) in een Docker-volume, zodat
   de gegevens een herstart overleven.

   Linux (bash):

   ```sh
   docker run --rm -p 8000:8000 \
     -e APP_ENV=development -e AUTH_MODE=dev \
     -v ashab-data:/data \
     --name ashab ashab-al-jannah
   ```

   Windows (PowerShell):

   ```powershell
   docker run --rm -p 8000:8000 `
     -e APP_ENV=development -e AUTH_MODE=dev `
     -v ashab-data:/data `
     --name ashab ashab-al-jannah
   ```

4. **Open** <http://127.0.0.1:8000>. Wil je demodata, voer dan in een tweede terminal uit:
   `docker exec ashab python -m ledenadmin.dummy_data`.
   Stoppen doe je met `Ctrl+C` of `docker stop ashab`. Een lege database krijg je met
   `docker volume rm ashab-data`.

#### Waar staan de gegevens?

De SQLite-database (`/data/ledenadmin.db`) staat niet in de container zelf, maar in het
Docker-volume `ashab-data` (`-v ashab-data:/data`). Docker beheert dat volume buiten de
container.

- **Stoppen en opnieuw starten:** `--rm` verwijdert de container bij het stoppen, maar het
  volume blijft bestaan. Start je opnieuw met hetzelfde commando, dan zijn alle leden en
  donaties er nog.
- **Nieuwe image (`docker pull`):** de gegevens blijven behouden. Bij het opstarten werkt
  de app het databaseschema automatisch bij (`RUN_MIGRATIONS=true`).
- **Gegevens kwijt:** als je `-v ashab-data:/data` weglaat (de database staat dan in de
  container en verdwijnt bij het stoppen), of na `docker volume rm ashab-data`.
- **Eerdere versie met `-v ashab-data:/home/app`?** Dat blijft werken als je ook
  `-e DATABASE_URL=sqlite:////home/app/ledenadmin.db` meegeeft, zoals voorheen.
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
| Data | SQLAlchemy 2 + Alembic, SQLite | Typed ORM, migraties; lokaal en in productie hetzelfde SQLite-bestand |
| Back-up | [Litestream](https://litestream.io) naar Azure Blob Storage | Continue back-up (± 1 s), terugzetten bij het opstarten; een paar cent per maand |
| Rapportage | pandas | Aggregaties per categorie, subcategorie, maand en lid; CSV-export |
| AI | Provider-interface: lokaal (standaard), OpenAI/Azure OpenAI, Anthropic | Werkt zonder externe dienst; alleen geaggregeerde data naar buiten |
| Auth | Azure Container Apps-authenticatie (Easy Auth, Entra ID) + rollen in de app | Geen eigen wachtwoordbeheer; autorisatie server-side |
| Hosting | Azure Container Apps (één container, scale-to-zero) | HTTPS, gratis maandtegoed; zie [3-MultiTenantOntwerp.md](./3-MultiTenantOntwerp.md) § 11.1 |
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
├── db.py                Database-klasse, UTC-datetimetype, naamconventies, SQLite-instellingen (WAL)
├── copy_database.py     Alle gegevens overzetten naar een andere database (bijv. Azure SQL → SQLite)
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

| Recht | Beheerder | Penningmeester | Bestuurder | Lid |
|---|:-:|:-:|:-:|:-:|
| Leden inzien | ✔ | ✔ | | |
| Leden aanmaken/wijzigen | ✔ | | | |
| Donaties inzien | ✔ | ✔ | | |
| Donaties registreren | ✔ | ✔ | | |
| Donaties bewerken (met wijzigingsgeschiedenis) | ✔ | | | |
| Donaties verwijderen | ✔ | | | |
| Leden verwijderen (inclusief hun donaties) | ✔ | | | |
| Categorieën en subcategorieën beheren | ✔ | | | |
| Rapportage (totalen, grafieken) | ✔ | ✔ | ✔ | |
| Rapportage per lid / met namen | ✔ | ✔ | | |
| Eigen gegevens, jaaroverzicht en donaties | | | | ✔ |
| AI-analyse | ✔ | ✔ | ✔ | |
| CSV-export | ✔ | ✔ | | |
| Logboek inzien | ✔ | | | |

De beheerder heeft alle rechten, ook rechten die later worden toegevoegd. De rechten staan
centraal in [principal.py](./src/ledenadmin/auth/principal.py) en worden
server-side afgedwongen. De UI toont alleen toegestane acties. Een bestuurder krijgt
rapporten zonder uitsplitsing per lid en zonder losse donaties. Een lid ziet alleen het eigen
gekoppelde ledenrecord en jaaroverzicht op *Mijn omgeving*; het lid kan geen organisatiebrede
rapportages of gegevens van andere leden inzien. Deze verdeling is een startpunt dat met het
bestuur moet worden bevestigd.

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
- **Bewerken (alleen beheerder):** via het potlood in elke donatietabel (Donaties, ledenpagina,
  Rapportage) past de beheerder lid, categorie, bedrag, datum en omschrijving aan. Elk
  gewijzigd veld wordt met oude en nieuwe waarde, gebruiker en tijdstip vastgelegd in
  `donation_changes`; de geschiedenis staat op de bewerkpagina en zit in de AVG-export. Bij
  een online betaling (Mollie) liggen lid, bedrag en datum vast. Valt de donatie in een voorbij
    jaar, dan toont het formulier een waarschuwing en vraagt de app bij opslaan om bevestiging;
    raakt een wijziging een voorbij jaar (oude of nieuwe datum), dan noemt de melding dat jaar,
    omdat eerder verstuurde overzichten dan niet meer kloppen. Een lid of subcategorie die
    inmiddels inactief is, blijft staan zolang u die niet wijzigt.
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
  `AUTH_MODE=dev`, of met SQLite zonder back-up (`LITESTREAM_REPLICA_URL`, of bewust
  `ALLOW_SQLITE_IN_PRODUCTION=true`).

## Configuratie

Alle instellingen staan in [.env.example](./.env.example). De belangrijkste:

| Variabele | Standaard | Toelichting |
|---|---|---|
| `APP_ENV` | `development` | `production` activeert de veiligheidscontroles en secure cookies |
| `DATABASE_URL` | `sqlite:///./ledenadmin.db` (container: `sqlite:////data/ledenadmin.db`) | SQLAlchemy-URL; in de container altijd een absoluut pad op de lokale schijf |
| `LITESTREAM_REPLICA_URL` | leeg | Back-up via Litestream, bijv. `abs://<opslagaccount>@<container>/ledenadmin`; verplicht voor SQLite in productie (zie *Back-up en herstel*) |
| `LITESTREAM_RETENTION` | `168h` | Hoe ver terug de back-up gaat (alleen uren: `168h` = 7 dagen) |
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
| `ALLOW_SQLITE_IN_PRODUCTION` | `false` | SQLite in productie zónder Litestream toestaan (alleen met een eigen back-up) |
| `DEV_USER_NAME` / `DEV_USER_ROLES` | `ontwikkelaar` / leeg | Alleen bij `AUTH_MODE=dev` |

### Checklist productie (alle fases)

1. **Fase 1–2** – `APP_ENV=production`, `AUTH_MODE=easyauth`, `LITESTREAM_REPLICA_URL` (back-up;
   zie *Deployment naar Azure*), precies één container (`maxReplicas=1`).
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
  Tags koppelen aan user stories (`US01` … `US08`); `smoke` draait ook na een deploy. De
  scenario's voor US11–US15 (meerdere stichtingen, uitnodigen, online doneren, donaties
  corrigeren, platformbeheer) zijn met pytest geautomatiseerd; bij elk scenario staat de test.
- De UI is handmatig gecontroleerd op desktop en mobiel (390 px). Geautomatiseerde
  browsertests (robotframework-browser) zijn een mogelijke volgende stap.

## Deployment naar Azure

De workflow [ci-cd.yml](./.github/workflows/ci-cd.yml) voert bij
elke push of PR uit: kwaliteit en unit tests, pip-audit, Robot-tests,
een Docker-build met containerrooktest (inclusief een back-up- en hersteltest met Litestream)
en security-tests:

| Soort | Tool | Wat |
|---|---|---|
| SCA | pip-audit, Trivy | Kwetsbare Python-packages; kwetsbaarheden in de container-image (HIGH/CRITICAL) |
| SAST | Bandit, CodeQL | Onveilige code in Python en JavaScript (resultaten onder *Security → Code scanning*) |
| Secrets | Gitleaks | Geheimen in code en git-historie |
| DAST | OWASP ZAP baseline | Passieve scan van de draaiende container; rapport als artifact (nog niet blokkerend) |

Op `main` wordt het image pas naar ghcr.io gepusht als alle tests en scans slagen.
Deployen gebeurt handmatig via *Run workflow* met `deploy_azure`.

Voor de eerste deployment zijn deze eenmalige stappen nodig:

1. **Opslag voor de back-up** (Azure Blob Storage, een paar cent per maand):

   ```bash
   az storage account create -n <opslagaccount> -g rg-ashab-al-jannah -l westeurope \
     --sku Standard_LRS --kind StorageV2 --min-tls-version TLS1_2 --allow-blob-public-access false
   az storage container create --account-name <opslagaccount> -n ledenadmin --auth-mode login
   # Extra vangnet: verwijderde back-upbestanden blijven 14 dagen terug te halen.
   az storage account blob-service-properties update --account-name <opslagaccount> \
     -g rg-ashab-al-jannah --enable-delete-retention true --delete-retention-days 14
   ```

2. **GitHub OIDC**: maak een app-registratie met een federated credential voor
   environment `production` en geef die Contributor op de resource group. Zet
   `AZURE_CLIENT_ID`, `AZURE_TENANT_ID` en `AZURE_SUBSCRIPTION_ID` als secrets.
3. **Secret en variabele** (environment `production`): secret `GHCR_PULL_TOKEN` (PAT met
   alleen `read:packages`) en variabele `LITESTREAM_REPLICA_URL`, bijvoorbeeld
   `abs://<opslagaccount>@ledenadmin/ledenadmin`.
4. **Toegang tot de opslag voor de app** (na de eerste deploy; tot dan start de container
   niet, omdat Litestream de back-up niet kan lezen). De app meldt zich aan met haar
   managed identity, dus er is geen opslagsleutel nodig:

   ```bash
   PRINCIPAL=$(az containerapp show -n ashab-al-jannah -g rg-ashab-al-jannah --query identity.principalId -o tsv)
   SCOPE=$(az storage account show -n <opslagaccount> -g rg-ashab-al-jannah --query id -o tsv)/blobServices/default/containers/ledenadmin
   az role assignment create --assignee-object-id "$PRINCIPAL" --assignee-principal-type ServicePrincipal \
     --role "Storage Blob Data Contributor" --scope "$SCOPE"
   az containerapp revision restart -n ashab-al-jannah -g rg-ashab-al-jannah \
     --revision $(az containerapp revision list -n ashab-al-jannah -g rg-ashab-al-jannah --query "[0].name" -o tsv)
   ```

5. **Aanmelden (Easy Auth)**: zie [4-EntraExternalID.md](4-EntraExternalID.md). Vereis
   aanmelding en sluit alleen de health-check uit:

   ```bash
   az containerapp auth update -n ashab-al-jannah -g rg-ashab-al-jannah \
     --unauthenticated-client-action RedirectToLoginPage --excluded-paths /api/v1/health
   ```

Aandachtspunten:
- Er draait **altijd precies één container** (`maxReplicas=1`): twee containers die dezelfde
  database en back-up beschrijven, maken de gegevens kapot. Bij een nieuwe versie stopt de
  workflow daarom eerst de oude container en start dan de nieuwe; de app is dan enkele
  seconden onbereikbaar.
- Door scale-to-zero duurt de eerste request na een stille periode een paar seconden: de
  container start en Litestream zet de database terug. Migraties draaien daarna bij het
  opstarten (`RUN_MIGRATIONS=true`).
- Controleer vóór ingebruikname de actuele limieten, kosten en regio van de gratis tegoeden.

### Back-up en herstel

- [docker-entrypoint.sh](./docker-entrypoint.sh) zet bij het opstarten de database terug uit
  de back-up als die nog niet op de schijf van de container staat, en start de app daarna
  onder `litestream replicate` ([litestream.yml](./litestream.yml)). Elke wijziging staat
  binnen ongeveer een seconde in Blob Storage; bij een harde crash kan dus hooguit de laatste
  seconde verloren gaan.
- Litestream maakt elke dag een volledige kopie en bewaart `LITESTREAM_RETENTION` (standaard
  7 dagen). Binnen die periode kun je naar elk moment terug.
- Kan de container de back-up niet lezen (bijv. geen rechten), dan start hij niet. Zo wordt
  nooit een lege database als nieuwe back-up weggeschreven.

**Een eerdere stand terugzetten** (bijv. na een fout van een gebruiker). Installeer
[Litestream](https://litestream.io/install/), bij voorkeur op Linux, macOS of in WSL (de
Windows-versie meldt na afloop onterecht "Access is denied", al is het bestand wel goed), en
meld je aan met `az login` (je account heeft de rol *Storage Blob Data Contributor* op de
container nodig):

```bash
# 1. Stand van een bepaald moment (UTC) ophalen en controleren
litestream restore -timestamp 2026-10-08T12:00:00Z -o herstel.db abs://<opslagaccount>@ledenadmin/ledenadmin
# 2. Als nieuwe back-up wegzetten onder een nieuw pad (de oude back-up blijft ongemoeid)
litestream replicate -once herstel.db abs://<opslagaccount>@ledenadmin/herstel-20261008
```

Zet daarna de variabele `LITESTREAM_REPLICA_URL` op het nieuwe pad en draai de workflow met
`deploy_azure`: de nieuwe container start leeg en zet `herstel.db` terug.

**Een kopie voor onderzoek** maak je met alleen stap 1, zonder `-timestamp` voor de laatste
stand. Open die nooit met een tweede app die naar dezelfde back-up schrijft.

### Overstap van Azure SQL

Draaide de app eerder op Azure SQL (`DATABASE_URL=mssql+pyodbc:...`), zet dan eenmalig de
gegevens over. De workflow weigert te deployen zolang de app nog `DATABASE_URL` heeft.

1. Lokaal: installeer ODBC Driver 18 en `pip install pyodbc`, en maak een lege database met
   het actuele schema: `$env:DATABASE_URL="sqlite:///./overstap.db"; alembic upgrade head`.
2. Kopieer alles (gebruik in de Azure SQL-URL `Authentication=ActiveDirectoryInteractive` in
   plaats van `ActiveDirectoryMsi`):

   ```powershell
   python -m ledenadmin.copy_database "<azure-sql-url>" "sqlite:///./overstap.db"
   ```

3. Zet het bestand als eerste back-up weg en verwijder de oude instelling:

   ```bash
   litestream replicate -once overstap.db abs://<opslagaccount>@ledenadmin/ledenadmin
   az containerapp update -n ashab-al-jannah -g rg-ashab-al-jannah --remove-env-vars DATABASE_URL
   ```

4. Volg de eenmalige stappen hierboven (opslag, variabele, rol) en deploy. Bewaar de Azure
   SQL-database nog even als vangnet en verwijder hem daarna.

## Uitbreidingen na de MVP

- **Boekhouding (US09)**: implementeer `ReportExporter` voor Moneybird of Exact Online,
  met een preview en expliciete bevestiging. Herhaalde exports mogen geen dubbele
  boekingen veroorzaken.
- **Bankafschriften (US10)**: begin bij voorkeur met CAMT.053- of CSV-exports van de bank
  (betrouwbaarder dan PDF); pdfplumber kan als fallback. AI mag matches voorstellen,
  maar definitief koppelen gebeurt altijd na menselijke bevestiging.
- Donaties crediteren met tegenboekingen (in plaats van direct bewerken) zodra er een
  koppeling met een boekhoudpakket is.

## Open besluiten

1. Definitieve rolverdeling en of donaties voor inactieve leden zijn toegestaan.
2. Bewaartermijnen (o.a. van het logboek en de back-up, nu 7 dagen) en AVG-procedures.
   Back-up en herstel zijn ingericht met Litestream (zie *Back-up en herstel*).
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
