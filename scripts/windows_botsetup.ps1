$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path $PSScriptRoot -Parent
$EnvPath = Join-Path $ProjectRoot "EnvHatsuneMiku"
$VenvPython = Join-Path $EnvPath "Scripts\python.exe"
$RequirementsPath = Join-Path $ProjectRoot "requirements.txt"

Set-Location $ProjectRoot

if (-not (Test-Path $EnvPath)) {
  Write-Host "Creating virtual environment at $EnvPath"
  if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -m venv $EnvPath
  } elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -m venv $EnvPath
  } else {
    throw "Python 3 was not found in PATH."
  }
} else {
  Write-Host "Virtual environment already exists at $EnvPath"
}

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r $RequirementsPath

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    & winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
  } else {
    Write-Warning "ffmpeg was not found and winget is unavailable. Install ffmpeg manually."
  }
} else {
  Write-Host "FFmpeg already installed."
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    & winget install -e --id OpenJS.NodeJS --accept-package-agreements --accept-source-agreements
  } else {
    Write-Warning "Node.js was not found and winget is unavailable. Install Node.js manually."
  }
} else {
  Write-Host "Node.js already installed."
}

Write-Host "Bot setup complete."
