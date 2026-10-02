*** Settings ***
Documentation       US02 - Donaties registreren (zie 2-TestScenarios, Feature: Donaties registreren)
Resource            resources/api.resource
Suite Setup         Maak API-sessie
Test Tags           US02    donaties    backend


*** Test Cases ***
Donatie registreren met standaarddatum
    Given lid "Jan Jansen" bestaat
    When de penningmeester een donatie van 50.00 euro registreert in "Sponsoring" / "MKB"
    Then is precies één donatie geregistreerd voor dat lid
    And bevat de donatie het bedrag "50.00", categorie "Sponsoring" en subcategorie "MKB"
    And ligt het tijdstip rond het moment van opslaan

Donatie registreren met aangepaste datum
    Given lid "Jan Jansen" bestaat
    When de penningmeester een donatie van 25.00 euro registreert op "2026-02-14T10:30:00"
    Then is de donatie opgeslagen op "2026-02-14T09:30:00Z" (UTC)

Ongeldige donatie wordt niet opgeslagen
    Given lid "Jan Jansen" bestaat
    When de penningmeester een donatie met bedrag 0 probeert te registreren
    Then wordt de donatie afgewezen met een validatiemelding
    And heeft het lid geen donaties

Donatie voor een onbekend lid wordt afgewezen
    When de penningmeester een donatie registreert voor een lid dat niet bestaat
    Then wordt de donatie afgewezen met de melding "Kies een bestaand lid"


*** Keywords ***
lid "${naam}" bestaat
    ${lid}=    Maak lid aan    ${naam}
    Set Test Variable    ${LID}    ${lid}

de penningmeester een donatie van ${bedrag} euro registreert in "${categorie}" / "${subcategorie}"
    ${resp}=    Registreer donatie    ${LID}[id]    ${bedrag}    ${categorie}    ${subcategorie}
    Set Test Variable    ${DONATIE}    ${resp.json()}

is precies één donatie geregistreerd voor dat lid
    ${resp}=    GET On Session    api    ${API}/members/${LID}[id]/donations    headers=${PENNINGMEESTER}
    Length Should Be    ${resp.json()}    1

bevat de donatie het bedrag "${bedrag}", categorie "${categorie}" en subcategorie "${subcategorie}"
    Should Be Equal    ${DONATIE}[amount]    ${bedrag}
    Should Be Equal    ${DONATIE}[category]    ${categorie}
    Should Be Equal    ${DONATIE}[subcategory]    ${subcategorie}
    Should Be Equal    ${DONATIE}[created_by]    robot-penningmeester

ligt het tijdstip rond het moment van opslaan
    ${verschil}=    Evaluate
    ...    abs((datetime.datetime.now(datetime.UTC) - datetime.datetime.fromisoformat($DONATIE['donated_at'])).total_seconds())
    ...    modules=datetime
    Should Be True    ${verschil} < 120

de penningmeester een donatie van ${bedrag} euro registreert op "${datum}"
    ${resp}=    Registreer donatie    ${LID}[id]    ${bedrag}    Contributie    Jaarlijks    datum=${datum}
    Set Test Variable    ${DONATIE}    ${resp.json()}

is de donatie opgeslagen op "${utc}" (UTC)
    Should Be Equal    ${DONATIE}[donated_at]    ${utc}

de penningmeester een donatie met bedrag 0 probeert te registreren
    ${resp}=    Registreer donatie    ${LID}[id]    0    expected_status=422
    Set Test Variable    ${RESP}    ${resp}

wordt de donatie afgewezen met een validatiemelding
    Should Be Equal As Integers    ${RESP.status_code}    422
    Should Contain    ${RESP.text}    amount

heeft het lid geen donaties
    ${resp}=    GET On Session    api    ${API}/members/${LID}[id]/donations    headers=${PENNINGMEESTER}
    Should Be Empty    ${resp.json()}

de penningmeester een donatie registreert voor een lid dat niet bestaat
    ${resp}=    Registreer donatie    99999999    10.00    expected_status=422
    Set Test Variable    ${RESP}    ${resp}

wordt de donatie afgewezen met de melding "${melding}"
    Should Be Equal    ${RESP.json()}[detail]    ${melding}
