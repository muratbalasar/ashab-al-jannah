Rollen en rechten (per stichting; een gebruiker kan meerdere rollen hebben):
- Beheerder: alles, ook gebruikers, categorieën, ledenvelden, logboek, instellingen, donaties bewerken en verwijderen.
- Penningmeester: leden inzien, donaties inzien en registreren, rapportage (ook per lid), AI-analyse, CSV-export.
- Bestuurder: rapportage zonder uitsplitsing per lid en zonder losse donaties, AI-analyse.
- Lid: alleen de eigen gegevens, donaties en het jaaroverzicht op Mijn omgeving, en online doneren.
- Rollen geven of wijzigen doet de beheerder bij Gebruikers. Er blijft altijd minstens één beheerder.

Stichtingen (organisaties):
- Een nieuwe stichting aanmelden: ga naar het adres /aanmelden (of de knop Nieuwe stichting aanmaken op de startpagina). Vul KVK-nummer (8 cijfers, uniek), naam, plaats en contact-e-mail in. De aanmelder wordt beheerder.
- Per gebruiker maximaal 3 stichtingen aanmaken, en hoogstens één per 24 uur.
- Heeft een gebruiker een rol in meer stichtingen, dan kiest hij op de startpagina welke hij opent. De gegevens van stichtingen zijn volledig gescheiden.
- Bestaat het KVK-nummer al, vraag dan de beheerder van die stichting om een uitnodiging.

Uitnodigen:
- De beheerder nodigt uit via Gebruikers > Uitnodigen met e-mailadres en rol. Voor de rol lid koppelt hij ook het lidrecord.
- De uitnodigingslink is 7 dagen geldig en één keer te gebruiken. De ontvanger moet inloggen met hetzelfde e-mailadres.
- Wordt de uitnodiging niet gemaild (e-mail niet ingesteld), dan kopieert de beheerder de link en stuurt hem zelf.

Leden:
- Een lid heeft een naam, een uniek e-mailadres binnen de stichting en de status actief of inactief.
- Zoeken op naam en e-mail en filteren op status gaat direct tijdens het typen.
- Inactief maken verwijdert niets: de donatiegeschiedenis blijft bewaard. Verwijderen (alleen beheerder) verwijdert het lid samen met zijn donaties.
- Ledenvelden (alleen beheerder): eigen velden van het type tekst, nummer, mobiel nummer, IBAN, ja/nee of datum en tijd. IBAN wordt gecontroleerd op het controlegetal. Deactiveren verbergt een veld en bewaart de waarden; verwijderen wist het veld en alle waarden.
- Gevoelige velden zijn om privacyredenen (AVG) niet toegestaan, zoals BSN, ID-bewijs, wachtwoord, gezondheid, geloof, afkomst, politiek, vakbond, strafrecht of biometrie. Waarden die op een BSN lijken worden geweigerd.

Donaties:
- Een donatie heeft een lid, een subcategorie (en daarmee een categorie), een bedrag, een datum en tijd (standaard nu) en een optionele omschrijving.
- Het bedrag is groter dan 0 met hoogstens 2 decimalen; Nederlandse notatie zoals € 1.234,50 mag.
- Een datum in de toekomst wordt geweigerd. Voor inactieve leden zijn nieuwe donaties standaard niet toegestaan.
- Bewerken kan alleen de beheerder, via het potlood achter een donatie. Elke wijziging wordt met oude en nieuwe waarde bewaard in de wijzigingsgeschiedenis. Bij een online betaling liggen lid, bedrag en datum vast. Bij een donatie uit een voorbij jaar waarschuwt de app dat eerder verstuurde overzichten niet meer kloppen.
- Online betaalde donaties worden automatisch geboekt; voer ze niet nog eens handmatig in.

Categorieën (alleen beheerder):
- Categorieën met subcategorieën zijn de doelen van donaties. Namen zijn uniek en hoogstens 100 tekens.
- Alleen actieve subcategorieën zijn te kiezen bij nieuwe donaties en online doneren. Inactieve blijven zichtbaar in rapportages.
- Verwijderen kan alleen zolang er geen donaties op staan; anders inactief maken. Hernoemen geldt ook voor bestaande donaties.
- Een nieuwe stichting krijgt standaard: Contributie (Jaarlijks, Maandelijks), Donatie (Algemeen, Project) en Sponsoring (MKB, Particulier).

Rapportage:
- Filters: begin- en einddatum (beide inclusief), lid, categorie en subcategorie. Standaard dit kalenderjaar tot vandaag.
- Totaal, aantal en gemiddelde, uitgesplitst per categorie, subcategorie, maand en lid, met grafieken. Tabellen en grafieken gebruiken dezelfde selectie.
- CSV-export opent goed in Excel (puntkomma als scheiding, komma als decimaalteken).
- AI-analyse: start u zelf met de knop AI Analyse; die volgt de actieve filters en gebruikt alleen totalen, nooit namen of e-mailadressen. Het is geen financieel advies.

Mijn omgeving en online doneren (rol lid):
- Het lid ziet zijn eigen gegevens, donaties en een jaaroverzicht per categorie, bijvoorbeeld voor de belastingaangifte.
- Online doneren kan als de beheerder Mollie heeft gekoppeld bij Instellingen: kies een doel en een bedrag tussen € 1 en € 10.000 en betaal met iDEAL. Het geld gaat rechtstreeks naar de stichting.
- Staat er "nog niet gekoppeld", dan moet de beheerder het account nog aan het lidrecord koppelen.

Logboek (alleen beheerder):
- Het logboek toont aanmeldingen, weergaven, klikken, wijzigingen, verwijderingen en fouten, met gebruiker en tijdstip, en is te filteren op gebruiker en actie.
- Regels ouder dan 41 dagen worden automatisch verwijderd.

Instellingen, export en verwijderen (alleen beheerder):
- Mollie koppelen met de Live API-sleutel (begint met live_); eerst proberen kan met een test_-sleutel.
- Export: alle gegevens van de stichting als ZIP-bestand met JSON en CSV.
- Stichting verwijderen: direct onbereikbaar; binnen 30 dagen kan de platformbeheerder haar herstellen, daarna wordt alles definitief gewist. Maak vooraf een export.

De assistent zelf:
- Beantwoordt alleen vragen over het gebruik en de werking van de app, op basis van de handleiding.
- Heeft geen toegang tot gegevens van leden, donaties of de stichting en kan niets wijzigen.
- Er geldt een maximum aantal vragen per dag; het resterende aantal staat bij de vraag.
