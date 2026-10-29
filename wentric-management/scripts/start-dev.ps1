$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
if (-not (Test-Path ".env")) { throw ".env topilmadi. Avval .env.example dan nusxa oling va sozlang." }
Write-Host 'PostgreSQL Docker konteynerini ishga tushirish...' -ForegroundColor Cyan
docker compose up -d db
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL ishga tushmadi. Docker Desktop ishlayotganini tekshiring.' }
$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
  $health = docker inspect --format='{{.State.Health.Status}}' wentric-postgres 2>$null
  if ($health -eq 'healthy') { $ready = $true; break }
  Start-Sleep -Seconds 2
}
if (-not $ready) { throw 'PostgreSQL hali tayyor emas. Docker Desktop loglarini tekshiring.' }
Write-Host 'API, Telegram bot va web-panel alohida oynalarda ishga tushadi.' -ForegroundColor Green
Start-Process powershell -ArgumentList '-NoExit','-ExecutionPolicy','Bypass','-File', (Join-Path $PSScriptRoot 'start-api.ps1')
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList '-NoExit','-ExecutionPolicy','Bypass','-File', (Join-Path $PSScriptRoot 'start-bot.ps1')
Start-Process powershell -ArgumentList '-NoExit','-ExecutionPolicy','Bypass','-File', (Join-Path $PSScriptRoot 'start-web.ps1')
Write-Host 'Web: http://localhost:3000  |  API: http://127.0.0.1:8000/docs' -ForegroundColor Cyan
