$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Resolve-Path (Join-Path $PSScriptRoot '../..'))
$stagingEnv = Join-Path (Get-Location) '.env.v2-staging'
function New-LocalSecret([int] $Count = 24) {
    $buffer = New-Object byte[] $Count
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($buffer)
    return [Convert]::ToBase64String($buffer).Replace('+','-').Replace('/','_')
}
if (-not (Test-Path -LiteralPath $stagingEnv)) {
    $lines = @()
    $lines += 'V2_DB_PASSWORD=' + (New-LocalSecret)
    $lines += 'V2_WEB_PASSWORD=' + (New-LocalSecret)
    $lines += 'V2_SESSION_SECRET=' + (New-LocalSecret 32)
    $lines | Set-Content -Encoding ascii -LiteralPath $stagingEnv
}
if (-not (Select-String -LiteralPath $stagingEnv -Pattern '^V2_ENCRYPTION_KEY=' -Quiet)) {
    Add-Content -Encoding ascii -LiteralPath $stagingEnv -Value ('V2_ENCRYPTION_KEY='+(New-LocalSecret 32))
}
if (-not (Select-String -LiteralPath $stagingEnv -Pattern '^V2_AGENT_TOKEN=' -Quiet)) {
    Add-Content -Encoding ascii -LiteralPath $stagingEnv -Value ('V2_AGENT_TOKEN='+(New-LocalSecret 32))
}
docker compose --env-file .env.v2-staging -f docker-compose.v2-staging.yml up -d --build
if ($LASTEXITCODE -ne 0) { throw 'Staging did not start' }
Write-Output 'Staging: http://127.0.0.1:8089 ; local login is stored in ignored .env.v2-staging'
