# Diagnostique rapide de la stack Docker.
# Usage : powershell -ExecutionPolicy Bypass -File C:\Users\KOURO\omniagent\scripts\diag.ps1

$ErrorActionPreference = "SilentlyContinue"
$c = "Cyan"; $r = "Red"; $g = "Green"; $y = "Yellow"

function Show($label, $cmd) {
    Write-Host "== $label ==" -ForegroundColor $c
    $out = & $cmd 2>&1
    $rc = $LASTEXITCODE
    if ($rc -eq 0 -and $out) {
        Write-Host ($out | Out-String).TrimEnd() -ForegroundColor $g
    } elseif ($out) {
        Write-Host ($out | Out-String).TrimEnd() -ForegroundColor $r
    } else {
        Write-Host "(no output)" -ForegroundColor $y
    }
    Write-Host ""
}

Write-Host "=== OmniAgent diagnostics ===" -ForegroundColor Cyan
Write-Host ""

Show "Docker version"           { docker version --format "{{.Server.Version}}" }
Show "docker compose version"  { docker compose version }
Show "Containers"              { docker compose -f C:\Users\KOURO\omniagent\infrastructure\docker\docker-compose.yml ps }
Show "Logs api (40 last)"      { docker logs --tail 40 omniagent-api }
Show "Logs postgres (40 last)" { docker logs --tail 40 omniagent-postgres }
Show "Logs redis (40 last)"    { docker logs --tail 40 omniagent-redis }
Show "Postgres NATIVE on host" { Get-NetTCPConnection -LocalPort 5432 -State Listen | Select-Object LocalAddress,LocalPort,OwningProcess }
Show "Redis NATIVE on host"    { Get-NetTCPConnection -LocalPort 6379 -State Listen | Select-Object LocalAddress,LocalPort,OwningProcess }

Write-Host "== Inspection manuelle des routes /api dans le compose (api/web ports) ==" -ForegroundColor $c
foreach ($p in 5432,6379,8000,3000,8090,3006) {
    $c2 = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    if ($c2) {
        Write-Host ("Port {0,5}  PID={1}  {2}" -f $p, $c2.OwningProcess, $c2.LocalAddress) -ForegroundColor $g
    } else {
        Write-Host ("Port {0,5}  libre" -f $p) -ForegroundColor $y
    }
}
Write-Host ""
Write-Host "Fin du diagnostic." -ForegroundColor $c