$Project_Root = split-path $PSScriptRoot -Parent
. (join-path $Project_Root "EnvHatsuneMiku\Scripts\Activate.ps1")
try {
    python -m pip install --upgrade yt-dlp
    python -m pip install --upgrade pip
    python (join-path $Project_Root "main.py")
}
finally {
    deactivate
}
