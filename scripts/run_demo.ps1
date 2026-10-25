# Start the existing application with separate local presentation data.
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$pythonPath = Join-Path (Get-Location) '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Create .venv and install requirements-cpu.txt, then requirements-api.txt. See README.' }
if (-not (Test-Path -LiteralPath 'runs/augmentation_001/weights/best.pt')) { throw 'Restore the frozen checkpoint before starting. See docs/REPRODUCIBILITY.md. No replacement model is downloaded.' }
$env:STOREROOM_DB_PATH = 'outputs/portfolio-demo/storeroom.db'
$env:SCAN_STORAGE_DIR = 'outputs/portfolio-demo/scans'
& $pythonPath -m src.catalog_cli seed-alternatives-demo
if ($LASTEXITCODE -ne 0) { throw 'Demo initialization failed.' }
Write-Host 'StoreRoom overview: http://127.0.0.1:8001/static/overview.html'
Write-Host 'Separate demo storage; existing data/storeroom.db is unchanged. Ctrl+C stops the server.'
& $pythonPath -m uvicorn src.api:app --host 127.0.0.1 --port 8001
exit $LASTEXITCODE
