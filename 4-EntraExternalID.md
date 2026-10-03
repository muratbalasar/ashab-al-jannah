# Inloggen met Entra External ID (fase 4)

Handleiding om Ashab al-Jannah open te stellen voor iedereen: inloggen met Google, Microsoft,
Apple, Facebook of een eenmalige e-mailcode. Alles gebeurt in de Azure/Entra-portal; de app
leest de identiteit uit Easy Auth van Azure Container Apps (zie
[3-MultiTenantOntwerp.md](./3-MultiTenantOntwerp.md) § 5).

Kosten: Entra External ID is gratis tot 50.000 maandelijks actieve gebruikers.

> De schermnamen in de portal veranderen af en toe. Zoek bij twijfel op de vetgedrukte termen.

## 1. Externe tenant aanmaken

1. Ga naar [entra.microsoft.com](https://entra.microsoft.com) en meld je aan met je eigen
   Azure-account.
2. **Identity → Overview → Manage tenants → Create**, kies **External**.
3. Vul een naam in (bijv. `ashab-login`) en een domein (bijv. `ashablogin`), kies je
   Azure-abonnement en de regio **Europe**.
4. Wacht tot de tenant is aangemaakt en wissel ernaartoe (**Switch directory**).

## 2. App-registratie

1. In de externe tenant: **Applications → App registrations → New registration**.
2. Naam: `Ashab al-Jannah`. Accounttype: **Accounts in this organizational directory only**.
3. Redirect URI (platform **Web**):
   `https://<jouw-app>.azurecontainerapps.io/.auth/login/aad/callback`
4. Na het aanmaken:
   - Noteer de **Application (client) ID** en de **Directory (tenant) ID**.
   - **Certificates & secrets → New client secret**; noteer de waarde (alleen nu zichtbaar).
   - **Token configuration → Add optional claim → ID** en vink `email` aan (en bevestig de
     Microsoft Graph-permissie als daarom wordt gevraagd).

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

1. **External Identities → User flows → New user flow** (sign up and sign in).
2. Kies de identity providers uit stap 3.
3. Attributen bij aanmelden: **Display Name** en **Email Address**.
4. **Applications → Add application**: koppel `Ashab al-Jannah`.

## 5. Easy Auth op de Container App

In de Azure-portal (je gewone tenant) bij de Container App: **Authentication → Add identity
provider → Microsoft**:

- App registration type: **Provide the details of an existing app registration**.
- Client ID en secret uit stap 2.
- Issuer URL: `https://<domein>.ciamlogin.com/<tenant-id>/v2.0`
- Unauthenticated requests: **HTTP 302 Found redirect**.
- Token store: aan.

Of met de Azure CLI:

```powershell
az containerapp auth microsoft update -g <resourcegroep> -n <app> `
  --client-id <client-id> --client-secret <secret> `
  --issuer "https://<domein>.ciamlogin.com/<tenant-id>/v2.0" --yes
az containerapp auth update -g <resourcegroep> -n <app> `
  --unauthenticated-client-action RedirectToLoginPage --excluded-paths "/api/v1/health"
```

## 6. App-instellingen

| Variabele | Waarde |
|---|---|
| `AUTH_MODE` | `easyauth` |
| `EASYAUTH_LOGIN_URL` | `/.auth/login/aad` (standaard) |
| `SUPERADMIN_SUBJECTS` | `<issuer>\|<object-id>` van je eigen account, zie stap 7 |
| `PUBLIC_BASE_URL` | `https://<jouw-app>.azurecontainerapps.io` |

## 7. Jezelf superadmin maken

1. Log in op de app.
2. Open `https://<jouw-app>/.auth/me` en zoek de claims `iss` en `oid` (of
   `http://schemas.microsoft.com/identity/claims/objectidentifier`).
3. Zet `SUPERADMIN_SUBJECTS=<iss>|<oid>` en herstart de app. `/platform` is nu zichtbaar.

## 8. Controleren

- Log in met elke provider; na het inloggen zie je de startpagina met **Nieuwe stichting
  aanmaken**.
- Een uitnodiging werkt alleen als het e-mailadres van de login gelijk is aan het
  uitgenodigde adres. De app gebruikt het e-mailadres niet als de provider meldt dat het
  niet geverifieerd is (`email_verified=false`).

## Hoe de app de identiteit leest

- Gebruiker = `issuer` + `subject` (`oid`/`sub`). Wie met Google én Microsoft inlogt, is voor
  de app twee gebruikers; via een uitnodiging kunnen beide aan dezelfde stichting gekoppeld
  worden.
- Rollen komen uit de database (`memberships`), niet uit het token. Alleen in de organisatie
  `standaard` worden Entra app-rollen nog overgenomen (overgang vanaf de oude installatie).
