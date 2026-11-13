# setup_venv.ps1 — Automated Virtual Environment Setup for MAL_PROJECTS
# Usage: powershell -ExecutionPolicy Bypass -File .\setup_venv.ps1

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   Malayalam Projects Virtual Environment Setup (Python 3.12)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Locate Python 3.12
$pyCandidates = @(
    "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python312\python.exe",
    "python.exe"
)

$pythonExe = $null
foreach ($cand in $pyCandidates) {
    if (Test-Path $cand) {
        $pythonExe = $cand
        break
    }
}

if (-not $pythonExe) {
    try {
        $ver = (& python --version 2>&1)
        if ($ver -match "3\.12") {
            $pythonExe = "python"
        }
    } catch {}
}

if (-not $pythonExe) {
    Write-Host "[ERROR] Python 3.12 not found! Python 3.12 is required because pre-built wheels exist for Demucs/sphn." -ForegroundColor Red
    exit 1
}

Write-Host "[INFO] Using Python: $pythonExe" -ForegroundColor Green

# 2. Create .venv if not exists
$venvDir = Join-Path $PSScriptRoot ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "[1/4] Creating virtual environment at $venvDir..." -ForegroundColor Yellow
    & $pythonExe -m venv $venvDir
} else {
    Write-Host "[1/4] Virtual environment already exists at $venvDir." -ForegroundColor Green
}

# 3. Upgrade pip
Write-Host "[2/4] Upgrading pip..." -ForegroundColor Yellow
& $venvPython -m pip install --upgrade pip

# 4. Install PyTorch CPU wheels
Write-Host "[3/4] Installing PyTorch CPU wheels..." -ForegroundColor Yellow
& $venvPython -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# 5. Install requirements
$reqFile = Join-Path $PSScriptRoot "requirements.txt"
Write-Host "[4/4] Installing dependencies from requirements.txt..." -ForegroundColor Yellow
& $venvPython -m pip install -r $reqFile

# 6. Verify installation
Write-Host "`nVerifying environment..." -ForegroundColor Yellow
$verifyCmd = "import torch, torchaudio, demucs, uroman, soundfile, yaml; print('>>> All dependencies imported successfully! <<<')"
& $venvPython -c $verifyCmd

Write-Host "`nSetup complete! To activate your environment:" -ForegroundColor Green
Write-Host "   .\.venv\Scripts\Activate.ps1" -ForegroundColor Cyan
