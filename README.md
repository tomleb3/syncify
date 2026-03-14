# Syncify

Automatically merges tracks from multiple Spotify playlists into a single target playlist, deduplicating as it goes. Designed to run as a scheduled GitHub Actions workflow.

## How it works

Syncify reads your chosen source playlists and adds any tracks not already present into a single target playlist. It uses the [Spotify Web API](https://developer.spotify.com/documentation/web-api) with the Authorization Code flow.

## Setup

### 1. Create a Spotify app

Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard), create a new app, and note down the **Client ID** and **Client Secret**.

Add `http://127.0.0.1:8888/callback` as a **Redirect URI** in the app settings.

### 2. Fork this repo

Click **Fork** on GitHub to create your own copy, then clone it locally:

```bash
git clone https://github.com/yourusername/syncify
cd syncify
```

### 3. Run interactive setup

The setup script prompts for your credentials, authorizes with Spotify, fetches your playlists, lets you pick which ones to sync, and pushes everything to your GitHub repo as Secrets/Variables.

```bash
make init
make setup
```

`make setup` includes authorization as part of the wizard. Run `make auth` separately only if you need to re-authorize later (e.g. your refresh token was revoked) without repeating the full setup.

That's it. GitHub Actions will sync your playlists daily at midnight UTC.

## Configuration

All settings live as GitHub Secrets and Variables in your fork. The `make setup` script pushes these automatically, but you can also set or change them manually in the GitHub UI.

**Secrets** (Settings → Secrets and variables → Actions → Secrets):

| Name | Value |
|---|---|
| `SPOTIFY_CLIENT_ID` | Your Spotify app's Client ID |
| `SPOTIFY_CLIENT_SECRET` | Your Spotify app's Client Secret |
| `SPOTIFY_REFRESH_TOKEN` | Refresh token from `make auth` or `make setup` |
| `TELEGRAM_BOT_TOKEN` | *(auto-set by bot)* Telegram bot token for notifications |

**Variables** (Settings → Secrets and variables → Actions → Variables):

| Name | Value |
|---|---|
| `SPOTIFY_SOURCE_PLAYLIST_IDS` | Comma-separated playlist IDs (empty = all) |
| `SPOTIFY_TARGET_PLAYLIST_ID` | Target playlist ID |
| `SPOTIFY_INCLUDE_EXTERNAL` | Include followed playlists (default: false) |
| `TELEGRAM_CHAT_ID` | *(auto-set by bot)* Your Telegram chat ID for notifications |

## Schedule

Edit the cron expression in [`.github/workflows/syncify.yml`](.github/workflows/syncify.yml):

```yaml
schedule:
  - cron: '0 0 * * *'   # daily at midnight UTC
```

Use [crontab.guru](https://crontab.guru) to build expressions.

## Telegram bot (optional)

The Telegram bot lets you manage playlist selection interactively and receive notifications after every sync.

### Bot commands

| Command | Description |
|---|---|
| `/start` | Show help and your chat ID |
| `/playlists` | Pick playlists via a toggleable inline keyboard |
| `/sync` | Run sync immediately |

### Bot setup

1. Message [@BotFather](https://t.me/BotFather) on Telegram, send `/newbot`, and copy the token.

2. Run the bot with a GitHub PAT and it will push the token as a GitHub Secret automatically:
   ```bash
   TELEGRAM_BOT_TOKEN=your_bot_token GITHUB_TOKEN=your_pat make bot
   ```
   `GITHUB_TOKEN` is a [Personal Access Token](https://github.com/settings/tokens) with **Actions Secrets write** and **Actions Variables write** permissions.

3. Send `/start` to your bot. It will confirm your chat ID and push `TELEGRAM_CHAT_ID` as a GitHub Variable.

That's it. The cron workflow will now send Telegram notifications. Run the bot with `make bot` any time you want to change your playlist selection. Saving a selection also pushes the updated `SPOTIFY_SOURCE_PLAYLIST_IDS` Variable automatically.

## Local usage

```bash
make init    # create venv and install deps
make setup   # interactive setup, pushes to GitHub
make auth    # re-authorize only, pushes refresh token to GitHub
make run     # trigger a sync via GitHub Actions
make bot     # start the Telegram bot (requires env vars, see below)
```

`make run` dispatches the GitHub Actions workflow, so all secrets and variables
come from GitHub. No local environment variables are needed.

`make bot` is a long-running local process. It requires `SPOTIFY_CLIENT_ID`,
`SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REFRESH_TOKEN`, and `TELEGRAM_BOT_TOKEN` in
the environment.
