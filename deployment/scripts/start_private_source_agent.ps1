param([switch] $ConnectVps)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Resolve-Path (Join-Path $PSScriptRoot '../..'))
if (-not (Test-Path -LiteralPath '.env.v2-staging') -or -not (Select-String -LiteralPath '.env.v2-staging' -Pattern '^V2_AGENT_TOKEN=' -Quiet)) {
    powershell -NoProfile -ExecutionPolicy Bypass -File deployment/scripts/start_v2_staging.ps1
    if ($LASTEXITCODE -ne 0) { throw 'Local environment initialization failed' }
}
docker compose --env-file .env.v2-staging -f docker-compose.v2-staging.yml -f docker-compose.source-agent-desktop.yml --profile agent --profile browser up -d --build chrome agent
if ($LASTEXITCODE -ne 0) { throw 'Private source agent did not start' }
Write-Output 'Private source agent is bound to 127.0.0.1:8092 and requires its generated access token.'
if (-not $ConnectVps) { exit 0 }
# This switch is for the separately approved production release only. Configure
# the shared token privately in the VPS .env and use the source-agent overlay.
# No public listener or sshd/GatewayPorts modification is required.
Write-Output 'Keeping the approved private VPS SSH socket connected; closing this process stops the route.'
while ($true) {
    & ssh.exe -o BatchMode=yes -o ConnectTimeout=15 codex-vps-2 'install -d -m 700 /run/marketfusion-agent'
    if ($LASTEXITCODE -eq 0) {
        & ssh.exe -N -o BatchMode=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -o StreamLocalBindUnlink=yes -R '/run/marketfusion-agent/source.sock:127.0.0.1:8092' codex-vps-2
    }
    Start-Sleep -Seconds 10
}
