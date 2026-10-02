*** Settings ***
Documentation       US07 - AI-inzicht opvragen (zie 2-TestScenarios, Feature: AI-inzicht)
Resource            resources/api.resource
Suite Setup         Maak API-sessie
Test Tags           US07    ai    backend


*** Test Cases ***
AI analyse volgt de rapportagefilters
    Given een lid heeft donaties in maart 1999
    When de bestuurder "AI Analyse" kiest voor maart 1999
    Then benoemt de analyse de periode "01-03-1999 t/m 31-03-1999"
    And bevat de analyse het totaal van de selectie
    And bevat de analyse geen namen of e-mailadressen

AI analyse meldt ontbrekende gegevens
    When de bestuurder "AI Analyse" kiest voor een periode zonder donaties
    Then meldt de applicatie dat er onvoldoende gegevens zijn


*** Keywords ***
een lid heeft donaties in maart 1999
    ${lid}=    Maak lid aan    Privacy Gevoelig
    Set Test Variable    ${LID}    ${lid}
    Registreer donatie    ${lid}[id]    17.00    datum=1999-03-10T10:00:00

de bestuurder "AI Analyse" kiest voor maart 1999
    ${body}=    Create Dictionary    start_date=1999-03-01    end_date=1999-03-31
    ${resp}=    POST On Session    api    ${API}/insights    json=${body}    headers=${BESTUURDER}
    ...    expected_status=200
    Set Test Variable    ${INZICHT}    ${resp.json()}

benoemt de analyse de periode "${periode}"
    Should Be Equal    ${INZICHT}[period]    ${periode}

bevat de analyse het totaal van de selectie
    Should Contain    ${INZICHT}[text]    17,00

bevat de analyse geen namen of e-mailadressen
    Should Not Contain    ${INZICHT}[text]    ${LID}[name]
    Should Not Contain    ${INZICHT}[text]    ${LID}[email]

de bestuurder "AI Analyse" kiest voor een periode zonder donaties
    ${body}=    Create Dictionary    start_date=1980-01-01    end_date=1980-01-31
    ${resp}=    POST On Session    api    ${API}/insights    json=${body}    headers=${BESTUURDER}
    Set Test Variable    ${INZICHT}    ${resp.json()}

meldt de applicatie dat er onvoldoende gegevens zijn
    Should Start With    ${INZICHT}[text]    Onvoldoende gegevens
