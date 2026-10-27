$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    Write-Host "Creating local virtual environment..."
    python -m venv .venv
}
& $Python -c "import streamlit" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing open-source dependencies..."
    & $Python -m pip install -r requirements.txt
}
Write-Host "Starting Chuanbo X-Ray locally. No paid service or remote upload is used."
& $Python -m streamlit run app.py --server.address 127.0.0.1
