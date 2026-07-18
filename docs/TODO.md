# TODO

Deferred runtime work intentionally excluded from the test suite:

- Implement deterministic Spotify-to-YouTube fuzzy matching based on the song
  title.
- Define and implement recovery when ffmpeg reports `403 Forbidden` for a
  cached source.
- Implement loop-all over every current song, including the active song.
- Restrict music-cog voice-state updates to events for the bot's own member.
- Display the actual nightcore enabled state in the queue embed.
- Clear the built audio source on stop while retaining the resolved URL cache.
- Reset `SongMods.is_song_modified` in `SongMods.reset_all_values()`. !DONE!
- Return `None` when every YouTube search candidate is filtered out. !DONE!
- Add SoundCloud playlist support.
- Stop `/skip` after replying that the queue is empty instead of enqueuing a
  controller skip action.
- Make the debugger guild-state embed handle a queue containing exactly one
  song without indexing a nonexistent next song.
- Remove the obsolete interactive `env_loader` setup.
- Point the console script at `hatsune_miku_bot.__main__` and align the README
  and Docker flags with `--debugger_enabled` and `--docker_enabled`.
- Spotify caching can be very slow fix later
