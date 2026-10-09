Deze kennis is alleen voor de platformbeheerder (superadmin).

Platformbeheer:
- Superadmin wordt u via de instelling SUPERADMIN_SUBJECTS met de waarde issuer|subject (meerdere komma-gescheiden). Inloggen met een andere inlogmethode geeft een ander issuer|subject.
- Op /platform: overzicht van alle stichtingen, blokkeren en deblokkeren, een verwijderde stichting herstellen of direct wissen, en het aantal fouten van de laatste 24 uur.
- SUPERADMIN_EMAIL ontvangt een mail bij elke nieuwe stichting, als e-mail via Brevo is ingesteld.

Hosting en deploy:
- De app draait als één container in Azure Container Apps (maximaal 1 tegelijk, gaat naar 0 bij geen gebruik). De database is SQLite op de schijf van de container; Litestream maakt continu een back-up naar Azure Blob Storage en zet die bij elke start terug.
- Er mag nooit meer dan één container tegelijk draaien. Nieuwe versies deployt de GitHub-workflow ci-cd.yml (Run workflow met deploy_azure); die stopt eerst de oude container.
- Instellingen wijzigen: eerst de actieve revision stoppen (az containerapp revision deactivate), dan az containerapp update --set-env-vars. Geheimen als Container Apps-secret met secretref.
- Logs: az containerapp logs show (app) en met --type system (opstarten, image ophalen).
- De volledige stappen en een troubleshootingtabel staan in README.md, Deployment naar Azure.

Belangrijke instellingen:
- APP_ENV=production, AUTH_MODE=easyauth, LITESTREAM_REPLICA_URL (verplicht voor de back-up), PUBLIC_BASE_URL (links in e-mails).
- MAX_ORGANIZATIONS_PER_USER (standaard 3), BREVO_API_KEY en MAIL_SENDER_EMAIL (e-mail), KVK_API_KEY (KVK-controle), SECRET_ENCRYPTION_KEY (Mollie-sleutels; kwijt = alle stichtingen moeten Mollie opnieuw koppelen).
- AI: AI_PROVIDER (local, openai of anthropic), AI_MODEL, OPENAI_API_KEY, OPENAI_BASE_URL (Azure OpenAI: https://<resource>.openai.azure.com/openai/v1/).
- Assistent: ASSISTANT_ENABLED=true werkt alleen met een externe AI_PROVIDER. Limieten: ASSISTANT_DAILY_LIMIT_PER_USER (standaard 20), ASSISTANT_DAILY_LIMIT_TOTAL (standaard 300), ASSISTANT_MAX_QUESTION_CHARS (500), ASSISTANT_MAX_OUTPUT_TOKENS (600).

Veelvoorkomende problemen:
- Container start niet na een deploy: de managed identity mist de rol Storage Blob Data Contributor op de back-upopslag.
- Na inloggen een fout of een lus: issuer, client-id of client secret van Easy Auth klopt niet.
- /platform geeft geen toegang: SUPERADMIN_SUBJECTS wijkt af; de issuer begint met het tenant-id.
- Mollie-betalingen blijven open: de webhook /betalingen/webhook/<slug> moet zonder inloggen bereikbaar zijn.
- Assistent zegt "niet bereikbaar": controleer AI_MODEL (naam van de deployment), OPENAI_BASE_URL, de sleutel en het quotum van de Azure OpenAI-deployment.
