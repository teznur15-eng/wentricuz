param([string]$OutputDir = '.\backups')
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
if (-not (Test-Path '.env')) { throw '.env topilmadi.' }
$envValues = @{}
Get-Content '.env' | ForEach-Object { if ($_ -match '^\s*([^#=]+)=(.*)$') { $envValues[$matches[1].Trim()] = $matches[2].Trim().Trim('"').Trim("'") } }
$container = if ($envValues['POSTGRES_CONTAINER']) { $envValues['POSTGRES_CONTAINER'] } else { 'wentric-postgres' }
$db = if ($envValues['POSTGRES_DB']) { $envValues['POSTGRES_DB'] } else { 'wentric' }
$user = if ($envValues['POSTGRES_USER']) { $envValues['POSTGRES_USER'] } else { 'wentric' }
$dest = Join-Path $Root $OutputDir
New-Item -ItemType Directory -Force -Path $dest | Out-Null
$file = Join-Path $dest ("wentric_{0}.dump" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
docker exec -e "PGPASSWORD=$($envValues['POSTGRES_PASSWORD'])" $container pg_dump -U $user -d $db -Fc -f /tmp/wentric_backup.dump
if ($LASTEXITCODE -ne 0) { throw 'pg_dump ishlamadi. PostgreSQL konteyneri va loginni tekshiring.' }
docker cp "${container}:/tmp/wentric_backup.dump" $file
if ($LASTEXITCODE -ne 0) { throw 'Backup faylini Docker ichidan nusxalab bo‘lmadi.' }
docker exec $container rm -f /tmp/wentric_backup.dump
Get-ChildItem $dest -File -Filter 'wentric_*.dump' | Sort-Object LastWriteTime -Descending | Select-Object -Skip 30 | Remove-Item -Force
Write-Host "Backup tayyor: $file" -ForegroundColor Green
