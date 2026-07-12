# OmniAgent - Demarrage sans Docker (mode dev local)
# Usage :
#   powershell -ExecutionPolicy Bypass -File scripts/dev-up.ps1

$ErrorActionPreference = "Stop"

Write-Host "=== OmniAgent dev-up (sans Docker) ===" -ForegroundColor Cyan

# 1) Postgres natif (optionnel). Si pas dispo, on force OMNIAGENT_FORCE_MEMORY=1.
$pgOk = $false
try {
    $null = & psql --version 2>$null
    $pgOk = ($LASTEXITCODE -eq 0) -and (Test-NetConnection -ComputerName localhost -Port 5432 -WarningAction SilentlyContinue).TcpTestSucceeded
} catch { $pgOk = $false }

if ($pgOk) {
    Write-Host "[OK] Postgres joignable sur localhost:5432" -ForegroundColor Green
    $env:OMNIAGENT_DB_URL = "postgresql+asyncpg://omniagent:omniagent@localhost:5432/omniagent"
    Remove-Item Env:OMNIAGENT_FORCE_MEMORY -ErrorAction SilentlyContinue
} else {
    Write-Host "[WARN] Postgres indisponible -> bascule sur memoire (in-memory backend)" -ForegroundColor Yellow
    $env:OMNIAGENT_FORCE_MEMORY = "1"
}

# 2) Liberation des ports squattes par Docker/WSL (on lance sur 8090 si 8000 pris)
function Test-Port([int]$Port) {
    $c = netstat.exe -ano | Where-Object { $_ -match "LISTENING" -and ($_ -match ":$Port ") } | Select-String "LISTENING"
    return [bool]$c
}

$apiPort = if (Test-Port 8000) { 8090 } else { 8000 }
$webPort = if (Test-Port 3000) { 3006 } else { 3000 }
Write-Host "[INFO] API on port $apiPort / Web on port $webPort" -ForegroundColor Cyan

$env:NEXT_PUBLIC_API_URL = "http://localhost:$apiPort"

# 3) Demarrage du backend
Write-Host "[..] Demarrage backend (uvicorn)..." -ForegroundColor Cyan
$apiJob = Start-Job -ScriptBlock {
    Set-Location (Join-Path $using:PWD "apps/api")
    $env:PYTHONPATH = "$PWD/src"
    if ($env:OMNIAGENT_FORCE_MEMORY) { $env:OMNIAGENT_FORCE_MEMORY = $env:OMNIAGENT_FORCE_MEMORY }
    & "C:\Users\KOURO\AppData\Local\Programs\Python\Python314\python.exe" -m uvicorn omniagent.main:app `
        --host 127.0.0.1 --port $using:apiPort --log-level warning
}

# 4) Attente backend
Start-Sleep -Seconds 6
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$apiPort/docs" -UseBasicParsing -TimeoutSec 10
    if ($r.StatusCode -eq 200) { Write-Host "[OK] Backend up sur http://127.0.0.1:$apiPort" -ForegroundColor Green }
} catch {
    Write-Host "[ERR] Backend n a pas repondu : $_" -ForegroundColor Red
}

# 5) Demarrage du frontend
Write-Host "[..] Demarrage frontend (next dev)..." -ForegroundColor Cyan
$webJob = Start-Job -ScriptBlock {
    Set-Location (Join-Path $using:PWD "apps/web")
    $env:NEXT_PUBLIC_API_URL = $using:env:NEXT_PUBLIC_API_URL
    & npm run dev -- -p $using:webPort
}

Start-Sleep -Seconds 8
Write-Host ""
Write-Host "==============================================="
Write-Host " Frontend : http://localhost:$webPort/profil" -ForegroundColor Green
Write-Host " Backend  : http://127.0.0.1:$apiPort/docs" -ForegroundColor Green
Write-Host "==============================================="
Write-Host " Tapez Ctrl+C pour arreter. Jobs actifs :"
Get-Job | Format-Table Id,Name,State -AutoSize