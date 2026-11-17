$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$python = ".\.venv\Scripts\python.exe"
& $python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000