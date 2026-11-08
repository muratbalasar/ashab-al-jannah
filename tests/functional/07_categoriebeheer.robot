*** Settings ***
Documentation       US02 (aanvulling) - Categorieën beheren (zie 2-TestScenarios, Feature: Categorieën beheren)
Resource            resources/api.resource
Suite Setup         Maak API-sessie
Test Tags           US02    categoriebeheer    backend


*** Test Cases ***
Beheerder maakt een categorie met subcategorie aan
    When de beheerder een categorie "Testfonds" met subcategorie "Testdoel" aanmaakt
    Then bestaat de categorie "Testfonds" met subcategorie "Testdoel"
    And staan de categorie en subcategorie op "actief"

Dubbele categorienaam wordt geweigerd
    Given er bestaat een categorie "Dubbele Categorie"
    When de beheerder nogmaals een categorie "Dubbele Categorie" probeert aan te maken
    Then wordt de categorie geweigerd met de melding "bestaat al"

Dubbele subcategorienaam binnen dezelfde categorie wordt geweigerd
    Given er bestaat een categorie "Unieke Categorie" met subcategorie "Unieke Sub"
    When de beheerder nogmaals een subcategorie "Unieke Sub" in diezelfde categorie probeert aan te maken
    Then wordt de subcategorie geweigerd met de melding "bestaat al"

Subcategorie hernoemen
    Given er bestaat een categorie "Hernoem Categorie" met subcategorie "Oude Naam"
    When de beheerder de subcategorie hernoemt naar "Nieuwe Naam"
    Then heet de subcategorie "Nieuwe Naam"

Gedeactiveerde subcategorie kan niet meer gebruikt worden bij nieuwe donaties
    Given lid "Jan Jansen" bestaat
    And er bestaat een categorie "Deactivatie Categorie" met subcategorie "Deactivatie Sub"
    When de beheerder de subcategorie deactiveert
    And de penningmeester een donatie probeert te registreren in die subcategorie
    Then wordt de donatie afgewezen met de melding "Kies een geldige categorie en subcategorie"

Subcategorie die al gebruikt is bij een donatie kan niet verwijderd worden
    Given lid "Jan Jansen" bestaat
    And er bestaat een categorie "Verwijder Categorie" met subcategorie "Verwijder Sub"
    And de penningmeester registreert een donatie in die subcategorie
    When de beheerder de subcategorie probeert te verwijderen
    Then wordt het verwijderen geweigerd met de melding "al gebruikt bij donaties"
    And bestaat de subcategorie nog steeds

Ongebruikte subcategorie kan worden verwijderd
    Given er bestaat een categorie "Opruim Categorie" met subcategorie "Opruim Sub"
    When de beheerder de subcategorie verwijdert
    Then bestaat de subcategorie niet meer


*** Keywords ***
lid "${naam}" bestaat
    ${lid}=    Maak lid aan    ${naam}
    Set Test Variable    ${LID}    ${lid}

de beheerder een categorie "${naam}" met subcategorie "${sub_naam}" aanmaakt
    er bestaat een categorie "${naam}" met subcategorie "${sub_naam}"

bestaat de categorie "${naam}" met subcategorie "${sub_naam}"
    Should Be Equal    ${CATEGORIE}[name]    ${naam}
    Should Be Equal    ${SUBCATEGORIE}[name]    ${sub_naam}

staan de categorie en subcategorie op "actief"
    Should Be True    ${CATEGORIE}[is_active]
    Should Be True    ${SUBCATEGORIE}[is_active]

er bestaat een categorie "${naam}"
    ${categorie}=    Maak categorie aan    ${naam}
    Set Test Variable    ${CATEGORIE}    ${categorie}

de beheerder nogmaals een categorie "${naam}" probeert aan te maken
    ${body}=    Create Dictionary    name=${naam}
    ${resp}=    POST On Session    api    ${API}/categories    json=${body}    headers=${BEHEERDER}
    ...    expected_status=anything
    Set Test Variable    ${RESP}    ${resp}

wordt de categorie geweigerd met de melding "${tekst}"
    Should Be Equal As Integers    ${RESP.status_code}    409
    Should Contain    ${RESP.json()}[detail]    ${tekst}

er bestaat een categorie "${naam}" met subcategorie "${sub_naam}"
    ${categorie}=    Maak categorie aan    ${naam}
    ${subcategorie}=    Maak subcategorie aan    ${categorie}[id]    ${sub_naam}
    Set Test Variable    ${CATEGORIE}    ${categorie}
    Set Test Variable    ${SUBCATEGORIE}    ${subcategorie}

de beheerder nogmaals een subcategorie "${naam}" in diezelfde categorie probeert aan te maken
    ${body}=    Create Dictionary    name=${naam}
    ${resp}=    POST On Session    api    ${API}/categories/${CATEGORIE}[id]/subcategories    json=${body}
    ...    headers=${BEHEERDER}    expected_status=anything
    Set Test Variable    ${RESP}    ${resp}

wordt de subcategorie geweigerd met de melding "${tekst}"
    Should Be Equal As Integers    ${RESP.status_code}    409
    Should Contain    ${RESP.json()}[detail]    ${tekst}

de beheerder de subcategorie hernoemt naar "${naam}"
    ${body}=    Create Dictionary    name=${naam}
    ${resp}=    PATCH On Session    api
    ...    ${API}/categories/${CATEGORIE}[id]/subcategories/${SUBCATEGORIE}[id]
    ...    json=${body}    headers=${BEHEERDER}    expected_status=200
    Set Test Variable    ${SUBCATEGORIE}    ${resp.json()}

heet de subcategorie "${naam}"
    Should Be Equal    ${SUBCATEGORIE}[name]    ${naam}

de beheerder de subcategorie deactiveert
    ${body}=    Create Dictionary    is_active=${False}
    ${resp}=    PATCH On Session    api
    ...    ${API}/categories/${CATEGORIE}[id]/subcategories/${SUBCATEGORIE}[id]
    ...    json=${body}    headers=${BEHEERDER}    expected_status=200
    Set Test Variable    ${SUBCATEGORIE}    ${resp.json()}

de penningmeester een donatie probeert te registreren in die subcategorie
    ${body}=    Create Dictionary    member_id=${LID}[id]    subcategory_id=${SUBCATEGORIE}[id]    amount=10.00
    ${resp}=    POST On Session    api    ${API}/donations    json=${body}    headers=${PENNINGMEESTER}
    ...    expected_status=anything
    Set Test Variable    ${RESP}    ${resp}

wordt de donatie afgewezen met de melding "${tekst}"
    Should Be Equal As Integers    ${RESP.status_code}    422
    Should Contain    ${RESP.json()}[detail]    ${tekst}

de penningmeester registreert een donatie in die subcategorie
    ${body}=    Create Dictionary    member_id=${LID}[id]    subcategory_id=${SUBCATEGORIE}[id]    amount=10.00
    POST On Session    api    ${API}/donations    json=${body}    headers=${PENNINGMEESTER}
    ...    expected_status=201

de beheerder de subcategorie probeert te verwijderen
    ${resp}=    DELETE On Session    api
    ...    ${API}/categories/${CATEGORIE}[id]/subcategories/${SUBCATEGORIE}[id]
    ...    headers=${BEHEERDER}    expected_status=anything
    Set Test Variable    ${RESP}    ${resp}

wordt het verwijderen geweigerd met de melding "${tekst}"
    Should Be Equal As Integers    ${RESP.status_code}    409
    Should Contain    ${RESP.json()}[detail]    ${tekst}

bestaat de subcategorie nog steeds
    ${sub}=    Haal subcategorie op    ${CATEGORIE}[id]    ${SUBCATEGORIE}[id]
    Should Not Be Equal    ${sub}    ${NONE}

de beheerder de subcategorie verwijdert
    DELETE On Session    api
    ...    ${API}/categories/${CATEGORIE}[id]/subcategories/${SUBCATEGORIE}[id]
    ...    headers=${BEHEERDER}    expected_status=204

bestaat de subcategorie niet meer
    ${sub}=    Haal subcategorie op    ${CATEGORIE}[id]    ${SUBCATEGORIE}[id]
    Should Be Equal    ${sub}    ${NONE}

Haal subcategorie op
    [Arguments]    ${categorie_id}    ${subcategorie_id}
    ${params}=    Create Dictionary    include_inactive=true
    ${resp}=    GET On Session    api    ${API}/categories    params=${params}
    ...    headers=${BEHEERDER}    expected_status=200
    FOR    ${cat}    IN    @{resp.json()}
        IF    $cat['id'] == $categorie_id
            FOR    ${sub}    IN    @{cat['subcategories']}
                IF    $sub['id'] == $subcategorie_id    RETURN    ${sub}
            END
        END
    END
    RETURN    ${NONE}
