param([Parameter(Mandatory=$true)][string]$BackupFile)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
if (-not (Test-Path '.env')) { throw '.env topilmadi.' }
$full = (Resolve-Path $BackupFile).Path
$answer = Read-Host "DIQQAT: $full bazaga qayta yuklanadi. Davom etish uchun RESTORE deb yozing"
if ($answer -cne 'RESTORE') { Write-Host 'Bekor qilindi.'; exit 0 }
$envValues = @{}
Get-Content '.env' | ForEach-Object { if ($_ -match '^\s*([^#=]+)=(.*)$') { $envValues[$matches[1].Trim()] = $matches[2].Trim().Trim('"').Trim("'") } }
$container = if ($envValues['POSTGRES_CONTAINER']) { $envValues['POSTGRES_CONTAINER'] } else { 'wentric-postgres' }
$db = if ($envValues['POSTGRES_DB']) { $envValues['POSTGRES_DB'] } else { 'wentric' }
$user = if ($envValues['POSTGRES_USER']) { $envValues['POSTGRES_USER'] } else { 'wentric' }
docker cp $full "${container}:/tmp/wentric_restore.dump"
if ($LASTEXITCODE -ne 0) { throw 'Backup konteynerga nusxalanmadi.' }
docker exec -e "PGPASSWORD=$($envValues['POSTGRES_PASSWORD'])" $container pg_restore --clean --if-exists --no-owner -U $user -d $db /tmp/wentric_restore.dump
if ($LASTEXITCODE -ne 0) { throw 'pg_restore xatolik berdi. Logni tekshiring.' }
docker exec $container rm -f /tmp/wentric_restore.dump
Write-Host 'Restore tugadi.' -ForegroundColor Green
