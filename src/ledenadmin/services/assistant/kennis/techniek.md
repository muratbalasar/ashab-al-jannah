Gebruik en apparaten:
- Ashab al-Jannah is een webapp: geen installatie, werkt in een actuele browser (Edge, Chrome, Firefox, Safari) op mobiel, tablet en laptop.
- Zoeken tijdens het typen en de grafieken hebben JavaScript nodig; dat staat in gewone browsers standaard aan.
- Na een tijd zonder gebruik kan de eerste pagina 30 tot 60 seconden laden, omdat de app dan opstart. Daarna is hij snel.
- Datums zijn in de vorm dd-mm-jjjj en tijden in de Nederlandse tijdzone. Bedragen zijn in euro.

Inloggen en sessie:
- Inloggen gaat via Microsoft Entra External ID: met uw e-mailadres en een eenmalige code per e-mail, of met een andere inlogmethode die het platform heeft ingesteld. De app zelf bewaart geen wachtwoorden.
- De eerste keer kiest u "Geen account? Maak er een". Komt de code niet aan, kijk dan in de map met ongewenste e-mail.
- Welke stichtingen en menu's u ziet, hangt af van uw rollen. Na inloggen zonder rol ziet u alleen de keuze om een stichting aan te melden.
- Afmelden: er is geen afmeldknop in de app; ga naar het adres /.auth/logout of sluit de browser.
- De melding "Je sessie is verlopen of ongeldig" verdwijnt als u de pagina ververst en het opnieuw probeert.

Fouten:
- Bij een onverwachte fout toont de app een foutcode zoals ERR-7F3K2Q. Geef die code door aan de beheerder van uw stichting; daarmee kan de fout worden opgezocht.
- "Organisatie niet gevonden" betekent: de stichting bestaat niet, is geblokkeerd, of u heeft er geen rol.

Gegevens, privacy en beveiliging:
- De gegevens staan in Microsoft Azure in West-Europa en worden continu (binnen ongeveer een seconde) geback-upt. Een eerdere stand terugzetten kan tot 7 dagen terug.
- Elke stichting ziet alleen haar eigen gegevens; ook de platformbeheerder ziet geen ledengegevens zonder rol in die stichting.
- Alle verbindingen zijn versleuteld (HTTPS). Mollie-sleutels worden versleuteld opgeslagen.
- Rechten worden op de server gecontroleerd; de app toont alleen wat uw rol mag.
- De AI-analyse stuurt alleen totalen naar de AI-dienst, nooit namen, e-mailadressen of omschrijvingen.
- De assistent stuurt alleen uw vraag en de handleiding naar de AI-dienst. E-mailadressen, IBAN's en lange nummers in de vraag worden eerst vervangen. Vragen en antwoorden worden niet opgeslagen, alleen geteld. Deel toch geen persoonsgegevens in een vraag.
- Gevoelige persoonsgegevens (zoals BSN of gezondheid) kunnen niet in ledenvelden worden opgeslagen.

Koppelingen en export:
- Online doneren loopt via Mollie (iDEAL); de app slaat geen bankgegevens van betalers op.
- E-mail (uitnodigingen) loopt via Brevo, als het platform dat heeft ingesteld.
- CSV-export: puntkomma als scheiding, komma als decimaalteken, UTF-8; waarden die met =, +, - of @ beginnen worden onschadelijk gemaakt voor Excel.
- Er is een REST API (/api/v1) met documentatie op /api/docs, voor wie is ingelogd.
