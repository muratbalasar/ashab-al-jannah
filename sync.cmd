@echo off
:: ============================================================
:: sync.cmd
:: Gebruik: sync.cmd "commit bericht"
::          Leest GitHub PAT uit __git-token.txt (gitignored)
:: ============================================================

if "%~1"=="" (
    echo Gebruik: sync.cmd "commit bericht"
    exit /b 1
)

set SCRIPT_DIR=%~dp0
set COMMIT_MSG=%~1

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$tokenFile = '%SCRIPT_DIR%__git-token.txt'; " ^
    "if (Test-Path $tokenFile) { $token = (Get-Content $tokenFile).Trim() } else { $token = Read-Host 'GitHub PAT token' }; " ^
    "git add -A; " ^
    "$commitOutput = git commit -m '%COMMIT_MSG%' 2>&1; " ^
    "if ($LASTEXITCODE -eq 0) { Write-Host $commitOutput } else { Write-Host 'Niets te committen, ga verder met pull/push.' }; " ^
    "git remote set-url origin \"https://muratbalasar:$token@github.com/muratbalasar/ashab-al-jannah.git\"; " ^
    "$branch = git rev-parse --abbrev-ref HEAD; " ^
    "git ls-remote --exit-code --heads origin $branch | Out-Null; " ^
    "if ($LASTEXITCODE -eq 0) { git pull origin $branch } else { Write-Host \"Branch $branch bestaat nog niet op remote, pull overgeslagen.\" }; " ^
    "git push -u origin $branch; " ^
    "git remote set-url origin 'https://github.com/muratbalasar/ashab-al-jannah.git'; " ^
    "exit 0"