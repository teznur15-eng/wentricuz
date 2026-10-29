$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
Write-Host "Wentric Management - Windows setup" -ForegroundColor Cyan
foreach ($cmd in @('python','node','npm')) { if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "$cmd topilmadi. Uni o'rnating, so'ng PowerShell'ni qayta oching." } }
if (-not (Test-Path '.env')) { Copy-Item '.env.example' '.env'; Write-Host ".env yaratildi. Ishga tushirishdan oldin qiymatlarini tahrir qiling." -ForegroundColor Yellow }
if (-not (Test-Path 'web/.env.local')) { Copy-Item 'web/.env.local.example' 'web/.env.local' }
if (-not (Test-Path '.venv')) { python -m venv .venv }
$Py = Join-Path $Root '.venv/Scripts/python.exe'
& $Py -m pip install --upgrade pip
& $Py -m pip install -r 'backend/requirements.txt'
Push-Location 'web'
npm install
Pop-Location
Write-Host "Tayyor. .env qiymatlarini to'ldiring, keyin ./scripts/start-dev.ps1 ni bajaring." -ForegroundColor Green
