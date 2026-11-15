$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Resolve-Path (Join-Path $PSScriptRoot '../..'))
$container = (docker compose --env-file .env.v2-staging -f docker-compose.v2-staging.yml ps -q db).Trim()
if (-not $container) { throw 'Start the isolated V2 staging database first' }
$details = docker inspect $container | ConvertFrom-Json
$project = $details[0].Config.Labels.'com.docker.compose.project'
if ($project -ne 'marketfusion-v2-staging') { throw 'Refusing to operate outside local staging' }
$restoreDb = 'restore_v2_' + [Guid]::NewGuid().ToString('N')
$backupDir = Join-Path (Get-Location) 'backups/v2'
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$dumpPath = Join-Path $backupDir ((Get-Date -Format 'yyyyMMdd-HHmmss')+'.dump')
docker exec $container pg_dump -U marketfusion -d marketfusion_v2 -Fc -f /tmp/marketfusion-v2-check.dump
if ($LASTEXITCODE -ne 0) { throw 'pg_dump failed' }
docker cp "${container}:/tmp/marketfusion-v2-check.dump" $dumpPath
if ($LASTEXITCODE -ne 0) { throw 'Copying backup failed' }
docker exec $container createdb -U marketfusion $restoreDb
if ($LASTEXITCODE -ne 0) { throw 'Creating isolated restore database failed' }
try {
    docker exec $container pg_restore -U marketfusion --exit-on-error --no-owner -d $restoreDb /tmp/marketfusion-v2-check.dump
    if ($LASTEXITCODE -ne 0) { throw 'pg_restore failed' }
    $query = "SELECT (SELECT count(*) FROM users),(SELECT count(*) FROM favorites),(SELECT count(*) FROM v2_watches),(SELECT count(*) FROM schema_migrations)"
    $original = docker exec $container psql -U marketfusion -d marketfusion_v2 -At -c $query
    $restored = docker exec $container psql -U marketfusion -d $restoreDb -At -c $query
    if ($original -ne $restored) { throw 'Restored counts do not match' }
    Copy-Item -LiteralPath .env.v2-staging -Destination (Join-Path $backupDir 'staging.env.restore-tested')
    Write-Output "Restore verified: $original ; dump stored under ignored backups/v2"
} finally {
    # This name is generated above; project identity was checked before creation.
    docker exec $container dropdb -U marketfusion $restoreDb | Out-Null
}
