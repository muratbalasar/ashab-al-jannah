*** Settings ***
Documentation       Smoketest: de applicatie is bereikbaar. Ook bruikbaar tegen een Azure-omgeving.
Resource            resources/api.resource
Suite Setup         Maak API-sessie
Test Tags           smoke


*** Test Cases ***
De API is operationeel
    ${resp}=    GET On Session    api    /api/v1/health    expected_status=200
    Should Be Equal    ${resp.json()}[status]    healthy

De applicatie levert beveiligingsheaders
    ${resp}=    GET On Session    api    /api/v1/health
    Should Be Equal    ${resp.headers}[X-Content-Type-Options]    nosniff
    Should Contain    ${resp.headers}[Content-Security-Policy]    default-src 'self'
