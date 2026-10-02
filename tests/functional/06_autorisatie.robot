*** Settings ***
Documentation       US08 - Gegevens veilig beheren (zie 2-TestScenarios, Feature: Autorisatie)
Resource            resources/api.resource
Suite Setup         Maak API-sessie
Test Tags           US08    autorisatie    backend


*** Test Cases ***
Bestuurder ziet totalen maar geen persoonsgegevens
    Given er is een donatie geregistreerd
    When de bestuurder de rapportage opvraagt
    Then ziet de bestuurder het totaal
    And bevat de rapportage geen uitsplitsing per lid of losse donaties

Bestuurder heeft geen toegang tot de ledenadministratie
    When de bestuurder de ledenlijst opvraagt
    Then wordt de toegang geweigerd

Penningmeester kan geen categorieën beheren
    When de penningmeester een categorie probeert aan te maken
    Then wordt de toegang geweigerd

Beheerder mag alles
    When de beheerder een donatie registreert
    Then is de donatie opgeslagen
    And kan de beheerder de CSV-export downloaden

Wijzigingen via de web-UI vereisen een CSRF-token
    When een formulier zonder CSRF-token wordt verstuurd
    Then wordt de toegang geweigerd


*** Keywords ***
er is een donatie geregistreerd
    ${lid}=    Maak lid aan    Autorisatie Lid
    Registreer donatie    ${lid}[id]    11.00

de bestuurder de rapportage opvraagt
    ${resp}=    Haal rapport op    ${BESTUURDER}
    Set Test Variable    ${RAPPORT}    ${resp.json()}

ziet de bestuurder het totaal
    Should Be True    ${RAPPORT}[count] >= 1

bevat de rapportage geen uitsplitsing per lid of losse donaties
    Should Be Empty    ${RAPPORT}[by_member]
    Should Be Empty    ${RAPPORT}[donations]
    Should Not Be True    ${RAPPORT}[includes_member_details]

de bestuurder de ledenlijst opvraagt
    ${resp}=    GET On Session    api    ${API}/members    headers=${BESTUURDER}    expected_status=anything
    Set Test Variable    ${RESP}    ${resp}

wordt de toegang geweigerd
    Should Be Equal As Integers    ${RESP.status_code}    403

de penningmeester een categorie probeert aan te maken
    ${body}=    Create Dictionary    name=Niet Toegestaan
    ${resp}=    POST On Session    api    ${API}/categories    json=${body}    headers=${PENNINGMEESTER}
    ...    expected_status=anything
    Set Test Variable    ${RESP}    ${resp}

de beheerder een donatie registreert
    ${lid}=    Maak lid aan    Beheerder Lid
    ${sub_id}=    Subcategorie-id van    Sponsoring    MKB
    ${body}=    Create Dictionary    member_id=${lid}[id]    subcategory_id=${sub_id}    amount=7.50
    ${resp}=    POST On Session    api    ${API}/donations    json=${body}    headers=${BEHEERDER}
    ...    expected_status=anything
    Set Test Variable    ${RESP}    ${resp}

is de donatie opgeslagen
    Should Be Equal As Integers    ${RESP.status_code}    201

kan de beheerder de CSV-export downloaden
    GET On Session    api    ${API}/reports/export.csv    headers=${BEHEERDER}    expected_status=200

een formulier zonder CSRF-token wordt verstuurd
    ${form}=    Create Dictionary    name=Zonder Token    email=geen-token@example.nl
    ${resp}=    POST On Session    api    /leden    data=${form}    headers=${BEHEERDER}
    ...    expected_status=anything
    Set Test Variable    ${RESP}    ${resp}
