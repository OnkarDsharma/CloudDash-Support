Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Error "Virtual environment not found. Run: python -m venv .venv"
    exit 1
}

Set-Location $ProjectRoot
& $Python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload

