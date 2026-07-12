# Cree la base et l utilisateur "omniagent" sur ton Postgres cible (natif ou Docker).
# Run: powershell -ExecutionPolicy Bypass -File scripts\pg-init.ps1
# Variables d environnement reconnues avant execution :
#   PGHOST  (defaut: localhost)
#   PGPORT  (defaut: 5432)
#   PGUSER  (defaut: postgres)
#   PGINIT_USER     (defaut: omniagent)
#   PGINIT_PASSWORD (defaut: omniagent)
#   PGINIT_DB       (defaut: omniagent)

if (-not $env:PGHOST)            { $env:PGHOST = "localhost" }
if (-not $env:PGPORT)            { $env:PGPORT = "5432" }
if (-not $env:PGUSER)            { $env:PGUSER = "postgres" }
if (-not $env:PGINIT_USER)       { $env:PGINIT_USER = "omniagent" }
if (-not $env:PGINIT_PASSWORD)   { $env:PGINIT_PASSWORD = "omniagent" }
if (-not $env:PGINIT_DB)         { $env:PGINIT_DB = "omniagent" }

function Run($sql) {
    Write-Host ">> $sql" -ForegroundColor DarkCyan
    & psql -h $env:PGHOST -p $env:PGPORT -U $env:PGUSER -d postgres -c "$sql" 2>&1 | Out-Host
}

# 1) Role (idempotent)
$roleCheck = psql -h $env:PGHOST -p $env:PGPORT -U $env:PGUSER -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$env:PGINIT_USER'" 2>$null
if ($roleCheck -ne "1") {
    Run "CREATE ROLE $env:PGINIT_USER WITH LOGIN PASSWORD '$env:PGINIT_PASSWORD'"
} else {
    Run "ALTER ROLE $env:PGINIT_USER WITH LOGIN PASSWORD '$env:PGINIT_PASSWORD'"
}

# 2) Database (idempotent)
$dbCheck = psql -h $env:PGHOST -p $env:PGPORT -U $env:PGUSER -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$env:PGINIT_DB'" 2>$null
if ($dbCheck -ne "1") {
    Run "CREATE DATABASE $env:PGINIT_DB OWNER $env:PGINIT_USER"
}

# 3) Privileges
Run "GRANT ALL PRIVILEGES ON DATABASE $env:PGINIT_DB TO $env:PGINIT_USER"

Write-Host ""
Write-Host "Postgres pret. Connexion possible avec :" -ForegroundColor Green
Write-Host "    psql -h $env:PGHOST -p $env:PGPORT -U $env:PGINIT_USER -d $env:PGINIT_DB"
Write-Host "    (mot de passe: $env:PGINIT_PASSWORD)"