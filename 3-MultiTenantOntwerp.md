# Technisch ontwerp: multi-tenant en self-service

Status: **fases 1–7 gebouwd** (zie [§ 12.1](#121-stand-van-zaken)). De besluiten staan in
[§ 11](#11-besluiten-3-oktober-2026); wat nog niet is gebouwd staat in [§ 13](#13-nog-niet-gebouwd).

## 1. Doel en uitgangspunten

- Meerdere stichtingen gebruiken één online installatie, en hun gegevens blijven strikt gescheiden.
- **Self-service:** een stichting meldt zich zelf aan, nodigt zelf haar bestuur en leden uit
  en beheert alles zelf. De platformeigenaar regelt alleen de eerste installatie.
- **Platformeigenaar = superadmin:** kan stichtingen bekijken, blokkeren en verwijderen,
  maar ziet standaard geen ledengegevens (zie § 5.3).
- **Gratis infrastructuur:** binnen de gratis Azure-tegoeden. Waar dat niet kan, staat het
  hieronder expliciet vermeld.
- Rollen en rechten blijven zoals ze zijn (`Permission`, `ROLE_PERMISSIONS`), maar gelden
  per stichting en komen uit de database.

## 2. Architectuur in één oogopslag

```
Gebruiker ──> Entra External ID (inloggen: Google, Microsoft, Apple, Facebook, e-mailcode)
                    │  OIDC-token (sub, e-mail)
                    ▼
Azure Container Apps (Easy Auth valideert token) ──> app (FastAPI)
                    │                                   │
                    │                    Membership-tabel: gebruiker × stichting × rol
                    ▼                                   ▼
        SQLite-bestand in de container, kolom organization_id
                    │  Litestream (continu, ± 1 s)
                    ▼
        Azure Blob Storage (back-up; teruggezet bij het opstarten)
```

| Onderdeel | Keuze | Kosten |
|---|---|---|
| Inloggen | Microsoft Entra External ID (externe tenant) | Gratis tot 50.000 actieve gebruikers per maand |
| Hosting | Azure Container Apps, schaalt naar 0, precies één container | Gratis maandtegoed (180.000 vCPU-seconden, 2 mln. verzoeken) |
| Database | SQLite met Litestream naar Azure Blob Storage (§ 11 #5) | Een paar cent per maand voor de opslag |
| Image | ghcr.io (publieke repo) | Gratis |
| E-mail (uitnodigingen) | Zie § 7.3 | Gratis tot een bepaald volume |
| KVK-controle | Zie § 6 | **Niet gratis** |

## 3. Datamodel

### 3.1 Nieuwe tabellen

```
Organization
  id, slug (uniek, bijv. "stichting-al-fajr"), name, kvk_number (uniek, nullable),
  kvk_verified_at, city, contact_email, status (actief | geblokkeerd | verwijderd),
  timezone, settings (json: ai_enabled, bewaartermijn logboek, ...), created_at

User                                   -- één per persoon, ongeacht het aantal stichtingen
  id, issuer, subject                  -- uniek paar uit het OIDC-token (sub)
  email (geverifieerd), display_name, is_superadmin, created_at, last_login_at

Membership                             -- welke rol heeft een gebruiker bij een stichting
  user_id, organization_id, role (beheerder | penningmeester | bestuurder | lid),
  member_id (nullable → koppeling met Member, verplicht bij rol "lid"),
  created_at, created_by
  UNIQUE (user_id, organization_id, role)

Invitation
  id, organization_id, email, role, member_id (nullable), token_hash, expires_at,
  accepted_at, created_by
```

### 3.2 Bestaande tabellen krijgen `organization_id`

`members`, `categories`, `subcategories` (via categorie), `donations`, `member_fields`,
`member_field_values` (via lid) en `audit_log`.

Unieke sleutels worden per stichting, bijvoorbeeld:
- `members.email`: uniek → uniek per `(organization_id, email)`
- `categories.name`: uniek → uniek per `(organization_id, name)`
- `member_fields.label`: uniek → uniek per `(organization_id, label)`

### 3.3 Migratie van de huidige installatie

1. Alembic-migratie maakt de nieuwe tabellen aan en de kolom `organization_id` (eerst nullable).
2. Alle bestaande rijen gaan naar één nieuwe organisatie, "Standaard".
3. Daarna wordt de kolom `NOT NULL` en komen de nieuwe unieke sleutels.

## 4. Scheiding tussen stichtingen

Het grootste risico is dat stichting A gegevens van stichting B ziet. Daarom geldt:

1. **Centraal filter.** Een `TenantContext` (organisatie-id en principal) wordt per verzoek
   bepaald en aan de `ServiceContainer` meegegeven. Repositories voegen
   `WHERE organization_id = :org` zelf toe; routes en services kunnen het niet vergeten.
   Een SQLAlchemy-event `do_orm_execute` met `with_loader_criteria` dient als vangnet: elke
   query op een tenant-tabel zonder organisatiecontext geeft een fout.
2. **Schrijven:** nieuwe rijen krijgen `organization_id` uit de context, nooit uit
   formulier- of API-invoer.
3. **Verwijzingen controleren:** een donatie mag alleen naar een lid en subcategorie van
   dezelfde stichting verwijzen (controle in de service plus samengestelde foreign keys).
4. **Tests:** een vaste testset maakt twee stichtingen aan en controleert voor elke route en
   API-endpoint dat A niets van B kan lezen, wijzigen of verwijderen. Een gok-ID van B geeft
   een 404, geen 403, zodat er niets uitlekt over het bestaan ervan.
5. **Optioneel later:** Row-Level Security als tweede slot, bij een overstap naar PostgreSQL.

Aparte databases per stichting vallen af: het beheer wordt zwaarder (migraties en back-ups
per database).

## 5. Inloggen, rollen en de superadmin

### 5.1 Inloggen

- Entra External ID (externe tenant), met:
  - Google, Facebook, Apple (OIDC) en Microsoft-accounts
  - **e-mail met eenmalige code**, voor mensen zonder social account
- Container Apps Easy Auth valideert het token; de app leest `iss`, `sub`, `email` en `name`
  uit de bestaande `x-ms-client-principal`-header (`EasyAuthProvider` wordt uitgebreid).
- Bij de eerste login wordt een `User` aangemaakt op basis van `(issuer, subject)`. Het
  e-mailadres wordt alleen gebruikt als het geverifieerd is (`email_verified`), om
  uitnodigingen te koppelen.
- Rollen komen **niet** meer uit het token, maar uit `Membership`.

### 5.2 Rollen

| Rol | Rechten |
|---|---|
| beheerder | Alles binnen de eigen stichting, inclusief gebruikers uitnodigen en de stichting verwijderen |
| penningmeester | Zoals nu (leden lezen, donaties, rapportage, export) |
| bestuurder | Zoals nu (rapportage en inzichten, zonder persoonsgegevens) |
| **lid** (nieuw) | Alleen de eigen gegevens: eigen profiel, eigen donaties en eigen jaaroverzicht. Later: zelf doneren (§ 8) |

Nieuwe permissies voor de rol lid: `SELF_READ` en (later) `SELF_DONATE`. Alle bestaande
routes blijven via `Permission` werken; de lid-pagina's krijgen een eigen
`/mijn`-gedeelte, en de queries daarvan filteren altijd ook op het gekoppelde `member_id`.

### 5.3 Superadmin (platformeigenaar)

- Ingesteld via de omgevingsvariabele `SUPERADMIN_SUBJECTS` (een of meer `issuer|sub`-paren
  van je eigen account), niet via de database. Zo kan niemand zichzelf superadmin maken.
- Ziet op `/platform`: alle stichtingen met naam, KVK, status, aantal gebruikers en leden,
  en datum van laatste activiteit. Kan een stichting **blokkeren**, **deblokkeren** of
  **verwijderen**.
- Ziet **geen ledengegevens of donaties**. Is dat voor support toch nodig, dan gebeurt dat
  alleen met een expliciete "toegang aanvragen"-stap die de beheerder van de stichting moet
  goedkeuren. Elke inzage wordt gelogd (AVG: jij bent verwerker, niet eigenaar van de data).

## 6. Een stichting aanmelden (self-service)

### 6.1 Verloop

1. Een ingelogde gebruiker zonder stichting ziet **Nieuwe stichting aanmaken**.
2. Hij vult het KVK-nummer in; de app zoekt de naam en plaats op en vult ze voor.
3. Hij bevestigt de gegevens en een contact-e-mailadres.
4. Het contact-e-mailadres moet hetzelfde zijn als zijn geverifieerde login-e-mailadres, of
   wordt bevestigd met een link (§ 7.3).
5. De stichting wordt actief; de aanmaker wordt **beheerder** en krijgt de standaard
   categorieën.

### 6.2 KVK-controle: wat wel en niet kan

| Controle | Kan het? | Hoe |
|---|---|---|
| Bestaat het KVK-nummer? | Ja | KVK API **Zoeken** |
| Klopt de naam? | Ja | KVK API Zoeken (handelsnaam) |
| Is het een stichting of vereniging? | Ja | KVK **Basisprofiel** (rechtsvorm) |
| Is de organisatie actief (niet opgeheven)? | Ja | Basisprofiel |
| Hoort het e-mailadres van de beheerder bij de stichting? | **Nee** | Het handelsregister bevat geen e-mailadressen, en bestuurders zijn niet via deze API op te vragen |

Het e-mailadres kan dus niet via KVK worden gecontroleerd. Wel mogelijk:
- **E-mailverificatie:** bewijst dat de persoon het adres bezit, niet dat hij bij de
  stichting hoort.
- **Domeincheck (optioneel):** als de website uit het KVK-profiel hetzelfde domein heeft als
  het e-mailadres (`info@alfajr.nl` en `www.alfajr.nl`), krijgt de stichting de status
  "geverifieerd". Anders "niet geverifieerd" (zichtbaar voor de superadmin).
- **Één stichting per KVK-nummer:** een tweede aanmelding met hetzelfde nummer wordt
  geweigerd met de melding om de bestaande beheerder te benaderen. Een
  "eigendom claimen"-procedure kan later, via de superadmin.

### 6.3 Kosten KVK

De KVK API is **niet gratis**: een abonnement van ongeveer € 6,40 per maand, plus € 0,02
per opvraging van het Basisprofiel (Zoeken is gratis per opvraging). Ter overweging:
- **Optie 1:** KVK-controle aan, voor ongeveer € 6,40 per maand plus een paar cent per
  aanmelding.
- **Optie 2:** KVK-nummer alleen op formaat controleren (8 cijfers) en uniek houden, zonder
  API. Gratis, maar minder bescherming tegen nep-aanmeldingen.
- De app ondersteunt beide via `KVK_API_KEY`: zonder sleutel draait optie 2.

### 6.4 Misbruik beperken

- Maximaal 1 nieuwe stichting per gebruiker per 24 uur, en maximaal 3 in totaal.
- Een nieuwe stichting heeft het eerste 14 dagen een limiet (bijv. 100 leden), tot ze
  geverifieerd is.
- De superadmin krijgt een melding (e-mail of overzicht) bij elke nieuwe stichting en kan
  blokkeren, maar hoeft niets goed te keuren.

## 7. Gebruikers uitnodigen

### 7.1 Bestuur

- De beheerder voert een e-mailadres en rol in. Er wordt een `Invitation` aangemaakt met een
  willekeurig token; alleen de hash wordt bewaard. De link is 7 dagen geldig en eenmalig te
  gebruiken.
- Wie de link opent, logt in (elke provider). De koppeling wordt alleen gemaakt als het
  **geverifieerde** login-e-mailadres overeenkomt met het uitgenodigde adres.
- Er moet altijd minstens één beheerder overblijven; de laatste beheerder kan zichzelf niet
  verwijderen of degraderen.

### 7.2 Leden

- Op de ledenpagina: **Uitnodigen voor Mijn omgeving** (per lid of in bulk voor alle leden
  met een e-mailadres).
- De uitnodiging is gekoppeld aan het `member_id`; na acceptatie krijgt de gebruiker de rol
  **lid** met die koppeling.
- Alternatief zonder e-mail: een lid logt in met hetzelfde e-mailadres als in de
  ledenadministratie en koppelt zichzelf, maar alleen als de beheerder "leden mogen zichzelf
  koppelen" heeft aangezet.

### 7.3 E-mail versturen

Voor uitnodigingen is een maildienst nodig. Opties:
- **Azure Communication Services Email:** fracties van een cent per mail; bij een paar
  honderd mails per maand praktisch gratis, maar niet volledig gratis.
- **Brevo of een vergelijkbare dienst:** gratis tot ongeveer 300 mails per dag.
- **Geen mail:** de beheerder kopieert de uitnodigingslink en deelt die zelf (WhatsApp, e-mail).
  Altijd beschikbaar, ook als terugvaloptie.

## 8. Later: zelf doneren (rol lid)

- Een betaalprovider met iDEAL, bijvoorbeeld **Mollie Connect**: elke stichting koppelt haar
  **eigen** Mollie-account. Het geld gaat rechtstreeks naar de stichting en nooit via het
  platform. Dat voorkomt dat jij betaaldienstverlener wordt (vergunningsplicht).
- Na een geslaagde betaling (webhook) registreert de app de donatie automatisch, met de
  categorie die het lid koos.
- Kosten: per transactie bij Mollie (voor rekening van de stichting), geen vaste kosten voor
  het platform.

## 9. AVG en beveiliging

- **Rolverdeling:** de stichting is verwerkingsverantwoordelijke; de platformeigenaar is
  verwerker. Bij aanmelden accepteert de beheerder de verwerkersovereenkomst en de
  gebruiksvoorwaarden (vastgelegd met datum en versie).
- **Export en verwijderen per stichting:** een beheerder kan alle gegevens exporteren
  (CSV/JSON) en de stichting verwijderen. Verwijderen is eerst 30 dagen een "zachte"
  verwijdering, daarna definitief.
- **Leden:** een lid kan zijn eigen gegevens inzien (`/mijn`).
- **Logboek:** per stichting, alleen zichtbaar voor de eigen beheerder. Bewaartermijn per
  stichting instelbaar (standaard 41 dagen).
- **AI-inzichten:** alleen totalen van de eigen stichting; per stichting aan of uit te zetten.
- **Sessies:** organisatiekeuze in een ondertekende cookie; bij elk verzoek wordt opnieuw
  gecontroleerd of het lidmaatschap nog bestaat.

## 10. Kosten en grenzen van de gratis tegoeden

| Onderdeel | Grens | Wat als het op is |
|---|---|---|
| Container Apps | 180.000 vCPU-seconden per maand (≈ 50 uur bij 1 vCPU, bij 0,25 vCPU ≈ 200 uur) | Betalen per gebruik, kleine bedragen |
| Blob Storage (back-up) | Geen gratis tegoed; enkele MB's tot GB's | Een paar cent per maand |
| Entra External ID | 50.000 actieve gebruikers per maand | $ 0,03 per extra gebruiker |

Sinds besluit 5 (§ 11) is er geen rekentijdgrens van een database meer: SQLite draait in de
container zelf. Het belangrijkste kostenrisico is nu de rekentijd van Container Apps bij
`minReplicas=1`; stel een budgetwaarschuwing in.

## 11. Besluiten (3 oktober 2026)

| # | Onderwerp | Besluit |
|---|---|---|
| 1 | KVK-controle | Gratis: controle op formaat (8 cijfers) en maximaal één stichting per KVK-nummer. Is er een `KVK_API_KEY`, dan controleert de app ook via de KVK-API. |
| 2 | Nieuwe stichting | Direct actief, **zonder limieten**. De superadmin krijgt een melding (e-mail en het overzicht in `/platform`). § 6.4 vervalt, op de aanmaaklimiet per gebruiker na. |
| 3 | E-mail | **Brevo** (gratis tot 300 mails per dag) én altijd de mogelijkheid om de link te kopiëren en zelf te delen. De app telt de mails per dag. Bij 80% verschijnt een waarschuwing in een infobalk. Bij 300 mails blokkeert de app het versturen tot de volgende dag, met een melding dat de link handmatig gedeeld moet worden. |
| 4 | Rol lid | Alleen via een uitnodiging van de beheerder; leden kunnen zichzelf niet koppelen. |
| 5 | Database | **SQLite-bestand** op de lokale schijf van de container, met **Litestream** dat continu een back-up naar Azure Blob Storage maakt (een paar cent per maand). Bij het opstarten zet Litestream de database terug. Daarom draait er maximaal **1 replica** (`maxReplicas=1`). Hetzelfde model als lokaal, dus geen verschil tussen ontwikkeling en productie. Azure SQL vervalt; de rekentijdgrens uit § 10 speelt daarmee niet meer. Kies `minReplicas=0`, met een paar seconden opstarttijd, of `minReplicas=1`, dat meer van het gratis tegoed gebruikt. ✅ Gebouwd, zie § 12.1. |
| 6 | URL | `/o/{slug}/...`, bijvoorbeeld `/o/stichting-al-fajr/leden`. Het KVK-nummer werkt ook als verwijzing: `/o/12345678/leden` leidt door naar de slug. De slug is te wijzigen; oude slugs blijven doorverwijzen (nog niet gebouwd, zie § 13). |

Gevolgen:
- Het KVK-nummer wordt **verplicht en uniek** voor `Organization`.
- SQLite kan maar door één proces tegelijk beschreven worden. Dat is voldoende voor tientallen
  stichtingen met weinig gelijktijdige schrijfacties; de schaalgrens wordt bewaakt.
  Overstappen naar PostgreSQL blijft mogelijk via SQLAlchemy.

### 11.1 SQLite met meerdere gebruikers tegelijk

**Wat wel en niet tegelijk kan**
- **Lezen** (lijsten, rapportages, `/mijn`) kan door veel gebruikers tegelijk.
- **Schrijven** gaat één voor één. Een opslag duurt een paar milliseconden, dus wie tegelijk
  opslaat wacht kort en merkt dat in de praktijk niet. Grove schatting: honderden schrijfacties
  per seconde zijn haalbaar; de verwachte belasting is een paar per minuut.

**Voorwaarden** (verplicht, ze komen in fase 1)
1. **Precies één container** (`minReplicas` 0 of 1, `maxReplicas=1`). Twee containers die
   hetzelfde bestand beschrijven geven corrupte data, en Litestream ondersteunt maar één schrijver.
2. **Het databasebestand op de lokale schijf van de container**, niet op een Azure Files-share:
   die netwerkschijf verdraagt de bestandsvergrendeling van SQLite slecht. Bij het opstarten zet
   Litestream de database terug uit Blob Storage; daarna repliceert het continu.
3. **Verbindingsinstellingen** in `db.py`:
   - `PRAGMA journal_mode=WAL`: lezers en de schrijver blokkeren elkaar niet. Litestream heeft
     dit ook nodig.
   - `PRAGMA busy_timeout=5000`: wie tegelijk opslaat wacht maximaal 5 seconden in plaats van
     direct een foutmelding te krijgen.
   - `PRAGMA foreign_keys=ON`: de database bewaakt de verwijzingen tussen tabellen zelf.
4. **Uvicorn met één worker**, met één Litestream-proces naast de app in dezelfde container.

**Wat het kost**
- Met `minReplicas=0` duurt de eerste aanvraag na een stille periode een paar seconden: de
  container start en de database wordt teruggezet.
- Crasht de container hard, dan kunnen de laatste wijzigingen verloren gaan (maximaal ongeveer
  1 seconde, de replicatie-interval van Litestream).
- Geen hoge beschikbaarheid: tijdens een herstart of uitrol is de app enkele seconden niet bereikbaar.

**Wanneer overstappen naar PostgreSQL**
- Bij honderden actieve stichtingen met veel gelijktijdig schrijfwerk, of als meerdere containers
  of hoge beschikbaarheid nodig zijn.
- De overstap is grotendeels een nieuwe `DATABASE_URL` plus het overzetten van de gegevens,
  omdat de app SQLAlchemy en Alembic gebruikt.
- Signalen om te bewaken: wachttijden bij opslaan (`database is locked` in de logs) en
  responstijden.

## 12. Fasering

| Fase | Inhoud | Resultaat |
|---|---|---|
| 1 | Datamodel, migratie, centrale tenantfilter en isolatietests | Huidige app werkt als één stichting, nu tenant-veilig |
| 2 | `User`, `Membership`, rollen uit de database, superadmin | Inloggen en rollen per stichting |
| 3 | Stichting aanmelden, KVK-controle, uitnodigingen | Self-service |
| 4 | Entra External ID instellen (Google, Microsoft, Apple, Facebook, e-mailcode) | Iedereen kan inloggen |
| 5 | Rol lid en `/mijn`-omgeving | Leden zien hun eigen gegevens |
| 6 | Export en verwijderen per stichting, platformoverzicht | AVG-compleet |
| 7 | Zelf doneren via Mollie (eigen sleutel per stichting) | Online donaties |

### 12.1 Stand van zaken

- **Fase 1 ✅ gereed.** Tabel `organizations`, `organization_id` op alle gegevens, centrale filter in `tenancy.py`, migratie `0004`.
- **Fase 2 ✅ gereed.**
  - Tabellen `users` (issuer + subject uniek) en `memberships` (gebruiker, organisatie, rol, optioneel lid), migratie `0005`. Rol `lid` met recht `self:read`.
  - Alle pagina's en de API staan onder `/o/{slug}/...` (bijv. `/o/standaard/leden`, `/o/standaard/api/v1/members`). `/api/v1/health` blijft globaal. Een KVK-nummer in plaats van de slug stuurt door naar de slug.
  - Rollen komen uit `memberships`. Alleen in de standaardorganisatie worden rollen uit het token (Entra app-rollen of `X-Dev-Roles`) overgenomen en vastgelegd, zodat de huidige installatie blijft werken.
  - Geen lidmaatschap, onbekende of geblokkeerde organisatie: altijd 404 (er lekt niet uit of een stichting bestaat).
  - `/` stuurt door naar je organisatie, of toont een keuzelijst bij meerdere organisaties. Oude URL's (`/leden`, ...) sturen door naar `/o/standaard/...`.
  - Superadmin via `SUPERADMIN_SUBJECTS` (`issuer|subject`, komma-gescheiden). `/platform` toont organisaties met aantal gebruikers en kan blokkeren/deblokkeren; zonder lidmaatschap ziet de superadmin geen ledengegevens.
- **Fase 3 ✅ gereed.**
  - `/aanmelden`: iedere ingelogde gebruiker maakt een stichting aan (naam, KVK, plaats, contact-e-mail) en wordt de eerste beheerder. Slug uit de naam (`-2` bij botsing). Standaardcategorieën worden aangemaakt.
  - KVK: altijd 8 cijfers en uniek (melding: vraag de bestaande beheerder om een uitnodiging). Met `KVK_API_KEY` ook een opzoeking in het Handelsregister; dan wordt `kvk_verified_at` gezet. Bij een storing van de API alleen de formaatcontrole.
  - Aanmaaklimiet per gebruiker: 1 per 24 uur, maximaal `MAX_ORGANIZATIONS_PER_USER` (standaard 3).
  - `/o/{org}/gebruikers` (recht `users:manage`, alleen beheerder): gebruikers en rollen, uitnodigen per e-mail en rol, rol verwijderen (nooit de laatste beheerder), uitnodiging intrekken. Leden worden uitgenodigd vanaf hun ledenpagina (rol `lid`, gekoppeld aan het ledenrecord).
  - Uitnodiging: willekeurig token, alleen de SHA-256-hash wordt bewaard, 7 dagen geldig, eenmalig. Accepteren via `/uitnodiging/{token}` kan alleen als het login-e-mailadres overeenkomt.
  - E-mail via Brevo (`BREVO_API_KEY`); zonder sleutel wordt alleen een kopieerbare link getoond. Teller per dag in `mail_counters`: waarschuwing vanaf 80%, bij `MAIL_DAILY_LIMIT` (300) geen mail meer, alleen de link. De superadmin krijgt een mail bij een nieuwe stichting (`SUPERADMIN_EMAIL`).
  - Migratie `0006`. `organizations.created_by_user_id` heeft bewust geen foreign key (SQLite kan die niet toevoegen zonder de tabel te hercreëren).
- **Fase 4 ✅ code gereed; inrichting in de portal volgens [4-EntraExternalID.md](./4-EntraExternalID.md).**
  - Easy Auth: het e-mailadres wordt genegeerd als `email_verified=false` of als het geen e-mailadres is (bijv. een gebruikersnaam in `preferred_username`).
  - `EASYAUTH_LOGIN_URL` is instelbaar.
- **Fase 5 ✅ gereed.**
  - `/o/{org}/mijn` (recht `self:read`): eigen gegevens, jaaroverzicht per categorie en eigen donaties, met keuze uit de laatste 6 jaar. Alle queries filteren op het `member_id` uit de eigen `membership`.
  - Een lid zonder andere rol komt na inloggen direct op `/mijn`; menu-item **Mijn omgeving** voor wie gekoppeld is.
  - Leden hebben geen toegang tot ledenlijst, donaties, rapportage, API of gebruikersbeheer (403).
- **Fase 6 ✅ gereed.**
  - `/o/{org}/instellingen` (recht `organization:manage`, alleen beheerder):
    - **Exporteren:** ZIP met `export.json` en CSV's (leden met extra velden, donaties, wijzigingen van donaties, categorieën, ledenvelden, gebruikers met rol). Alleen gegevens van de eigen organisatie.
    - **Verwijderen:** bevestigen door de slug te typen. Status wordt `verwijderd` en `deleted_at` wordt gezet (migratie `0007`); de organisatie geeft daarna 404.
  - Na 30 dagen wordt alles definitief gewist: lidmaatschappen, uitnodigingen, leden, donaties, categorieën, ledenvelden, logboek en de organisatie zelf. Dit gebeurt bij het starten van de app en bij het openen van `/platform`.
  - `/platform`: per organisatie KVK (met ✓ als gecontroleerd), plaats, aantal gebruikers en leden, laatste activiteit (uit het logboek) en status, plus totalen. Verwijderde organisaties kan de superadmin **herstellen** of **nu wissen**. Nog steeds geen persoonsgegevens.
  - Een verwijderde organisatie houdt haar KVK-nummer bezet tot ze gewist is, zodat herstellen mogelijk blijft.

### Fase 7 ✅ gereed – Online doneren (Mollie, optie A)

- Gekozen voor **optie A**: de stichting plakt haar eigen Mollie API-sleutel in Instellingen (geen Mollie Connect/OAuth, geen platformaccount). Sleutel wordt gecontroleerd bij Mollie en versleuteld (Fernet, `SECRET_ENCRYPTION_KEY`) opgeslagen.
- Nieuwe permissie `self:donate` voor de rol *lid*; tabel `payments` (migratie 0008).
- Flow: `/mijn` → `POST /mijn/doneren` → Mollie-checkout → `/mijn/betaling/{id}`; webhook `POST /betalingen/webhook/{slug}` (status altijd bij Mollie opgehaald, bedrag gecontroleerd, idempotent) boekt bij `paid` een donatie.
- Verwijderen/wissen van een organisatie neemt betalingen mee.

### Na fase 7

- **Database: SQLite met Litestream ✅** (besluit 5).
  - De image bevat Litestream (versie en checksum vast in de `Dockerfile`); de ODBC-driver voor Azure SQL is verwijderd. De database staat in de container op `/data/ledenadmin.db`.
  - `docker-entrypoint.sh`: met `LITESTREAM_REPLICA_URL` eerst `litestream restore` (alleen als er nog geen database is), daarna `litestream replicate -exec` met migraties en de app als subproces. Lukt het terugzetten niet, dan start de container niet.
  - Back-up naar Azure Blob Storage met de managed identity van de app (rol *Storage Blob Data Contributor*); dagelijkse snapshot, `LITESTREAM_RETENTION` standaard 7 dagen.
  - De app weigert in productie SQLite zonder `LITESTREAM_REPLICA_URL` (of expliciet `ALLOW_SQLITE_IN_PRODUCTION=true`).
  - De CI test terugzetten na het weggooien van een container. Bij een uitrol stopt de workflow eerst de oude container, zodat er nooit twee schrijvers zijn.
  - Overstap van een bestaande Azure SQL-database: `python -m ledenadmin.copy_database` (README, *Overstap van Azure SQL*).
- **Donaties bewerken ✅** (alleen beheerder, recht `donations:edit`): elk gewijzigd veld met oude en nieuwe waarde in `donation_changes` (migratie `0009`), ook in de export. Bij online betalingen liggen lid, bedrag en datum vast; bij een voorbij jaar waarschuwt de app.
- **Lokaal testen ✅**: in de ontwikkelmodus kan elke browser van gebruiker wisselen via `/dev/gebruiker` (bijv. om een uitnodiging te accepteren); uitleg onder Help → *Lokaal testen*.

## 13. Nog niet gebouwd

Onderdelen uit dit ontwerp die (nog) niet in de app zitten:

| § | Onderdeel | Opmerking |
|---|---|---|
| 5.3 | Superadmin vraagt toegang aan tot gegevens van een stichting (met goedkeuring en logging) | Nu ziet de superadmin alleen aantallen |
| 6.1 | Naam en plaats automatisch invullen via KVK; contact-e-mail bevestigen met een link | Bij aanmelden wordt alleen de plaats uit KVK overgenomen als die leeg is |
| 6.2 | KVK Basisprofiel (rechtsvorm, actief) en domeincheck "geverifieerd" | Alleen Zoeken-API met `KVK_API_KEY` |
| 7.2 | Alle leden in één keer uitnodigen voor Mijn omgeving | Nu per lid |
| 9 | Akkoord op verwerkersovereenkomst en voorwaarden bij aanmelden (met datum en versie) | Nodig vóór productie |
| 9 | Bewaartermijn van het logboek per stichting | Nu vast 41 dagen (`RETENTION` in `audit.py`) |
| 9 | AI-inzichten per stichting aan/uit | Nu één instelling voor het hele platform |
| 11 #6 | Slug wijzigen met doorverwijzing vanaf oude slugs | Slug ligt vast na aanmelden |

Vervallen door besluiten: limiet voor nieuwe stichtingen (§ 6.4, besluit 2), leden die zichzelf
koppelen (§ 7.2, besluit 4), Azure SQL (besluit 5) en de organisatiekeuze in een cookie (§ 9;
de organisatie staat in de URL, besluit 6).
