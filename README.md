# Syncify

Automatically merges tracks from multiple Spotify playlists into a single target playlist, deduplicating as it goes. Designed to run as a scheduled GitHub Actions workflow.

## How it works

Syncify reads your chosen source playlists and adds any tracks not already present into a single target playlist (default name: **Syncified**). It uses the [Spotify Web API](https://developer.spotify.com/documentation/web-api) with the Client Credentials flow.

## Setup

### 1. Create a Spotify app

Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard), create a new app, and note down the **Client ID** and **Client Secret**.

### 2. Fork this repo

Click **Fork** on GitHub to create your own copy, then clone it locally:

```bash
git clone https://github.com/yourusername/syncify
cd syncify
```

### 3. Run interactive setup

The setup script fetches your real Spotify playlists, lets you pick which ones to sync, and pushes everything to your GitHub repo as Secrets/Variables.

```bash
make init
export SPOTIFY_CLIENT_ID=your_client_id
export SPOTIFY_CLIENT_SECRET=your_client_secret
make setup
```

That's it. GitHub Actions will sync your playlists daily at midnight UTC.

## Configuration

All settings live as GitHub Secrets and Variables in your fork. The `make setup` script pushes these automatically, but you can also set or change them manually in the GitHub UI.

**Secrets** (Settings → Secrets and variables → Actions → Secrets):

| Name | Value |
|---|---|
| `SPOTIFY_CLIENT_ID` | Your Spotify app's Client ID |
| `SPOTIFY_CLIENT_SECRET` | Your Spotify app's Client Secret |
| `TELEGRAM_BOT_TOKEN` | *(optional)* Telegram bot token for notifications |

**Variables** (Settings → Secrets and variables → Actions → Variables):

| Name | Value |
|---|---|
| `SPOTIFY_USER_ID` | Your Spotify user ID |
| `SPOTIFY_SOURCE_PLAYLISTS` | Comma-separated playlist names (empty = all) |
| `SPOTIFY_TARGET_PLAYLIST` | Target playlist name (default: Syncified) |
| `SPOTIFY_INCLUDE_EXTERNAL` | Include followed playlists (default: false) |
| `TELEGRAM_CHAT_ID` | *(optional)* Your Telegram chat ID for notifications |

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

1. Message [@BotFather](https://t.me/BotFather) on Telegram → `/newbot` → copy the token.

2. Add `TELEGRAM_BOT_TOKEN` as a GitHub Secret so the cron workflow can send notifications.

3. Run the bot locally to get your chat ID:
   ```bash
   export TELEGRAM_BOT_TOKEN=your_bot_token
   make bot
   ```
   Send `/start` to your bot. It will reply with your chat ID.

4. Add `TELEGRAM_CHAT_ID` as a GitHub Variable so the cron workflow knows where to send notifications.

5. Run the bot with `make bot` any time you want to change your playlist selection. When `GITHUB_TOKEN` is set, saving a selection in the bot automatically updates the `SPOTIFY_SOURCE_PLAYLISTS` GitHub Variable:
   ```bash
   GITHUB_TOKEN=your_pat make bot
   ```
   `GITHUB_TOKEN` is a [Personal Access Token](https://github.com/settings/tokens) with **Actions Variables write** permission.

## Local usage

```bash
make init

export SPOTIFY_CLIENT_ID=your_client_id
export SPOTIFY_CLIENT_SECRET=your_client_secret

make setup   # interactive setup, pushes to GitHub
make run     # run sync locally
make bot     # run the Telegram bot
```
