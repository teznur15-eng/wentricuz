$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$BackupScript = Join-Path $PSScriptRoot 'backup.ps1'
$TaskName = 'Wentric Management Daily PostgreSQL Backup'
$PowerShell = (Get-Command powershell.exe -ErrorAction Stop).Source
$Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$BackupScript`""
$Action = New-ScheduledTaskAction -Execute $PowerShell -Argument $Arguments -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -Daily -At '23:00'
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Description 'Wentric PostgreSQL bazasining kundalik lokal backup nusxasi' -Force | Out-Null
Write-Host "Kundalik backup vazifasi o‘rnatildi: $TaskName (har kuni 23:00). Kompyuter yoqilgan va foydalanuvchi tizimga kirgan bo‘lishi kerak." -ForegroundColor Green
