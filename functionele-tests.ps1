# functionele-tests.ps1
# Start de API met een lege database en voert de Robot Framework-acceptatietests uit.
# Gebruik: .\functionele-tests.ps1 [-Port 8765] [-Include US02]

param(
    [int]$Port = 8765,
    [string]$Include = ""
)

Set-Location $PSScriptRoot
$python = ".venv\Scripts\python.exe"
$uitvoer = "output\robot-results"
New-Item -ItemType Directory -Force -Path $uitvoer | Out-Null

$db = "output\robot.db"
Remove-Item $db -ErrorAction SilentlyContinue
$env:DATABASE_URL = "sqlite:///./$($db -replace '\\', '/')"
$env:AUTH_MODE = "dev"

& $python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { Write-Host "Databasemigratie mislukt" -ForegroundColor Red; exit 1 }

$server = Start-Process -FilePath $python -PassThru -WindowStyle Hidden `
    -ArgumentList "-m", "uvicorn", "--factory", "ledenadmin.main:create_app", "--port", "$Port" `
    -RedirectStandardOutput "$uitvoer\server.log" -RedirectStandardError "$uitvoer\server-fouten.log"

try {
    $robotArgs = @("-m", "robot", "--outputdir", $uitvoer, "--variable", "BASE_URL:http://127.0.0.1:$Port")
    if ($Include) { $robotArgs += @("--include", $Include) }
    & $python @($robotArgs + "tests\functional")
    $code = $LASTEXITCODE
} finally {
    Stop-Process -Id $server.Id -ErrorAction SilentlyContinue
}
exit $code
