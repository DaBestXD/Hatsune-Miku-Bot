$Project_Root = split-path $PSScriptRoot -Parent
$Env_path = join-path $Project_Root "HatsuneMikuENV"
if (test-path $Env_path) {
  echo "Virutal envionrment already set up."
} else {
  python -m venv $Env_path
  . (join-path $Env_path "Scripts\Activate.ps1")
  python -m pip install -r (join-path $Project_Root "requirements.txt")
  deactivate
  winget install ffmpeg
  echo "Bot setup complete restart terminal and run winrun_bot.ps1"
}

