$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
if (-not (Test-Path '.venv/Scripts/python.exe')) { throw 'Avval ./scripts/setup.ps1 ni bajaring.' }
$env:PYTHONPATH = (Join-Path $Root 'backend')
& (Join-Path $Root '.venv/Scripts/python.exe') -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
