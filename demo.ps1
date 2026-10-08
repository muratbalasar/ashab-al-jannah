# demo.ps1
# Geautomatiseerde rondleiding met Playwright: een nieuwe stichting aanmelden, leden en
# donaties registreren en een penningmeester uitnodigen. Draait tegen een verse demo-database.
# Gebruik: .\demo.ps1 [-Pauze 2] [-Port 8770] [-Browser msedge|chrome|chromium] [-Platform] [-Headless]
#   -Pauze     seconden tussen de UI-acties (standaard 1,5)
#   -Platform  toont aan het eind ook /platform als superadmin
#   -Headless  zonder zichtbaar browservenster (bijv. om te controleren of de demo werkt)

param(
    [double]$Pauze = 1.5,
    [int]$Port = 8770,
    [string]$Browser = "msedge",
    [switch]$Platform,
    [switch]$Headless
)

$ErrorActionPreference = "Continue"  # stderr van alembic/pip mag het script niet afbreken
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Geen .venv gevonden. Voer eerst .\start.ps1 -Install uit." }

& $python -c "import playwright" 2>$null
if ($LASTEXITCODE -ne 0) {
    & $python -m pip install -r requirements-demo.txt
    if ($LASTEXITCODE -ne 0) { throw "Playwright installeren mislukt" }
}
if ($Browser -eq "chromium") {
    & $python -m playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw "Chromium installeren mislukt" }
}

# Eigen map en database, zodat ledenadmin.db en een eventuele .env niet worden gebruikt
# (de server leest .env uit de werkmap; zo gaan er geen echte e-mails of KVK-verzoeken uit).
$demoDir = Join-Path $PSScriptRoot "output\demo"
New-Item -ItemType Directory -Force -Path $demoDir | Out-Null
$db = Join-Path $demoDir "demo.db"
Get-ChildItem $demoDir -Filter "demo.db*" | Remove-Item -ErrorAction SilentlyContinue
if (Test-Path $db) { throw "Kan $db niet verwijderen. Draait er nog een demo? Stop die eerst." }

$baseUrl = "http://127.0.0.1:$Port"
$env:DATABASE_URL = "sqlite:///$($db -replace '\\', '/')"
$env:AUTH_MODE = "dev"
$env:PUBLIC_BASE_URL = $baseUrl
$env:SUPERADMIN_SUBJECTS = "dev|platformeigenaar"
$env:PYTHONUTF8 = "1"

& $python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw "Databasemigratie mislukt" }

$server = Start-Process -FilePath $python -PassThru -WindowStyle Hidden -WorkingDirectory $demoDir `
    -ArgumentList "-m", "uvicorn", "--factory", "ledenadmin.main:create_app", "--port", "$Port" `
    -RedirectStandardOutput "$demoDir\server.log" -RedirectStandardError "$demoDir\server-fouten.log"

try {
    $klaar = $false
    for ($i = 0; $i -lt 40 -and -not $klaar; $i++) {
        Start-Sleep -Milliseconds 500
        if ($server.HasExited) { throw "Server gestopt; zie $demoDir\server-fouten.log" }
        try {
            Invoke-WebRequest "$baseUrl/api/v1/health" -UseBasicParsing -TimeoutSec 2 | Out-Null
            $klaar = $true
        } catch { }
    }
    if (-not $klaar) { throw "Server niet bereikbaar op $baseUrl; zie $demoDir\server-fouten.log" }

    Write-Host "Demo-server draait op $baseUrl" -ForegroundColor Green
    $demoArgs = @("demo\demo_playwright.py", "--base-url", $baseUrl, "--pauze", $Pauze.ToString([cultureinfo]::InvariantCulture), "--browser", $Browser)
    if ($Platform) { $demoArgs += "--platform" }
    if ($Headless) { $demoArgs += "--headless" }
    & $python @demoArgs
    $code = $LASTEXITCODE
} finally {
    Stop-Process -Id $server.Id -ErrorAction SilentlyContinue
}
exit $code
