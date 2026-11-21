$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
& .\.venv\Scripts\python.exe scripts\create_admin.py
