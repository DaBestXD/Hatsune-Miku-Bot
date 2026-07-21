<!-- markdownlint-disable -->
# TODO

- Implement deterministic Spotify-to-YouTube fuzzy matching based on the song !HALF-DONE!
- Add SoundCloud playlist support.
- Add ability to pass in cookie files for soundcloud and youtube
- Add Docstrings...

## Code review findings

(Medium) [`.github/workflows/deploy.yml:46`]

- Description: `StrictHostKeyChecking=no` disables SSH server identity verification during deployment.
- Suggested fix: Pin the VM host key with protected `known_hosts` data and require host checking, or use Tailscale SSH with an appropriate ACL.

(Medium) [`.github/workflows/deploy.yml:53`]

- Description: Deployment removes the running container before building its replacement. A failed build leaves the bot offline.
- Suggested fix: Build before replacing the running container; use `docker compose up -d --build` without an unconditional preceding `down`.

(Low) [`.github/workflows/deploy.yml:29`]

- Description: CI uses unittest while project configuration and developer instructions use pytest, and CI omits the required type, format, and lint checks. Future pytest-style tests could be silently skipped.
- Suggested fix: Run `uv run pytest`, `uv run ty check`, `uv run ruff format --check`, and `uv run ruff check` in CI.

### CI/CD pipeline improvements

- Avoid running expensive CI checks or deployments for documentation-only changes. Keep a lightweight required check that always reports success or failure so skipped jobs do not leave pull requests blocked, and filter the deployment workflow to runtime and deployment-related files.
- Learn and configure GitHub branch protection for `main`. Require changes to arrive through pull requests and require the CI status check before merging; block force pushes and branch deletion. Approvals can remain optional while the repository has a single maintainer.
