# TODO

- Implement deterministic Spotify-to-YouTube fuzzy matching based on the song !HALF-DONE!
- Define and implement recovery when ffmpeg reports `403 Forbidden` for a
  cached source.
- Add SoundCloud playlist support.
- Update the README to use `--debugger_enabled` and document `/loop-all`.
- Improve Spotify-to-YouTube resolution and caching performance.
- Add focused regression tests for completed TODO behavior:
  - rotating loop-all queues, switching loop modes, and restarting effects;
  - displaying the actual nightcore state in the queue embed;
  - clearing the built audio source on stop while retaining the URL cache;
  - resetting `SongMods.is_song_modified`;
  - returning `None` when every YouTube search candidate is filtered out;
  - returning from `/skip` without queuing an event when the queue is empty;
  - rendering debugger state for a queue containing exactly one song;
  - loading configuration without the removed interactive `env_loader` setup.
