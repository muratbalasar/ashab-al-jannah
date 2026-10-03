*** Settings ***
Documentation       Gedeelde keywords voor de API-acceptatietests van de ledenadministratie.
...                 De server draait met AUTH_MODE=dev; rollen worden per request
...                 gezet via de header X-Dev-Roles.
Library             RequestsLibrary
Library             Collections
Library             String


*** Variables ***
${BASE_URL}             http://127.0.0.1:8000
${HEALTH_TIMEOUT}       60s
${API}                  /o/standaard/api/v1
&{BEHEERDER}            X-Dev-Roles=beheerder           X-Dev-User=robot-beheerder
&{PENNINGMEESTER}       X-Dev-Roles=penningmeester      X-Dev-User=robot-penningmeester
&{BESTUURDER}           X-Dev-Roles=bestuurder          X-Dev-User=robot-bestuurder


*** Keywords ***
Maak API-sessie
    Create Session    api    ${BASE_URL}    disable_warnings=1
    Wait Until Keyword Succeeds    ${HEALTH_TIMEOUT}    2s    GET On Session    api    /api/v1/health    expected_status=200

Unieke code
    ${code}=    Generate Random String    8    [LOWER][NUMBERS]
    RETURN    ${code}

Maak lid aan
    [Arguments]    ${naam}    ${email}=${EMPTY}
    IF    not $email
        ${code}=    Unieke code
        ${email}=    Set Variable    robot-${code}@example.nl
    END
    ${body}=    Create Dictionary    name=${naam}    email=${email}
    ${resp}=    POST On Session    api    ${API}/members    json=${body}    headers=${BEHEERDER}
    ...    expected_status=201
    RETURN    ${resp.json()}

Categorie-id van
    [Arguments]    ${categorie}
    ${resp}=    GET On Session    api    ${API}/categories    expected_status=200
    FOR    ${cat}    IN    @{resp.json()}
        IF    $cat['name'] == $categorie    RETURN    ${cat['id']}
    END
    Fail    Categorie ${categorie} bestaat niet

Subcategorie-id van
    [Arguments]    ${categorie}    ${subcategorie}
    ${resp}=    GET On Session    api    ${API}/categories    expected_status=200
    FOR    ${cat}    IN    @{resp.json()}
        IF    $cat['name'] == $categorie
            FOR    ${sub}    IN    @{cat['subcategories']}
                IF    $sub['name'] == $subcategorie    RETURN    ${sub['id']}
            END
        END
    END
    Fail    Subcategorie ${categorie} / ${subcategorie} bestaat niet

Registreer donatie
    [Arguments]    ${lid_id}    ${bedrag}    ${categorie}=Sadaka    ${subcategorie}=Waterput
    ...    ${datum}=${NONE}    ${expected_status}=201
    ${sub_id}=    Subcategorie-id van    ${categorie}    ${subcategorie}
    ${body}=    Create Dictionary    member_id=${lid_id}    subcategory_id=${sub_id}    amount=${bedrag}
    IF    $datum    Set To Dictionary    ${body}    donated_at=${datum}
    ${resp}=    POST On Session    api    ${API}/donations    json=${body}    headers=${PENNINGMEESTER}
    ...    expected_status=${expected_status}
    RETURN    ${resp}

Haal rapport op
    [Arguments]    ${headers}=${PENNINGMEESTER}    ${expected_status}=200    &{filters}
    ${resp}=    GET On Session    api    ${API}/reports/summary    params=${filters}    headers=${headers}
    ...    expected_status=${expected_status}
    RETURN    ${resp}
