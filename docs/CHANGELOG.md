<!-- markdownlint-disable -->

# Changelog

User-facing changes and developer-facing internal changes are tracked together.
Dates are listed without release versions for now.

## 2026-07-18

### Added

- Added `/loop-all` to loop the full queue.
- Added `/song-tracker` to show the most-played songs for the current server.
- Added per-server song play counting for `/song-tracker`.

### Changed

- Adjusted `/loop` and `/loop-all` so only one loop mode is active at a time.

### Fixed

- Fixed `/skip` so an empty queue replies with `Queue empty!` and stops there.
- Fixed stale cached audio sources so playback reloads the active song after a 403 audio-source error.
- Fixed bot voice-state handling so only the bot's own voice updates change playback state.

### Removed

- Removed the deprecated bot status runtime from the main bot startup path.
- Removed dead bot status and playback code that was no longer reachable from the current entrypoint.

### Internal

- Added a SQLite-backed playback logging layer that creates the playback table, records song starts per guild, and exposes ranked per-guild playback counts for the music cog.
- Patched Docker Compose and runtime configuration after removing the old bot status database service.
- Restored the bot-id guard in `on_voice_state_update` so unrelated member voice events cannot mutate bot playback state.
- Updated `README.md` and `.env.example` to match the current package entrypoint, environment values, logs path, data path, and SQLite playback tracking behavior.
- Switched logging from a plain file handler to a rotating file handler so long-running deployments do not grow `logs/bot.log` indefinitely.
- Reworked stale audio-source recovery to remove the stale cached source, restore the active song to the front of the queue when needed, clear seek/mod timing state, and retry playback through the normal playback path.
- Added regression tests for TODO-driven playback fixes, including stale cache recovery, voice-state filtering, and queue/playback edge cases.
- Updated tracked TODO notes after moving playback reliability items into tests or implementation.

## 2026-07-17

### Changed

- Restored Spotify matching so Spotify links resolve closer to YouTube Music matches.

### Fixed

- Fixed the `/queue` embed so the Nightcore status displays correctly.

### Internal

- Fixed typing issues reported by `ty` in the audio resolver, music cog, and database logging code.
- Split bot status code into a separate `src/bot_status` package area so status API/database code was isolated from the main `hatsune_miku_bot` package.
- Removed unused constants and moved remaining constants closer to the modules that actually use them.
- Refactored the test suite by replacing older module names, removing duplicate legacy tests, and consolidating coverage around the current `src/hatsune_miku_bot` package layout.
- Removed redundant helpers and fields from `GuildStateController` and `Song`/`Playlist` classes after the queue and resolver rewrites made them unnecessary.
- Reworked Spotify source resolution to normalize titles, search YouTube Music, compare candidate songs, and resolve the closest match instead of relying only on highest view count or the first search result.
- Fixed Docker-related project setup issues after the package layout and status-service changes.

## 2026-07-16

### Fixed

- Fixed owner debugger commands so `/cog_reload` and `/dump_cog_info` work again.

### Internal

- Fixed the `BotDebugger` cog after package renames and extension path changes.
- Applied small import, typing, tooling, and startup patches needed to keep the reorganized package runnable.

## 2026-07-15

### Changed

- Updated `/queue` embed presentation for a cleaner queue view.

### Removed

- Removed the `/unstuck` command from the public command list.

### Internal

- Continued the audio handler rewrite by replacing the older synchronous/request-heavy resolver path with the newer `AudioInfoResolver` design.
- Moved Spotify API access toward async `aiohttp` calls, token caching, retry handling, and clearer route handling for tracks, albums, and playlists.
- Reworked YouTube and SoundCloud resolution internals around `Song` and `Playlist` objects instead of loose tuples.
- Updated queue embed internals to show current playback state, queue details, effect state, page controls, and shorter song titles consistently after the model rewrite.
- Removed the old bot events file after event handling was folded into the controller-oriented playback flow.
- Renamed and reorganized modules into clearer package paths: audio code under `audio`, bot startup/config under `bot_config`, Discord helpers under `utils`, and cogs by responsibility.
- Moved the music cog, utility cog, debug cog, audio resolver, queue view, playback helpers, and song/playlist models into the current `src/hatsune_miku_bot` package structure.

## 2026-07-14

### Internal

- Started a larger refactor of audio handling and guild playback control by adding rewrite modules for the audio resolver and guild controller beside the existing implementation.

## 2026-07-09

### Internal

- Started a YouTube-focused audio handler rewrite to separate source lookup from source playback behavior.

## 2026-05-20

### Changed

- Adjusted Spotify search matching to improve the audio selected for Spotify links.

### Internal

- Updated resolver tests around Spotify matching and source selection behavior.
- Cleaned up bot config and logging assumptions while updating Spotify resolver settings.

## 2026-05-18

### Internal

- Refactored the project into a `uv`/`src` package layout.
- Moved runtime code under `src/hatsune_miku_bot`, moved package metadata into `pyproject.toml`, and updated imports/tests around the installable package structure.
- Reorganized assets, audio utilities, bot config, cogs, database code, and startup code under the package root so local execution is closer to packaged execution.

## 2026-04-01

### Fixed

- Fixed playback desync when changing speed-based effects during a song.

### Internal

- Fixed speed-effect position tracking so the controller accounts for effective playback rate when calculating where to resume after speed or pitch-like changes.
- Fixed reset behavior for playback modifiers so stopped playback clears offset, seek, and modifier state consistently.
- Fixed a bad import path after the package layout changed.

## 2026-03-25

### Internal

- Fixed startup behavior and Docker packaging after the March package and deployment work.
- Adjusted image/build configuration so runtime files and imports line up inside the container.
- Updated test imports after project layout changes so the suite targets current modules rather than older package paths.

## 2026-03-24

### Changed

- Improved bot startup and playback reliability when command handling or playback fails.

### Internal

- Improved startup cleanup when bot startup fails so resources close more reliably after partial initialization.
- Improved playback reliability around queue and source errors so failed playback events do not stop the main queue loop.
- Added broader test coverage for bot config, startup lifecycle, database logic, audio resolving, queue handling, and playback controller behavior.
- Added tests around startup failure cleanup and event-loop resilience.
- Applied minor bug fixes discovered during the reliability and test pass.

## 2026-03-23

### Internal

- Added API endpoints for bot status data, including status, uptime windows, and recent event data backed by status database helpers.
- Restructured the project for deployment by moving runtime modules and adding deployment-oriented configuration files.
- Added and iterated on deployment workflow files.
- Fixed variable names, import paths, and deployment config while stabilizing the new structure.
- Moved modules toward absolute imports so deployment and packaged execution no longer depend as heavily on the current working directory.
- Fixed utility command import paths missed during the restructure.
- Fixed view-count handling when candidate search results had tied values.
- Fixed CORS origins for the status API.

## 2026-03-21

### Internal

- Added early GitHub Actions workflow testing before the later deployment workflow and test-suite cleanup stabilized.

## 2026-03-20

### Added

- Added `/bass-boost` to apply a bass effect to playback.
- Added `/speed` to change playback speed from `0.01` to `2.0`.

### Internal

- Updated the bot run script to auto-update `yt-dlp` before launch.
- Added internal support for bass and speed FFmpeg filter generation.
- Added modifier handling to restart playback near the current position after changing bass or tempo filters.

## 2026-03-16

### Internal

- Added a debugger launch option so owner-only debug commands can be loaded only when explicitly enabled.
- Updated README setup documentation for the debugger flag and current run workflow.

## 2026-03-14

### Internal

- Added Docker test work as part of deployment and containerization experiments.

## 2026-03-13

### Internal

- Fixed guild state bugs after the playback-state queue conversion.
- Revamped the guild playback state dictionary so state lookup and lifecycle management are more consistent across guild join, ready, command, and disconnect paths.

## 2026-03-12

### Added

- Added `/help` to list available bot commands.
- Added `/unstuck` to reset stuck playback for the current server.

### Internal

- Changed guild playback state processing to use an `asyncio.Queue`.
- Moved command handling toward enqueueing playback events for a per-guild controller loop instead of mutating playback state directly from several command paths.
- Added the temporary `/unstuck` reset path while the queue-based controller was still being stabilized.

## 2026-03-10

### Added

- Added an interactive `/queue` view with page controls.
- Added queue buttons for shuffle, Nightcore, and stop.
- Added owner debugger commands `/cog_reload` and `/dump_cog_info`.

### Internal

- Refactored music bot modules into `audio_utils`, splitting audio source lookup, playback helpers, guild playback state, and queue model/embed code into separate modules.
- Added queue view support code, including paged queue embeds and Discord UI button callbacks for queue actions.
- Expanded debugger command support with cog reload and state dump helpers for inspecting command registration and per-guild playback state.

## 2026-03-07

### Changed

- Polished music command embeds and response formatting.

### Internal

- Cleaned up embed and response UI internals so song and playlist responses were more consistent before the later queue embed/view refactor.

## 2026-03-06

### Added

- Added `/night-core` to toggle the Nightcore playback effect.

### Fixed

- Fixed `/night-core` so the effect applies correctly during playback.

### Internal

- Added Nightcore filter plumbing and fixed the FFmpeg filter application path.
- Started tracking modifier state needed for effect toggles so playback can restart with modified audio filters.

## 2026-03-05

### Internal

- Applied minor bug fixes around bot config, constants, music command behavior, and requirements after the embed/model changes.

## 2026-03-04

### Added

- Added richer embeds for songs, playlists, queue display, skip messages, and playback errors.

### Internal

- Added `Song` and `Playlist` classes to replace many loose tuple/list payloads flowing through the music player.
- Added shared embed generation for songs, playlists, queue display, skip messages, and playback errors.
- Added the bot thumbnail asset and wired it into embeds.

## 2026-02-28

### Fixed

- Fixed `/stop` so it disconnects the bot from voice.
- Fixed duplicate slash commands appearing in Discord.

### Internal

- Fixed stop-command cleanup so stopping playback also disconnects from voice and resets relevant playback state.
- Merged the multi-server overhaul to `main`.
- Fixed duplicate slash command registration after the multi-server merge.

## 2026-02-27

### Added

- Added per-server playback state so multiple Discord servers can use the bot independently.
- Added per-server song caching support.

### Internal

- Started the multi-server playback rewrite by moving playback state away from a single global queue and toward per-guild state objects.
- Scoped cached audio sources by guild playback state rather than sharing one global player cache.
- Applied minor resolver and bot config bug fixes discovered during the multi-server rewrite.

## 2026-02-25

### Changed

- Improved plain search queries so channel results are skipped and better playable songs are selected.
- Improved caching so queued songs are refreshed after skip and shuffle.

### Fixed

- Improved playback recovery so bad audio sources are skipped instead of leaving playback stuck.

### Internal

- Improved cache lifetime and cache refresh handling.
- Allowed current sources to be inserted into the cache immediately and restarted cache tasks more carefully.
- Improved search result selection by skipping channel results and preferring playable candidates with higher view counts.
- Fixed playback helper behavior around bad sources so unresolved queued sources are reported and skipped.
- Improved cache invalidation after skip and shuffle so queued songs are re-cached in the new playback order.

## 2026-02-24

### Added

- Added audio caching so queued songs start faster.

### Fixed

- Improved handling for stale cached audio sources.
- Fixed caching after `/shuffle`.

### Internal

- Added basic audio-source caching for queued songs.
- Improved stale cached-source handling by detecting 403 errors from FFmpeg stderr and removing stale cache entries before continuing playback.
- Fixed cache state after shuffle so cached sources correspond to the new queue order.
- Applied additional music player bug fixes around cache tasks, queue state, and playback transitions.

## 2026-02-23

### Internal

- Added early caching to reduce delay before the next song starts by pre-resolving audio sources for queued songs.

## 2026-02-22

### Added

- Added playlist support to `/play`.
- Added Spotify album and playlist support to `/play`.
- Added `/shuffle` to shuffle queued songs while keeping the current song active.
- Added `/volume` to set playback volume.

### Internal

- Prototyped playlist handling and cleaned it up into the main music command path.
- Added volume state using `PCMVolumeTransformer`.
- Updated `main.py` and related command setup while integrating playlist and volume changes.

## 2026-02-20

### Fixed

- Fixed first-start setup so the bot can prompt for missing environment values before startup.
- Fixed owner ID handling for owner-only commands.

### Internal

- Fixed first-start crashes around missing environment values by loading setup values before constants are consumed.
- Fixed startup/config bugs around token, guild id, and user id handling.
- Fixed owner user-id parsing so owner-only command checks compare against an integer user id.

## 2026-02-18

### Internal

- Added bot run and startup scripts for Windows and Unix-like local development.
- Added initial README setup documentation with Discord application setup, environment values, and platform-specific run instructions.
- Fixed README links and setup notes through several documentation-only commits.

## 2026-02-17

### Changed

- Improved `/play` handling for direct links and search input.

### Removed

- Removed `/play-next` during the playback command rewrite.

### Internal

- Refactored YouTube download and music player logic after moving away from the initial local database approach.
- Changed playback code to resolve titles and source URLs on demand instead of depending on pre-added local files.
- Added a setup script for loading environment values from the user.

## 2025-12-22

### Added

- Added SoundCloud track support to `/play`.

### Fixed

- Improved error handling when a track cannot be downloaded or resolved.

### Internal

- Added SoundCloud resolver support to the downloader layer.
- Added controlled download error handling so failed track downloads or invalid sources do not crash the command path.

## 2025-12-21

### Added

- Added Spotify track link support to `/play`.

### Internal

- Added Spotify resolver support so Spotify track links could be translated into playable audio searches.
- Removed remaining `pytubefix` usage after the migration to `yt-dlp`.

## 2025-12-20

### Added

- Added `/remove <index>` to remove a queued song.

### Changed

- Improved playback responses to include clickable song links.

### Internal

- Removed the old downloader module and continued consolidating playback around the `yt-dlp` downloader path.
- Added remove-from-queue command logic and index validation in the music cog.

## 2025-12-19

### Added

- Added `/die` for owner-only bot shutdown.

### Changed

- Changed `/play` to accept YouTube links and search terms directly.

### Removed

- Removed `/add-url` and `/song-db` after direct playback replaced the local song database flow.

### Internal

- Switched from `pytubefix` to `yt-dlp` for media extraction.
- Moved playback from a local-file download/cache model toward resolving streaming audio sources.
- Removed the local audio file database flow, including command paths for adding/listing local database songs.

## 2025-12-17

### Added

- Added `/clear` to clear the music queue.
- Added `/play-next` to insert a song after the current song.
- Added `/loop` to toggle looping for the current song.

### Changed

- Updated `/queue` to show numbered entries.

### Internal

- Added environment-based guild configuration instead of a hard-coded guild id.
- Added early queue mutation and loop state handling for clear, play-next, skip, and loop behavior.
- Updated queue display logic to track song order and show indexed queue entries.

## 2025-12-16

### Added

- Added initial Discord music bot commands: `/add-url`, `/play`, `/stop`, `/skip`, `/queue`, and `/song-db`.
- Added queue playback so additional songs wait behind the current song.

### Internal

- Created the initial Discord bot project with a first music cog, command registration, voice joining, queue state, and local SQLite-backed audio file lookup.
- Added the first local audio database code for storing downloaded YouTube file paths and matching song names during `/play`.
