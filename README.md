# Hatsune Miku Discord Bot

Self-hosted Discord music bot built with `discord.py`, `yt-dlp`, and `ffmpeg`.\
Stores per-guild song play counts in SQLite.

## Features

- Play YouTube links, YouTube playlists, Spotify tracks, Spotify albums,
  Spotify playlists, SoundCloud track links, and plain search queries.
- Queue, skip, shuffle, clear, stop, and loop playback.
- Toggle queue-wide looping with `/loop-all`.
- Apply playback effects: volume, nightcore, bass boost, and speed.
- Show the current queue with playback state and queue controls.
- Track the most-played songs per Discord server.
- Optional owner-only debugger commands for inspecting and reloading cogs.

SoundCloud playlists are not currently supported.

## Commands

### Music

- `/play <query>`: Play or queue a song, playlist, Spotify link, SoundCloud
  track, YouTube link, or search query.
- `/queue`: Show the current queue and playback state.
- `/skip`: Skip the active song.
- `/shuffle`: Shuffle the queued songs.
- `/loop`: Toggle looping for the current song.
- `/loop-all`: Toggle looping for the full queue.
- `/remove <index>`: Remove a queued song by index.
- `/clear`: Clear the queue while keeping the bot connected.
- `/stop`: Stop playback, clear playback state, and disconnect from voice.
- `/volume <0.0-2.0>`: Set playback volume.
- `/night-core`: Toggle the nightcore effect.
- `/bass-boost <float>`: Apply a bass boost value.
- `/speed <0.5-2.0>`: Change playback speed.
- `/song-tracker`: Show the top played songs for the current server.

### Utility

- `/help`: Show the bot command list.
- `/die`: Shut down the bot. Owner only; requires `USER_ID`.

### Debugger

Debugger commands are loaded only when the bot launches with
`--debugger_enabled` and both `USER_ID` and `GUILD_ID` are set.

- `/cog_reload <cog_name>`: Reload a loaded extension.
- `/dump_cog_info <cog_class_name>`: Show command and guild-state information
  for a cog.

## Requirements

- Python `3.14`
- `uv`
- `ffmpeg`
- `node`

The Docker image installs `ffmpeg`, `libopus0`, `nodejs`, and `uv`.

## Configuration

The bot loads environment variables from `.env` in the project root.

Required:

- `DISCORD_TOKEN`: Discord bot token.

Optional:

- `SPOTIFY_CLIENT_ID`: Spotify API client id.
- `SPOTIFY_CLIENT_SECRET`: Spotify API client secret.
- `USER_ID`: Discord user id for owner-only commands.
- `GUILD_ID`: Discord guild id for debugger guild-scoped commands.

Spotify credentials are required for Spotify track, album, and playlist links.
Plain YouTube, SoundCloud track, and search playback do not require Spotify
credentials.

Minimal `.env` example:

```env
DISCORD_TOKEN=your_discord_bot_token
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
USER_ID=
GUILD_ID=
```

Runtime files:

- `logs/bot.log`: bot log output.
- `data/status.db`: SQLite database for per-guild song play counts.

## Local Setup

Install dependencies:

```bash
uv sync
```

Run the bot:

```bash
uv run hatsune-miku-bot
```

Run with debugger commands:

```bash
uv run hatsune-miku-bot --debugger_enabled
```

Run checks:

```bash
uv run ty check
uv run ruff format
uv run ruff check --fix
uv run pytest
```

## Docker Setup

Build the image:

```bash
docker build -t hatsune-miku-bot .
```

Run the container with an env file:

```bash
docker run -d \
  --name hatsune-miku-bot \
  --env-file path/to/your.env \
  -v "$(pwd)/logs:/app/logs" \
  -v "$(pwd)/data:/app/data" \
  --restart unless-stopped \
  hatsune-miku-bot
```
