# Syncify

Automatically merges tracks from multiple Spotify playlists into a single target playlist, deduplicating as it goes. Designed to run as a scheduled GitHub Actions workflow.

## How it works

Syncify reads your chosen source playlists and adds any tracks not already present into a single target playlist (default name: **Syncified**). It uses the [Spotify Web API](https://developer.spotify.com/documentation/web-api) with the Client Credentials flow.

---

## Setup

### 1. Create a Spotify Developer App

1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and create a new app.
2. Note down the **Client ID** and **Client Secret**.

### 2. Clone (don't fork) your own copy

```bash
git clone https://github.com/yourusername/syncify
cd syncify
```

The repo includes:
- **`syncify.config.yml.example`** — committed, shows the config structure
- **`syncify.config.yml`** — gitignored, your personal config (created on first use)

Your personal `syncify.config.yml` will never appear in git history.

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

**Important:** `syncify.config.yml` is in `.gitignore` — it will never be committed or pushed. Your config stays private.

---

## Deployment

### Local / VPS (cron job)

After `make setup`, your `syncify.config.yml` exists locally and the sync works directly:

```bash
crontab -e
```

Add a line like:
```bash
0 0 * * * cd /path/to/syncify && export SPOTIFY_CLIENT_ID=... SPOTIFY_CLIENT_SECRET=... && make run
```

Or use systemd timer for more control. `syncify.config.yml` is local — no secrets to manage in git.

### GitHub Actions (scheduled cron)

Since `syncify.config.yml` is gitignored, it won't exist in the GitHub runner. You have two options:

**Option A: Use GitHub Secrets/Variables (recommended)**

The script falls back to environment variables. Set these as GitHub Secrets/Variables:

1. Go to your repo: **Settings → Secrets and variables → Actions → Secrets**

| Name | Value |
|---|---|
| `SPOTIFY_CLIENT_ID` | Your Spotify app's Client ID |
| `SPOTIFY_CLIENT_SECRET` | Your Spotify app's Client Secret |

2. Go to **Settings → Secrets and variables → Actions → Variables** (non-sensitive):

| Name | Value |
|---|---|
| `SPOTIFY_USER_ID` | your_user_id |
| `SPOTIFY_SOURCE_PLAYLISTS` | Playlist A,Playlist B |
| `SPOTIFY_TARGET_PLAYLIST` | Syncified |
| `SPOTIFY_INCLUDE_EXTERNAL` | false |

The workflow already reads these:
```yaml
      - name: Run Syncify
        env:
          SPOTIFY_CLIENT_ID: ${{ secrets.SPOTIFY_CLIENT_ID }}
          SPOTIFY_CLIENT_SECRET: ${{ secrets.SPOTIFY_CLIENT_SECRET }}
          SPOTIFY_USER_ID: ${{ vars.SPOTIFY_USER_ID }}
          SPOTIFY_SOURCE_PLAYLISTS: ${{ vars.SPOTIFY_SOURCE_PLAYLISTS }}
          SPOTIFY_TARGET_PLAYLIST: ${{ vars.SPOTIFY_TARGET_PLAYLIST }}
          SPOTIFY_INCLUDE_EXTERNAL: ${{ vars.SPOTIFY_INCLUDE_EXTERNAL }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
        run: uv run python syncify.py
```

**Option B: Store config as a secret**

If you prefer to keep all config together, encode `syncify.config.yml` as a secret and write it at runtime:

1. Create `syncify.config.yml` locally (via `make setup`)
2. Encode it: `cat syncify.config.yml | base64`
3. Add as GitHub Secret: `SYNCIFY_CONFIG_B64`
4. Update workflow to decode it:
```yaml
      - name: Write config
        env:
          CONFIG_B64: ${{ secrets.SYNCIFY_CONFIG_B64 }}
        run: echo "$CONFIG_B64" | base64 -d > syncify.config.yml

      - name: Run Syncify
        env:
          SPOTIFY_CLIENT_ID: ${{ secrets.SPOTIFY_CLIENT_ID }}
          SPOTIFY_CLIENT_SECRET: ${{ secrets.SPOTIFY_CLIENT_SECRET }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
        run: uv run python syncify.py
```

**Which to choose?**
- **Option A** if you want transparency and granular control of each setting
- **Option B** if you want everything bundled (feels more like the local workflow)

---

## How config is loaded

The script uses this priority (first match wins):

1. **Environment variables** (`SPOTIFY_USER_ID`, `SPOTIFY_SOURCE_PLAYLISTS`, etc.)
2. **`syncify.config.yml`** (your personal config, gitignored)
3. **`syncify.config.yml.example`** (fallback/reference only)
4. **Built-in defaults** (empty lists, "Syncified" for target playlist)

**Why this matters:**
- **Locally**: `make setup` creates `syncify.config.yml`, which is read automatically
- **GitHub Actions**: `syncify.config.yml` doesn't exist (gitignored), so env vars from Secrets/Variables are used
- **VPS/server**: Same as local — the config file exists on the machine you set it up on

Customize the workflow schedule in [`.github/workflows/syncify.yml`](.github/workflows/syncify.yml) if needed:

```yaml
schedule:
  - cron: '0 0 * * *'   # daily at midnight UTC
```

Use [crontab.guru](https://crontab.guru) to build expressions.

---

## Run it

**Locally:**
```bash
make run
```

**Telegram bot** (interactive playlist selection + live sync):
```bash
TELEGRAM_BOT_TOKEN=your_token GITHUB_TOKEN=your_pat make bot
```

`GITHUB_TOKEN` is a [Personal Access Token](https://github.com/settings/tokens) with **Actions Variables write** permission. When set, saving a playlist selection in the bot immediately updates the `SPOTIFY_SOURCE_PLAYLISTS` GitHub Variable — so the next scheduled cron run picks it up automatically.

**Full automated flow:**
1. Local cron or GitHub Actions calls `make run`
2. Reads your config from `syncify.config.yml` (ignored, stays private)
3. Or overrides via env vars
4. On success/failure, sends a Telegram notification if configured

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
   This file stays local (it's in `.gitignore`).

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
