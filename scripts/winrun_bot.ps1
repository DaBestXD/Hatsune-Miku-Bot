$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path $PSScriptRoot -Parent
$SetupScript = Join-Path $PSScriptRoot "windows_botsetup.ps1"
Set-Location $ProjectRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue) -or -not (Test-Path (Join-Path $ProjectRoot ".venv"))) {
  Write-Host "uv environment not ready. Running setup first."
  & $SetupScript
}

uv run python -m yt_dlp --remote-components ejs:github --version | Out-Null
uv run hatsune-miku-bot @args
exit $LASTEXITCODE
