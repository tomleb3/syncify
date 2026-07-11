# Syncify

Automatically merges tracks from multiple Spotify playlists into one target playlist and runs through GitHub Actions.

## Use This Template

1. Click **Use this template** and create your own repo.
2. If you want your sync history and cron runs private, make that repo **private**.

The source/template repo stays manual-only. Add scheduled runs only in the repo that should own the run history.

## Setup

1. Create a Spotify app in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. Add `http://127.0.0.1:8888/callback` as a redirect URI.
3. Clone your new repo.
4. Run:

```bash
make init
make setup
```

`make setup` authorizes Spotify, lets you choose source and target playlists, and pushes the required GitHub Secrets and Variables.

If you only need to refresh the Spotify authorization later, run `make auth`. It uses the same setup script and only updates `SPOTIFY_REFRESH_TOKEN`.

## Schedule

If you want automatic syncs, uncomment the `schedule` block in `.github/workflows/syncify.yml` in your repo and set your cron.

Example:

```yaml
schedule:
  - cron: '0 0 * * *'
```

If the repo running the workflow is public, its Actions history is public too.

## Optional: Keep Your Repo Updated

Repos created from a template are standalone, so GitHub's **Sync fork** button does not apply.

To pull future changes from your actual template/source repo, add it as a remote and merge from it:

```bash
git remote add template https://github.com/tomleb3/syncify.git
git fetch template
git merge template/master
git push origin HEAD
```

If the template/source repo changes `.github/workflows/syncify.yml`, make sure the `schedule` block is still uncommented in your repo.

## Commands

```bash
make init
make setup
make auth
make run
SYNCIFY_GH_REPO=owner/repo make run
```
