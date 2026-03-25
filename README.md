# Hatsune Miku Discord Bot

## Bot Overview

Hatsune Miku Bot is a self-hosted Discord music bot built with `discord.py`, `yt-dlp`, and `ffmpeg`.


## Bot Commands

### Music

- `/play <query>`: Play or queue a song, playlist, Spotify link, or search query
- `/queue`: Show the current queue
- `/skip`: Skip the active song
- `/shuffle`: Shuffle the queued songs
- `/loop`: Toggle looping for the current song
- `/remove <index>`: Remove a queued song by index
- `/clear`: Clear the queue while keeping the current song
- `/stop`: Stop playback and disconnect from voice
- `/volume <0.0-2.0>`: Set playback volume
- `/night-core`: Toggle the nightcore effect
- `/bass-boost <float>`: Apply a bass boost value
- `/speed <0.01-2.0>`: Change playback speed

### Utility

- `/help`: Show the bot command list
- `/unstuck`: Hard-reset the bot in if playback becomes stuck
- `/die`: Shut down the bot
  - Owner only. Controlled by `USER_ID`.

### Debugger

These commands are only loaded when the bot launches with the `--debugger` flag
and both `USER_ID` and `GUILD_ID` are set.

- `/cog_reload <cog_name>`: Reload a cog
- `/dump_cog_info <cog_class_name>`: Dump command and guild-state info for a cog


## Bot Requirements

Local/runtime requirements:

- Python `3.14`
- `ffmpeg`
- `node`

Environment variables:

- Required: `DISCORD_TOKEN`
- Optional: `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `USER_ID`, `GUILD_ID`

Optional env usage:

- `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` enables Spotify playback
- `USER_ID` enables owner-only commands such as `/die`
- `GUILD_ID` is used for the debugger cog's guild-scoped commands

Minimal env example:

```env
DISCORD_TOKEN=your_discord_bot_token
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
USER_ID=
GUILD_ID=
```

## Docker Setup

Build the image:

```bash
docker build -t hatsune-miku-bot .
```

Run the container with your own env file:

```bash
docker run -d \
  --name hatsune-miku-bot \
  --env-file path/to/your.env \
  -v "$(pwd)/logs:/app/logs" \
  -v "$(pwd)/data:/app/data" \
  --restart unless-stopped \
  hatsune-miku-bot
```

