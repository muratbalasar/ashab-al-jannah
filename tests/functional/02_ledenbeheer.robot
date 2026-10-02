*** Settings ***
Documentation       US01 - Leden beheren (zie 2-TestScenarios, Feature: Leden beheren)
Resource            resources/api.resource
Suite Setup         Maak API-sessie
Test Tags           US01    ledenbeheer    backend


*** Test Cases ***
Beheerder maakt een lid aan
    Given de beheerder is aangemeld
    When de beheerder een lid opslaat met naam "Jan Jansen" en een uniek e-mailadres
    Then bestaat het lid met een uniek ID en de status "actief"
    And is het lid terug te vinden in de ledenlijst

Dubbel e-mailadres wordt afgewezen
    Given er bestaat een lid met een uniek e-mailadres
    When de beheerder een ander lid probeert op te slaan met hetzelfde e-mailadres in hoofdletters
    Then wordt het lid niet aangemaakt omdat het e-mailadres al in gebruik is

Lid inactief maken behoudt de historie
    Given een lid heeft een geregistreerde donatie
    When de beheerder het lid op inactief zet
    Then staat het lid als "inactief" in de ledenadministratie
    And blijft de bestaande donatie gekoppeld aan het lid


*** Keywords ***
de beheerder is aangemeld
    ${resp}=    GET On Session    api    ${API}/me    headers=${BEHEERDER}    expected_status=200
    List Should Contain Value    ${resp.json()}[permissions]    members:write

de beheerder een lid opslaat met naam "${naam}" en een uniek e-mailadres
    ${lid}=    Maak lid aan    ${naam}
    Set Test Variable    ${LID}    ${lid}

bestaat het lid met een uniek ID en de status "${status}"
    Should Be True    ${LID}[id] > 0
    Should Be Equal    ${LID}[status]    ${status}

is het lid terug te vinden in de ledenlijst
    ${params}=    Create Dictionary    q=${LID}[email]
    ${resp}=    GET On Session    api    ${API}/members    params=${params}    headers=${BEHEERDER}
    Length Should Be    ${resp.json()}    1
    Should Be Equal As Integers    ${resp.json()}[0][id]    ${LID}[id]

er bestaat een lid met een uniek e-mailadres
    ${lid}=    Maak lid aan    Bestaand Lid
    Set Test Variable    ${LID}    ${lid}

de beheerder een ander lid probeert op te slaan met hetzelfde e-mailadres in hoofdletters
    ${email}=    Convert To Upper Case    ${LID}[email]
    ${body}=    Create Dictionary    name=Ander Lid    email=${email}
    ${resp}=    POST On Session    api    ${API}/members    json=${body}    headers=${BEHEERDER}
    ...    expected_status=anything
    Set Test Variable    ${RESP}    ${resp}

wordt het lid niet aangemaakt omdat het e-mailadres al in gebruik is
    Should Be Equal As Integers    ${RESP.status_code}    409
    Should Contain    ${RESP.json()}[detail]    al in gebruik

een lid heeft een geregistreerde donatie
    ${lid}=    Maak lid aan    Historie Lid
    Set Test Variable    ${LID}    ${lid}
    Registreer donatie    ${lid}[id]    15.00

de beheerder het lid op inactief zet
    ${body}=    Create Dictionary    status=inactief
    PATCH On Session    api    ${API}/members/${LID}[id]    json=${body}    headers=${BEHEERDER}
    ...    expected_status=200

staat het lid als "${status}" in de ledenadministratie
    ${resp}=    GET On Session    api    ${API}/members/${LID}[id]    headers=${BEHEERDER}
    Should Be Equal    ${resp.json()}[status]    ${status}

blijft de bestaande donatie gekoppeld aan het lid
    ${resp}=    GET On Session    api    ${API}/members/${LID}[id]/donations    headers=${BEHEERDER}
    Length Should Be    ${resp.json()}    1
    Should Be Equal    ${resp.json()}[0][amount]    15.00
