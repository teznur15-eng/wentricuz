$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $Root 'web')
if (-not (Test-Path 'node_modules')) { throw 'Avval ./scripts/setup.ps1 ni bajaring.' }
npm run dev
