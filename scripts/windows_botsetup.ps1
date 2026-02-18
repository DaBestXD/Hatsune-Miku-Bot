$Project_Root = split-path $PSScriptRoot -Parent
$Env_path = join-path $Project_Root "EnvHatsuneMiku"
if (test-path $Env_path) {
  echo "Virutal envionrment already set up."
} else {
  python -m venv $Env_path
  . (join-path $Env_path "Scripts\Activate.ps1")
  python -m pip install -r (join-path $Project_Root "requirements.txt")
  deactivate
  if (-not (get-command ffmpeg -erroraction silentlycontinue)){
    winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
  } else {
      echo "FFmpeg already installed."
  }
  if (-not (get-command node -erroraction silentlycontinue)){
    winget install -e --id OpenJS.NodeJS --accept-package-agreements --accept-source-agreements
  } else {
      echo "Node already installed."
  }
  echo "Bot setup complete restart terminal and run winrun_bot.ps1"
}

