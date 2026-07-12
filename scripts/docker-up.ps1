# Demarrage rapide de la stack API + Web en Docker, avec lecture live des logs.
# Usage : powershell -ExecutionPolicy Bypass -File C:\Users\KOURO\omniagent\scripts\docker-up.ps1

$ErrorActionPreference = "Continue"
$composeFile = "C:\Users\KOURO\omniagent\infrastructure\docker\docker-compose.yml"

# Ports publies sur l hote (chacun +1000 par rapport au port container pour eviter
# les conflits avec WSL/Docker qui squatte 3000/5432/6379/8000 sur cette machine).
$apiHost  = 18000
$webHost  = 13000

function Step($label, $color) {
    Write-Host "=== $label ===" -ForegroundColor $color
}

Step "Arret des containers existants (best-effort)" Cyan
docker compose -f $composeFile down --remove-orphans --timeout 5 2>&1 | Out-Null
foreach ($c in @("omniagent-api","omniagent-web","omniagent-redis","omniagent-postgres")) {
    docker rm -f $c 2>&1 | Out-Null
}
Write-Host ""

Step "Demarrage api + web (force-recreate, --no-deps)" Cyan
docker compose -f $composeFile up -d --force-recreate --no-deps api web 2>&1 | Out-Host
Write-Host ""

Step "URLs publiees sur l hote" Yellow
Write-Host "  API     : http://127.0.0.1:$apiHost/docs"
Write-Host "  Web     : http://127.0.0.1:$webHost/profil"
Write-Host ""

Step "Logs api (Ctrl+C pour arreter)" Cyan
docker logs -f --tail 60 omniagent-api