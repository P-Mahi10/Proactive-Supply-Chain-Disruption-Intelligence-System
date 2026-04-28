# ─────────────────────────────────────────────────────────────────────────────
# start_backend.ps1
# Run from the project root:  .\start_backend.ps1
# ─────────────────────────────────────────────────────────────────────────────

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir  = Join-Path $ProjectRoot "backend"

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  Supply Chain Intelligence System - Backend" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Project root : $ProjectRoot"
Write-Host "  Backend dir  : $BackendDir"
Write-Host "  Server URL   : http://localhost:8000"
Write-Host "  API docs     : http://localhost:8000/docs"
Write-Host ""

# Change into the backend directory so 'app' is importable
Set-Location $BackendDir

# Ensure the project root is on PYTHONPATH so simulation_model.py is found
$env:PYTHONPATH = $ProjectRoot

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
