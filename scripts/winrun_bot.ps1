$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path $PSScriptRoot -Parent
$EnvPath = Join-Path $ProjectRoot "EnvHatsuneMiku"
$VenvPython = Join-Path $EnvPath "Scripts\python.exe"
$SetupScript = Join-Path $PSScriptRoot "windows_botsetup.ps1"
$MainPath = Join-Path $ProjectRoot "main.py"

Set-Location $ProjectRoot

if (-not (Test-Path $VenvPython)) {
  Write-Host "Virtual environment not found. Running setup first."
  & $SetupScript
}

& $VenvPython $MainPath @args
exit $LASTEXITCODE
