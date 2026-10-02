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

Beheerder kan geen donaties registreren
    When de beheerder een donatie probeert te registreren
    Then wordt de toegang geweigerd

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

de beheerder een donatie probeert te registreren
    ${body}=    Create Dictionary    member_id=1    subcategory_id=1    amount=5
    ${resp}=    POST On Session    api    ${API}/donations    json=${body}    headers=${BEHEERDER}
    ...    expected_status=anything
    Set Test Variable    ${RESP}    ${resp}

een formulier zonder CSRF-token wordt verstuurd
    ${form}=    Create Dictionary    name=Zonder Token    email=geen-token@example.nl
    ${resp}=    POST On Session    api    /leden    data=${form}    headers=${BEHEERDER}
    ...    expected_status=anything
    Set Test Variable    ${RESP}    ${resp}
