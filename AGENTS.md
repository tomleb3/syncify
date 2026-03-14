# AGENTS.md

## Project overview

Syncify merges tracks from multiple Spotify playlists into a single target playlist, deduplicating as it goes. It runs as a scheduled GitHub Actions workflow and can also be managed interactively via a Telegram bot.

## Language and tooling

- Python (>=3.9), managed with [uv](https://docs.astral.sh/uv/)
- Dependencies are defined in `pyproject.toml` and locked in `uv.lock`
- No test framework is configured yet

## Project structure

- `syncify.py` - Core sync logic and CLI entry point (`make run`)
- `auth.py` - One-time Spotify OAuth Authorization Code flow (`make auth`)
- `setup.py` - Interactive setup wizard, pushes secrets/variables to GitHub (`make setup`)
- `bot.py` - Telegram bot for interactive playlist management (`make bot`)
- `.github/workflows/syncify.yml` - Scheduled GitHub Actions workflow
- `Makefile` - Common tasks: `init`, `setup`, `auth`, `bot`, `run`, `clean`

## Common commands

- `make init` - Create venv and install locked dependencies
- `make auth` - Run OAuth flow to obtain a Spotify refresh token
- `make setup` - Interactive setup (authorize, pick playlists, push to GitHub)
- `make run` - Run the sync locally
- `make bot` - Start the Telegram bot

## Authentication

Syncify uses the Spotify OAuth Authorization Code flow (not Client Credentials). The `auth.py` script handles the one-time browser-based authorization and produces a refresh token. On each run, `syncify.py` exchanges the refresh token for a fresh access token.

Required scopes: `playlist-read-private`, `playlist-modify-private`.

The redirect URI is `https://localhost:8888/callback`. This must be registered in the Spotify app's settings.

## Required environment variables

### Secrets (required)

- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `SPOTIFY_REFRESH_TOKEN`

### Variables (optional)

- `SPOTIFY_USER_ID`
- `SPOTIFY_SOURCE_PLAYLISTS` - Comma-separated playlist names (empty = all)
- `SPOTIFY_TARGET_PLAYLIST` - Target playlist name (default: `Syncified`)
- `SPOTIFY_INCLUDE_EXTERNAL` - Set to `true` to include followed playlists
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Error handling conventions

All functions that make Spotify API calls must re-raise exceptions after logging. Never swallow errors by returning empty defaults (e.g. `return []` or `return {}`). Errors must propagate to the caller so the process exits with a non-zero exit code on failure.

The only exception is best-effort operations like Telegram notifications (`_notify_telegram`) and GitHub variable/secret pushes (`_push_gh_variable`, `_push_gh_secret`), which log warnings but do not raise.

## Style guidelines

- Do not use em dashes (--) anywhere in code, comments, or documentation. Use standard dashes (-) or rewrite the sentence instead.
- Keep code straightforward. Avoid unnecessary abstractions or over-engineering.
- Use `raise_for_status()` on all Spotify API responses.
