$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path $PSScriptRoot -Parent

Set-Location $ProjectRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  throw "uv was not found in PATH. Install it from https://docs.astral.sh/uv/ and rerun this script."
}

uv sync

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
