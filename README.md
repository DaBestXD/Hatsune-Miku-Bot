# Hatsune Miku Discord Bot

A self-hosted Discord music bot built with `discord.py`, `yt-dlp`, and `ffmpeg`.

## Features

- Plays music from YouTube, SoundCloud, Spotify links, or search queries
- Maintains a per-guild playback queue
- Interactive queue view with paging and playback controls
- Optional debugger cog for owner-only inspection commands
- Local startup flow with guided `.env` creation
- Docker image for non-interactive deployment

## Commands

### Music

- `/play <query>`: Queue a song, playlist, or search result
- `/queue`: Show the current queue with interactive controls
- `/skip`: Skip the current song
- `/shuffle`: Shuffle the queued songs
- `/loop`: Toggle looping for the current song
- `/remove <index>`: Remove a queued song by index
- `/clear`: Clear the queued songs while keeping the current track
- `/stop`: Stop playback and disconnect from voice
- `/volume <0.0-2.0>`: Set playback volume
- `/night-core`: Toggle the nightcore effect

### Utility

- `/help`: Display the bot command list
- `/unstuck`: Hard reset the playback controller for the current guild
- `/die`: Shut down the bot
  - Bot owner only. Controlled by `USER_ID`.

## Requirements

- Python 3.14
- `ffmpeg`
- `node`
  - Required by the configured `yt-dlp` JS runtime support

## Environment Variables

Required:

- `DISCORD_TOKEN`

Optional:

- `GUILD_ID`
- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `USER_ID`

Notes:

- `USER_ID` controls owner-only commands like `/die`
- `GUILD_ID` is only used for guild-scoped debugger commands when starting the bot with `--debugger`
- Spotify credentials are only needed for Spotify metadata support
- The project reads values from the process environment and from `.env`

Example `.env`:

```env
DISCORD_TOKEN=your_discord_bot_token
GUILD_ID=123456789012345678
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
USER_ID=
```

## Discord Setup

1. Create an application at the [Discord Developer Portal](https://discord.com/developers/applications).
2. Create a bot user for the application.
3. Copy the bot token for `DISCORD_TOKEN`.
4. Enable the intents your bot needs in the Discord developer portal.
   - The current bot code explicitly enables `message_content` and `voice_states`.
5. Invite the bot to your server with bot + application command scopes.
6. If you plan to use debugger mode, copy your server ID for `GUILD_ID`.

To get IDs, enable Developer Mode in Discord and use "Copy ID" on your user/server.

## Local Setup

### Linux / macOS

Bootstrap the venv and install Python dependencies:

```bash
scripts/bash_botsetup.sh
```

Start the bot:

```bash
scripts/bashrun_bot.sh
```

The run script will call setup automatically if `EnvHatsuneMiku` does not exist yet, and it forwards any extra args to `main.py`.

Examples:

```bash
scripts/bashrun_bot.sh --debugger
scripts/bashrun_bot.sh --docker
```

### Windows

Bootstrap the venv and install Python dependencies:

```powershell
.\scripts\windows_botsetup.ps1
```

If `ffmpeg` or `node` are missing, the setup script attempts to install them with `winget`.

Start the bot:

```powershell
.\scripts\winrun_bot.ps1
```

The run script will call setup automatically if `EnvHatsuneMiku` does not exist yet, and it forwards any extra args to `main.py`.

Examples:

```powershell
.\scripts\winrun_bot.ps1 --debugger
.\scripts\winrun_bot.ps1 --docker
```

### First Startup

Running `main.py` directly without `--docker` uses the guided local setup flow:

- If `.env` already exists, it is loaded
- If `.env` does not exist, the app prompts for values and writes the file for you

Equivalent manual run:

```bash
python main.py
```

Useful flags:

- `--docker`: skip the interactive `.env` prompt and read config from the environment
- `--debugger`: start the bot with the debugger cog enabled
  - The debugger cog loads owner-only debug commands and uses `USER_ID` and `GUILD_ID` for command gating/scoping

## Docker

The repo includes a single `Dockerfile`. The container starts the bot with:

```bash
python main.py --docker
```

Docker mode skips the interactive `.env` prompt and expects environment variables to be injected at runtime.

Build the image:

```bash
docker build -t hatsune-miku-bot .
```

Run it in the background:

```bash
docker run -d \
  --name hatsune-miku-bot \
  --env-file .env \
  -v "$(pwd)/logs:/app/logs" \
  --restart unless-stopped \
  hatsune-miku-bot
```

Useful Docker commands:

```bash
docker ps
docker logs -f hatsune-miku-bot
docker restart hatsune-miku-bot
docker stop hatsune-miku-bot
```

## Logging

- Logs are written to `./logs/bot.log`
- The logger creates the `logs/` directory automatically
- In Docker, mount `/app/logs` if you want logs persisted on the host

## Project Structure

- [`main.py`](main.py): Startup entrypoint
- [`botconfig/bot.py`](botconfig/bot.py): Bot initialization and extension loading
- [`cogs/musicplayer.py`](cogs/musicplayer.py): Music slash commands
- [`cogs/utilcommands.py`](cogs/utilcommands.py): Utility commands
- [`audio_utils/guildstate_controller.py`](audio_utils/guildstate_controller.py): Per-guild playback event loop
- [`docs/bot_music_player.md`](docs/bot_music_player.md): Music playback flow notes
