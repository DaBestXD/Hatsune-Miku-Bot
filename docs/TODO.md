<!-- markdownlint-disable -->
# TODO

- Implement deterministic Spotify-to-YouTube fuzzy matching based on the song !HALF-DONE!
- Add SoundCloud playlist support.
- Add ability to pass in cookie files for soundcloud and youtube
- Add Docstrings...

## Code review findings

(High) [`src/hatsune_miku_bot/audio/audio_resolver.py:385`]

- Description: Media-provider routing uses hostname substring checks, so an attacker-controlled hostname such as `youtube.attacker.example` can reach yt-dlp's generic extractor and make requests from the bot's network position. Git history shows this behavior predates the current changes.
- Suggested fix: Parse the URL and allow only exact trusted provider hostnames or validated subdomains. Add `allowed_extractors = ["youtube.*", "soundcloud.*", "end"]` as a second layer after fixing the SoundCloud URL handling described below.

(Medium) [`src/hatsune_miku_bot/audio/guild_state_controller.py:380`]

- Description: Modifier commands received before the asynchronous stop callback each insert another active-song copy and repeatedly count the same elapsed playback interval. Rapid nightcore, bass, and speed changes can repeat the song and seek too far forward.
- Suggested fix: Coalesce changes while a modifier restart is pending. Prefer an explicit restart state that does not mutate the song queue, and snapshot elapsed time only once per interruption.

(Medium) [`src/hatsune_miku_bot/audio/guild_state_controller.py:236`]

- Description: A 403 immediately after an effect change enters stale-source recovery before the modified-playback queue transition, leaving the inserted active-song copy to play again.
- Suggested fix: Have stale-source recovery consume or collapse a pending modifier restart, or remove the queue-copy restart design.

(Medium) [`src/hatsune_miku_bot/audio/audio_resolver.py:305`]

- Description: SoundCloud metadata stores yt-dlp's processed `url`, which is generally a temporary media/CDN URL rather than the stable SoundCloud webpage. This can break later cache refresh, 403 recovery, and an `allowed_extractors` restriction on `AUDIO_OPTS`.
- Suggested fix: Preserve `webpage_url` or `original_url` for SoundCloud songs and fall back to `url` only when necessary. Decide whether `on.soundcloud.com` short links should be resolved explicitly or rejected.

(Medium) [`src/hatsune_miku_bot/audio/audio_resolver.py:185`]

- Description: Spotify treats 401 and 429 responses as terminal. A rejected token can remain cached until local expiry, while a rate-limited page aborts the complete album or playlist request.
- Suggested fix: On 401, clear the token and refresh/retry once. On 429, honor `Retry-After` with bounded retries.

(Medium) [`.github/workflows/deploy.yml:46`]

- Description: `StrictHostKeyChecking=no` disables SSH server identity verification during deployment.
- Suggested fix: Pin the VM host key with protected `known_hosts` data and require host checking, or use Tailscale SSH with an appropriate ACL.

(Medium) [`.github/workflows/deploy.yml:53`]

- Description: Deployment removes the running container before building its replacement. A failed build leaves the bot offline.
- Suggested fix: Build before replacing the running container; use `docker compose up -d --build` without an unconditional preceding `down`.

(Low) [`src/hatsune_miku_bot/audio/guild_state_controller.py:110`]

- Description: Cache-removal tasks are untracked. After guild removal stops the controller, tasks can remain alive for 30 minutes and then enqueue events with no consumer.
- Suggested fix: Track delayed tasks per controller, deduplicate them by URL, and cancel/gather them during controller and cog cleanup.

(Low) [`.github/workflows/deploy.yml:29`]

- Description: CI uses unittest while project configuration and developer instructions use pytest, and CI omits the required type, format, and lint checks. Future pytest-style tests could be silently skipped.
- Suggested fix: Run `uv run pytest`, `uv run ty check`, `uv run ruff format --check`, and `uv run ruff check` in CI.

### CI/CD pipeline improvements

(Medium) [`.github/workflows/deploy.yml:3`]

- Description: CI currently runs only after changes have been pushed to `main` or `dev`, so it cannot act as a required pre-merge check. Because a push to `main` is also the deployment trigger, an unprotected direct push can reach the deployment pipeline before the change has been reviewed.
- Suggested fix: Add a CI workflow triggered by pull requests targeting `main` and configure a `main` branch protection rule or ruleset that requires a pull request and the CI status check before merging. Block force pushes and branch deletion; keep approvals optional for a single-maintainer repository.

(Medium) [`.github/workflows/deploy.yml:3`]

- Description: The combined workflow considers every push to `main` deployable, including documentation-only changes, resulting in unnecessary VM connections, image builds, and bot restarts.
- Suggested fix: Separate CI from deployment. Run CI for every pull request, but trigger deployment only for pushes to `main` that change runtime source, dependency manifests, the Docker configuration, or other deployment inputs. Retain `workflow_dispatch` for intentional manual deployments.

(Low) [`.github/workflows/deploy.yml:3`]

- Description: Applying `paths-ignore` to a required pull-request workflow can leave its required status check pending when GitHub skips the workflow, preventing a documentation-only pull request from merging.
- Suggested fix: Keep a stable required CI check that starts for every pull request. If documentation-only changes should skip expensive tests, use a lightweight change-detection job and have the required final CI gate succeed after either the code checks run successfully or the change is classified as documentation-only; apply path filtering to the deployment workflow instead.

(Low) [`README.md:36`]

- Description: The README documents `/speed` as accepting `0.01-2.0`, while the command and changelog use the supported `0.5-2.0` range.
- Suggested fix: Change the README lower bound to `0.5`.

### Test coverage gaps

(Medium) [`tests/test_audio_resolver.py:52`]

- Description: Spotify coverage does not exercise three or more pagination pages, token expiry between pages, a server-side 401, or a 429 response with `Retry-After`.
- Suggested fix: Add three-plus-page pagination tests, an explicit expired-token refresh test, a 401 refresh/retry test, and bounded 429 backoff coverage.

(Medium) [`tests/test_guild_state_controller.py:432`]

- Description: Modifier tests do not process multiple queued modifier events before `after_callback`, a modifier followed by 403 recovery, or a modifier while `song_loop_all` is active.
- Suggested fix: Add event-ordering regressions for all three state transitions and assert queue identity/count and playback offset.

(Low) [`tests/test_audio_resolver.py:129`]

- Description: Empty collections are tested at the Playlist model level, but resolver coverage does not exercise Spotify collections containing only null tracks or YouTube results with `entries=[]`.
- Suggested fix: Test both Spotify collection branches and the YouTube branch through their public resolver methods, asserting they return `None`.

(Medium) [`tests/test_audio_resolver.py:353`]

- Description: SoundCloud coverage checks basic metadata resolution but not preservation of the stable webpage URL or re-resolution after a media URL expires.
- Suggested fix: Assert that resolved songs retain their SoundCloud page URL and that playback resolution starts from that stable URL.

(Low) [`tests/test_cogs.py:33`]

- Description: Guild lifecycle coverage does not exercise `on_voice_state_update`, a missing controller during lifecycle races, delayed-task cancellation, or full cog cleanup.
- Suggested fix: Add bot-member filtering, missing-controller, guild-removal, and cleanup tests that assert no controller or cache task remains running.

(Low) [`src/hatsune_miku_bot/db_logging/db_main.py:14`]

- Description: DBLogic has no current source test module covering schema and query behavior.
- Suggested fix: Add tests for schema creation, playback upserts, guild isolation, deterministic tie ordering, the top-ten limit, and empty rankings.

(Low) [`src/hatsune_miku_bot/cogs/music.py:374`]

- Description: Command coverage does not verify `/speed` range metadata or `/song-tracker` empty and populated replies.
- Suggested fix: Add command-level tests for range enforcement and both song-tracker response branches.
