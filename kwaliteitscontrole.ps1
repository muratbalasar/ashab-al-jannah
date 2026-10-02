# kwaliteitscontrole.ps1
# Voert lokaal dezelfde controles uit als de CI: black, isort, flake8, pytest + coverage.
# Gebruik: .\kwaliteitscontrole.ps1 [-Fix]
#   -Fix : past black en isort toe in plaats van alleen te controleren.

param(
    [switch]$Fix
)

Set-Location $PSScriptRoot

$python = ".venv\Scripts\python.exe"
$paden = @("src", "tests", "migrations")
$fouten = 0

function Stap {
    param([string]$Naam, [string[]]$Commando)
    Write-Host "`n=== $Naam ===" -ForegroundColor Cyan
    & $python @Commando
    if ($LASTEXITCODE -ne 0) {
        Write-Host "MISLUKT: $Naam" -ForegroundColor Red
        $script:fouten++
    } else {
        Write-Host "OK: $Naam" -ForegroundColor Green
    }
}

if ($Fix) {
    Stap "Black (formatteren)" (@("-m", "black") + $paden)
    Stap "isort (imports sorteren)" (@("-m", "isort") + $paden)
} else {
    Stap "Black (check)" (@("-m", "black", "--check") + $paden)
    Stap "isort (check)" (@("-m", "isort", "--check-only") + $paden)
}

Stap "Flake8" (@("-m", "flake8") + $paden)
Stap "Pytest + coverage" @("-m", "pytest", "--cov", "--cov-report=term-missing", "--cov-fail-under=90")

Write-Host ""
if ($fouten -eq 0) {
    Write-Host "Alle controles geslaagd." -ForegroundColor Green
    exit 0
} else {
    Write-Host "$fouten controle(s) mislukt." -ForegroundColor Red
    exit 1
}
