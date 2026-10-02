# start.ps1
# Start Ashab al-Jannah lokaal met een SQLite-database en ontwikkel-authenticatie.
# Gebruik: .\start.ps1 [-Port 8000] [-Install] [-ResetDatabase] [-InitWithDummyData]
#   -ResetDatabase      verwijdert de lokale SQLite-database en begint met een lege database
#   -InitWithDummyData  voegt 10 dummy leden met donaties toe (wordt overgeslagen als ze al bestaan)

param(
    [int]$Port = 8000,
    [switch]$Install,
    [switch]$ResetDatabase,
    [switch]$InitWithDummyData
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    py -3.12 -m venv .venv 2>$null
    if ($LASTEXITCODE -ne 0) { python -m venv .venv }
    $Install = $true
}
$python = ".venv\Scripts\python.exe"

if ($Install) {
    & $python -m pip install --upgrade pip
    & $python -m pip install -r requirements-dev.txt
    & $python -m pip install -e . --no-deps
}

if (-not $env:AUTH_MODE) { $env:AUTH_MODE = "dev" }
if (-not $env:DATABASE_URL) { $env:DATABASE_URL = "sqlite:///./ledenadmin.db" }

if ($ResetDatabase) {
    if ($env:DATABASE_URL -notmatch '^sqlite(\+pysqlite)?:///(.+)$') {
        throw "-ResetDatabase werkt alleen met een lokale SQLite-database (DATABASE_URL=$env:DATABASE_URL)"
    }
    $dbFile = $Matches[2]
    if (Test-Path $dbFile) {
        try {
            Remove-Item $dbFile -ErrorAction Stop
        } catch {
            throw "Kan $dbFile niet verwijderen. Draait de app nog? Stop die eerst."
        }
        Write-Host "Database $dbFile verwijderd." -ForegroundColor Yellow
    }
}

& $python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw "Databasemigratie mislukt" }

if ($InitWithDummyData) {
    $env:PYTHONUTF8 = "1"
    & $python -m ledenadmin.dummy_data
    if ($LASTEXITCODE -ne 0) { throw "Dummy data toevoegen mislukt" }
}

Write-Host "Ashab al-Jannah: http://127.0.0.1:$Port  (API-docs: /api/docs)" -ForegroundColor Green
& $python -m uvicorn --factory ledenadmin.main:create_app --reload --port $Port
