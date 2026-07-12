# Bootstrap complet (PowerShell)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "=== 1. Lancement Docker (PostgreSQL + Redis) ===" -ForegroundColor Cyan
Push-Location "$root\infrastructure\docker"
docker compose up -d
Pop-Location

Write-Host "=== 2. venv Python + dependances API ===" -ForegroundColor Cyan
Push-Location "$root\apps\api"
if (-not (Test-Path ".venv")) { python -m venv .venv }
& ".\.venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium
Pop-Location

Write-Host "=== 3. Installation frontend ===" -ForegroundColor Cyan
Push-Location "$root\apps\web"
if (-not (Test-Path "node_modules")) { npm install }
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
Pop-Location

Push-Location "$root\apps\api"
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
Pop-Location

Write-Host ""
Write-Host "=== Setup termine ! ===" -ForegroundColor Green
Write-Host "  API : http://localhost:8000/docs"
Write-Host "  WEB : http://localhost:3000"
Write-Host ""
Write-Host "Demarrage :"
Write-Host "  cd apps\api ; .venv\Scripts\Activate.ps1 ; uvicorn omniagent.main:app --reload"
Write-Host "  cd apps\web ; npm run dev"