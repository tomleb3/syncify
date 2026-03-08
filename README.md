# Syncify

Automatically merges tracks from multiple Spotify playlists into a single target playlist, deduplicating as it goes. Designed to run as a scheduled GitHub Actions workflow.

## How it works

Syncify reads your chosen source playlists and adds any tracks not already present into a single target playlist (default name: **Syncified**). It uses the [Spotify Web API](https://developer.spotify.com/documentation/web-api) with the Client Credentials flow.

---

## Setup

### 1. Create a Spotify Developer App

1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and create a new app.
2. Note down the **Client ID** and **Client Secret**.

### 2. Fork this repository

Click **Fork** at the top of this page to create your own copy.

### 3. Run interactive setup

> This fetches your real Spotify playlists and lets you pick which ones to sync.

```bash
make init
export SPOTIFY_CLIENT_ID=your_client_id
export SPOTIFY_CLIENT_SECRET=your_client_secret
make setup
```

The script will:
1. Ask for your Spotify User ID
2. Fetch your playlists from Spotify
3. Let you select which ones to sync (by number)
4. Ask for a target playlist name and other options
5. Write `syncify.config.yml` with your choices

Commit `syncify.config.yml` when done — this is the only file that needs to go into your fork.

### 4. Add GitHub Secrets

In your fork: **Settings → Secrets and variables → Actions → Secrets**

| Name | Value |
|---|---|
| `SPOTIFY_CLIENT_ID` | Your Spotify app's Client ID |
| `SPOTIFY_CLIENT_SECRET` | Your Spotify app's Client Secret |

### 5. Adjust the schedule (optional)

The workflow runs **daily at midnight UTC** by default. To change this, edit the `cron` line in [`.github/workflows/syncify.yml`](.github/workflows/syncify.yml):

```yaml
schedule:
  - cron: '0 0 * * *'   # daily at midnight UTC
```

Use [crontab.guru](https://crontab.guru) to build your preferred expression.

### 6. Run it

- **Automatic**: the workflow runs on the configured schedule.
- **Manual**: go to **Actions → Syncify → Run workflow** to trigger it immediately.

## Telegram bot (optional)

The Telegram bot lets you manage playlist selection interactively and receive a success/failure message after every sync — whether triggered manually via Telegram or by the scheduled cron job.

### Bot commands

| Command | Description |
|---|---|
| `/start` | Show help (also prints your chat ID for first-time setup) |
| `/playlists` | Show all your Spotify playlists as a toggleable inline keyboard, then save and/or sync |
| `/sync` | Run sync immediately using the current config |

### Setup

1. **Create a bot**: message [@BotFather](https://t.me/BotFather) on Telegram → `/newbot` → copy the token.

2. **Add the bot token as a GitHub Secret** (`TELEGRAM_BOT_TOKEN`) so the cron workflow can send notifications.

3. **Find your chat ID**:
   ```bash
   export TELEGRAM_BOT_TOKEN=your_bot_token
   make bot
   ```
   Message your bot on Telegram and send `/start`. It will reply with your chat ID.

4. **Add the chat ID to `syncify.config.yml`**:
   ```yaml
   telegram:
     chat_id: "123456789"
   ```
   Commit and push.

5. **Run the bot locally** (or on a VPS/server) with `make bot` any time you want to change your playlist selection. The cron job does not need the bot running — it just sends a notification when done.

---



```bash
make init

export SPOTIFY_CLIENT_ID=your_client_id
export SPOTIFY_CLIENT_SECRET=your_client_secret
export TELEGRAM_BOT_TOKEN=your_bot_token  # optional

make setup   # interactive — generates syncify.config.yml
make bot     # run the Telegram bot for interactive playlist selection
make run     # run the sync immediately
```
