# TODO

- Implement deterministic Spotify-to-YouTube fuzzy matching based on the song !HALF-DONE!
- Add SoundCloud playlist support.
- Improve Spotify-to-YouTube resolution and caching performance.
- Add focused regression tests for completed TODO behavior:
  - rotating loop-all queues, switching loop modes, and restarting effects;
  - clearing the built audio source on stop while retaining the URL cache;
  - returning `None` when every YouTube search candidate is filtered out;
