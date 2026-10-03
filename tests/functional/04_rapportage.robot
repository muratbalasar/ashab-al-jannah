*** Settings ***
Documentation       US04/US05/US06 - Rapportage per periode en per lid, met filters
...                 (zie 2-TestScenarios, Feature: Rapportage). Elk scenario filtert op
...                 een eigen lid, zodat de tests onafhankelijk zijn van andere data.
Resource            resources/api.resource
Suite Setup         Maak API-sessie
Test Tags           rapportage    backend


*** Test Cases ***
Rapportage filtert op inclusieve periode
    [Tags]    US04
    Given een lid heeft donaties op 31 januari 23:30, 1 februari 00:00 en 28 februari 23:59
    When de penningmeester de periode "2026-02-01" tot en met "2026-02-28" kiest voor dat lid
    Then bevat de rapportage 2 donaties met een totaal van "80.00"
    And tellen de uitsplitsingen per categorie en per maand op tot het totaal

Rapportage per lid en periode
    [Tags]    US05
    Given twee leden hebben donaties in februari 2026
    When de penningmeester het eerste lid en februari 2026 selecteert
    Then bevat het overzicht alleen donaties van het eerste lid
    And is het totaal gelijk aan de som van de getoonde donaties

Rapportage filtert op categorie
    [Tags]    US06
    Given een lid heeft donaties in "Sadaka" en "Contributie"
    When de penningmeester filtert op categorie "Contributie"
    Then bevat de rapportage alleen donaties in categorie "Contributie"

Rapportage toont lege periode
    [Tags]    US04
    When de bestuurder een periode zonder donaties kiest
    Then is de rapportage leeg met totaal "0.00"

Einddatum voor begindatum wordt afgewezen
    [Tags]    US04
    When de bestuurder een einddatum vóór de begindatum kiest
    Then wordt het rapport afgewezen met een melding over de einddatum


*** Keywords ***
een lid heeft donaties op 31 januari 23:30, 1 februari 00:00 en 28 februari 23:59
    ${lid}=    Maak lid aan    Periode Lid
    Set Test Variable    ${LID}    ${lid}
    Registreer donatie    ${lid}[id]    10.00    datum=2026-01-31T23:30:00
    Registreer donatie    ${lid}[id]    50.00    datum=2026-02-01T00:00:00
    Registreer donatie    ${lid}[id]    30.00    Contributie    Maandelijks    datum=2026-02-28T23:59:00

de penningmeester de periode "${start}" tot en met "${eind}" kiest voor dat lid
    ${resp}=    Haal rapport op    start_date=${start}    end_date=${eind}    member_id=${LID}[id]
    Set Test Variable    ${RAPPORT}    ${resp.json()}

bevat de rapportage ${aantal} donaties met een totaal van "${totaal}"
    Should Be Equal As Integers    ${RAPPORT}[count]    ${aantal}
    Should Be Equal    ${RAPPORT}[total]    ${totaal}

tellen de uitsplitsingen per categorie en per maand op tot het totaal
    FOR    ${uitsplitsing}    IN    by_category    by_month
        ${som}=    Evaluate    sum(decimal.Decimal(b['total']) for b in $RAPPORT['${uitsplitsing}'])
        ...    modules=decimal
        Should Be Equal As Numbers    ${som}    ${RAPPORT}[total]
    END
    Should Be Equal    ${RAPPORT}[by_month][0][key]    2026-02

twee leden hebben donaties in februari 2026
    ${eerste}=    Maak lid aan    Eerste Lid
    ${tweede}=    Maak lid aan    Tweede Lid
    Set Test Variable    ${LID}    ${eerste}
    Registreer donatie    ${eerste}[id]    20.00    datum=2026-02-10T12:00:00
    Registreer donatie    ${eerste}[id]    5.25    datum=2026-02-11T12:00:00
    Registreer donatie    ${tweede}[id]    99.00    datum=2026-02-10T12:00:00

de penningmeester het eerste lid en februari 2026 selecteert
    ${resp}=    GET On Session    api    ${API}/reports/members/${LID}[id]
    ...    params=start_date=2026-02-01&end_date=2026-02-28    headers=${PENNINGMEESTER}
    Set Test Variable    ${RAPPORT}    ${resp.json()}

bevat het overzicht alleen donaties van het eerste lid
    Length Should Be    ${RAPPORT}[donations]    2
    FOR    ${donatie}    IN    @{RAPPORT}[donations]
        Should Be Equal As Integers    ${donatie}[member_id]    ${LID}[id]
    END

is het totaal gelijk aan de som van de getoonde donaties
    ${som}=    Evaluate    sum(decimal.Decimal(d['amount']) for d in $RAPPORT['donations'])
    ...    modules=decimal
    Should Be Equal As Numbers    ${som}    ${RAPPORT}[total]
    Should Be Equal    ${RAPPORT}[total]    25.25

een lid heeft donaties in "${eerste}" en "${tweede}"
    ${lid}=    Maak lid aan    Categorie Lid
    Set Test Variable    ${LID}    ${lid}
    Registreer donatie    ${lid}[id]    40.00    ${eerste}    Waterput
    Registreer donatie    ${lid}[id]    12.00    ${tweede}    Jaarlijks

de penningmeester filtert op categorie "${categorie}"
    ${categorie_id}=    Categorie-id van    ${categorie}
    ${rapport}=    Haal rapport op    member_id=${LID}[id]    category_id=${categorie_id}
    Set Test Variable    ${RAPPORT}    ${rapport.json()}

bevat de rapportage alleen donaties in categorie "${categorie}"
    Should Be Equal    ${RAPPORT}[total]    12.00
    FOR    ${donatie}    IN    @{RAPPORT}[donations]
        Should Be Equal    ${donatie}[category]    ${categorie}
    END

de bestuurder een periode zonder donaties kiest
    ${resp}=    Haal rapport op    ${BESTUURDER}    start_date=1990-01-01    end_date=1990-12-31
    Set Test Variable    ${RAPPORT}    ${resp.json()}

is de rapportage leeg met totaal "${totaal}"
    Should Be Equal As Integers    ${RAPPORT}[count]    0
    Should Be Equal    ${RAPPORT}[total]    ${totaal}
    Should Be Empty    ${RAPPORT}[by_category]

de bestuurder een einddatum vóór de begindatum kiest
    ${resp}=    Haal rapport op    ${BESTUURDER}    422    start_date=2026-02-02    end_date=2026-02-01
    Set Test Variable    ${RESP}    ${resp}

wordt het rapport afgewezen met een melding over de einddatum
    Should Contain    ${RESP.text}    einddatum
