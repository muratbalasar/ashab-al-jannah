# Inloggen met Entra External ID (fase 4)

Handleiding om Ashab al-Jannah open te stellen voor iedereen: inloggen met Google, Microsoft,
Apple, Facebook of een eenmalige e-mailcode. Alles gebeurt in de Azure/Entra-portal; de app
leest de identiteit uit Easy Auth van Azure Container Apps (zie
[3-MultiTenantOntwerp.md](./3-MultiTenantOntwerp.md) § 5).

Kosten: Entra External ID is gratis tot 50.000 maandelijks actieve gebruikers.

> De schermnamen in de portal veranderen af en toe. Zoek bij twijfel op de vetgedrukte termen;
> tussen haakjes staat de Engelse naam. De commando's voor de command line staan in
> [README.md, stap 8 en 9](./README.md#stap-8--inloggen-met-entra-external-id-easy-auth); deze
> handleiding geeft de achtergrond en de stappen in de portal.

## 1. Externe tenant aanmaken

1. Ga naar [entra.microsoft.com](https://entra.microsoft.com) en meld je aan met je eigen
   Azure-account.
2. **Entra ID → Overzicht → Tenants beheren → Maken** (*Manage tenants → Create*), kies
   **External**.
3. Vul een naam in (bijv. `ashab-login`) en een domein (bijv. `ashablogin`), kies je
   Azure-abonnement, resource group `rg-ashab-al-jannah` en de regio **Europe**.
4. Wacht tot de tenant is aangemaakt en wissel ernaartoe. Het betrouwbaarst is een nieuw
   tabblad met `https://entra.microsoft.com/?tenant=<domein>.onmicrosoft.com`; controleer
   rechtsboven dat je in de nieuwe tenant zit.

> Zie je in de externe tenant een fout met `errorCode 401` en het id van je abonnement, dan
> gebruikt de portal nog de context van je gewone tenant. Open de URL hierboven en ga niet via
> *Abonnementen* of *Resourcegroepen*: die horen bij je gewone tenant.

## 2. App-registratie

Met de command line: [README, stap 8b](./README.md#stap-8--inloggen-met-entra-external-id-easy-auth)
(app, redirect-URI, `email`-claim, Graph-permissies met admin consent). In de portal:

1. In de externe tenant: **Toepassingen → App-registraties → Nieuwe registratie**
   (*Applications → App registrations → New registration*).
2. Naam: `Ashab al-Jannah`. Accounttype: **Alleen accounts in deze organisatiemap**
   (*Accounts in this organizational directory only*).
3. Omleidings-URI (platform **Web**):
   `https://<jouw-app>.azurecontainerapps.io/.auth/login/aad/callback`
4. Na het aanmaken:
   - Noteer de **Toepassings-id (client)** en de **Map-id (tenant)**.
   - **Verificatie** (*Authentication*): vink **Id-tokens** aan.
   - **Certificaten en geheimen → Nieuw clientgeheim**; noteer de waarde (alleen nu
     zichtbaar, deel hem met niemand).
   - **Tokenconfiguratie → Optionele claim toevoegen → ID** en vink `email` aan (en bevestig
     de Microsoft Graph-permissie als daarom wordt gevraagd).
   - **API-machtigingen**: Microsoft Graph `openid`, `profile`, `email` en `offline_access`, en
     klik **Beheerderstoestemming verlenen** (*Grant admin consent*). Gebruikers in een externe
     tenant kunnen zelf geen toestemming geven.

## 3. Inlogmethoden (identity providers)

**External Identities → All identity providers**:

| Provider | Wat je nodig hebt | Waar je dat haalt |
|---|---|---|
| E-mail met eenmalige code | niets | Standaard aanwezig; zet in de user flow **Email one-time passcode** aan |
| Microsoft-account | niets | Standaard beschikbaar |
| Google | Client ID + secret | [Google Cloud Console](https://console.cloud.google.com) → APIs & Services → Credentials → OAuth client (Web). Redirect-URI's: zie de Entra-pagina van de Google-provider |
| Facebook | App ID + secret | [developers.facebook.com](https://developers.facebook.com) → app aanmaken → Facebook Login. Redirect-URI: zie de Entra-pagina van de Facebook-provider |
| Apple | Services ID, Team ID, Key ID en .p8-sleutel | [developer.apple.com](https://developer.apple.com) (betaald Apple Developer-account nodig, ca. € 99 per jaar). Optioneel; kan later |

Instagram heeft geen eigen login meer voor websites; gebruikers met Instagram loggen in via
Facebook.

## 4. User flow

1. **Externe identiteiten → Gebruikersstromen → Nieuwe gebruikersstroom** (*External
   Identities → User flows → New user flow*), naam bijv. `signup_signin`.
2. Kies de identity providers uit stap 3. Begin met **Eenmalige wachtwoordcode voor e-mail**
   (onder *E-mailaccounts*); die werkt zonder externe accounts. Andere providers voeg je later
   toe.
3. Gebruikerskenmerken: **Weergavenaam** (*Display Name*); het e-mailadres wordt altijd
   gevraagd.
4. Open de stroom → **Toepassingen → Toepassing toevoegen**: koppel `Ashab al-Jannah`.

## 5. Easy Auth op de Container App

Met de command line ([README, stap 8d](./README.md#stap-8--inloggen-met-entra-external-id-easy-auth)):

```bash
az containerapp auth microsoft update -g <resourcegroep> -n <app> \
  --client-id <client-id> --client-secret "<secret>" \
  --issuer "https://<domein>.ciamlogin.com/<tenant-id>/v2.0" --yes
az containerapp auth update -g <resourcegroep> -n <app> --enabled true \
  --unauthenticated-client-action RedirectToLoginPage --excluded-paths "/api/v1/health"
```

Of in de Azure-portal (je gewone tenant) bij de Container App: **Verificatie → Id-provider
toevoegen → Microsoft** (*Authentication → Add identity provider*):

- App registration type: **Provide the details of an existing app registration**.
- Client ID en secret uit stap 2.
- Issuer URL: `https://<domein>.ciamlogin.com/<tenant-id>/v2.0`
- Unauthenticated requests: **HTTP 302 Found redirect**.

De *token store* staat bij Container Apps standaard uit (daarvoor is aparte opslag nodig).
De app heeft hem niet nodig, maar daardoor werkt `/.auth/me` niet (404); zie stap 7.

## 6. App-instellingen

| Variabele | Waarde |
|---|---|
| `AUTH_MODE` | `easyauth` (zet de workflow al) |
| `EASYAUTH_LOGIN_URL` | `/.auth/login/aad` (standaard) |
| `SUPERADMIN_SUBJECTS` | `<issuer>\|<subject>` van je eigen account, zie stap 7 |
| `PUBLIC_BASE_URL` | `https://<jouw-app>.azurecontainerapps.io` |

Wijzig variabelen altijd volgens
[README, Instellingen later wijzigen](./README.md#instellingen-later-wijzigen): eerst de draaiende
container stoppen, anders schrijven er even twee containers naar dezelfde database.

## 7. Jezelf superadmin maken

1. Log in op de app (zie stap 8 voor een nieuw account).
2. Haal je `issuer|subject` uit de database van de draaiende container (alleen lezen):

   ```bash
   az containerapp exec -n <app> -g <resourcegroep> --command sh
   python -c "import sqlite3;[print(f'{i}|{s}   <- {e}') for i,s,e in sqlite3.connect('/data/ledenadmin.db').execute('select issuer,subject,email from users')]"
   exit
   ```

   Neem bij jouw e-mailadres alles vóór `   <-` over. `/.auth/me` werkt niet, omdat de token
   store uit staat (stap 5).
3. Zet `SUPERADMIN_SUBJECTS=<issuer>|<subject>` (zie stap 6); `/platform` is daarna zichtbaar.
   Uitgewerkt: [README, stap 9](./README.md#stap-9--jezelf-superadmin-maken-cloud-shell).

## 8. Controleren

- Open de app in een privévenster: je komt op de inlogpagina van `<domein>.ciamlogin.com`.
- Nieuwe gebruikers kiezen **Geen account? Maak er een**. Dat geldt ook voor jou: je
  beheerdersaccount van de tenant is geen klantaccount, dus "Er is geen account met dit
  e-mailadres gevonden" is normaal bij de eerste keer.
- Log in met elke provider; na het inloggen zie je de startpagina met **Nieuwe stichting
  aanmaken**.
- Een uitnodiging werkt alleen als het e-mailadres van de login gelijk is aan het
  uitgenodigde adres. De app gebruikt het e-mailadres niet als de provider meldt dat het
  niet geverifieerd is (`email_verified=false`).
- Meer problemen en oplossingen: [README, Troubleshooting deployment](./README.md#troubleshooting-deployment).

## Hoe de app de identiteit leest

- Gebruiker = `issuer` + `subject` (`oid`/`sub`). De issuer in het token begint met het
  tenant-**id**, niet met het domein: `https://<tenant-id>.ciamlogin.com/<tenant-id>/v2.0`. Wie
  met Google én Microsoft inlogt, is voor de app twee gebruikers; via een uitnodiging kunnen
  beide aan dezelfde stichting gekoppeld worden.
- Rollen komen uit de database (`memberships`), niet uit het token. Alleen in de organisatie
  `standaard` worden Entra app-rollen nog overgenomen (overgang vanaf de oude installatie).
