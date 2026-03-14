"""
Interactive setup for Syncify.
Fetches your Spotify playlists, lets you pick which ones to sync,
and pushes everything to GitHub Secrets/Variables.
Requires SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in the environment.
"""

import os
import re
import subprocess
import sys
import requests

from auth import authorize

BASE_URL = 'https://api.spotify.com'


def fetch_playlists(user_id: str, access_token: str) -> list[dict]:
    response = requests.get(
        f'{BASE_URL}/v1/users/{user_id}/playlists',
        headers={'Authorization': f'Bearer {access_token}'},
    )
    response.raise_for_status()
    return response.json().get('items', [])


def prompt(question: str, default: str = '') -> str:
    suffix = f' [{default}]' if default else ''
    answer = input(f'{question}{suffix}: ').strip()
    return answer if answer else default


def choose_from_list(items: list[str], label: str) -> list[str]:
    print(f'\nAvailable {label}:')
    for i, item in enumerate(items, 1):
        print(f'  {i:2}. {item}')
    print()

    while True:
        raw = input('Enter numbers to select (e.g. 1,3,5) or press Enter to select ALL: ').strip()
        if not raw:
            return items
        try:
            indices = [int(n.strip()) for n in raw.split(',')]
            if all(1 <= i <= len(items) for i in indices):
                return [items[i - 1] for i in indices]
        except ValueError:
            pass
        print(f'  Invalid input. Enter comma-separated numbers between 1 and {len(items)}.')


def _detect_gh_repo() -> str:
    """Detect owner/repo from git remote origin URL."""
    try:
        result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            capture_output=True, text=True, check=True,
        )
        url = result.stdout.strip()
        # https://github.com/owner/repo(.git)
        m = re.search(r'github\.com[:/](.+?/[^/]+?)(?:\.git)?$', url)
        if m:
            return m.group(1)
    except subprocess.CalledProcessError:
        pass
    return ''


def _gh_push(repo: str, secrets: dict[str, str], variables: dict[str, str]) -> None:
    """Push secrets and variables to GitHub via the gh CLI."""
    def _run(args: list[str], value: str) -> bool:
        result = subprocess.run(
            ['gh'] + args + ['--repo', repo],
            input=value, text=True, capture_output=True,
        )
        return result.returncode == 0

    print()
    all_ok = True
    for name, value in secrets.items():
        ok = _run(['secret', 'set', name], value)
        print(f'  {"✅" if ok else "❌"} secret  {name}')
        all_ok = all_ok and ok

    for name, value in variables.items():
        ok = _run(['variable', 'set', name, '--body', value], '')
        print(f'  {"✅" if ok else "❌"} variable {name}')
        all_ok = all_ok and ok

    if not all_ok:
        print('\n  Some values failed. Make sure `gh` is installed and authenticated (`gh auth login`).')


def main() -> None:
    print('=== Syncify Setup ===\n')

    client_id = os.environ.get('SPOTIFY_CLIENT_ID') or prompt('Spotify Client ID')
    client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET') or prompt('Spotify Client Secret')
    user_id = prompt('Spotify User ID (the segment after /user/ in your profile URL)')

    if not all([client_id, client_secret, user_id]):
        print('Error: Client ID, Client Secret, and User ID are all required.')
        sys.exit(1)

    print('\nAuthorizing with Spotify...')
    print('Make sure http://127.0.0.1:8888/callback is in your Spotify app\'s Redirect URIs.')
    try:
        access_token, refresh_token = authorize(client_id, client_secret)
        all_playlists = fetch_playlists(user_id, access_token)
    except requests.HTTPError as e:
        print(f'Error: {e}')
        sys.exit(1)

    if not all_playlists:
        print('No playlists found for this user.')
        sys.exit(1)

    owned = [p for p in all_playlists if p['owner']['id'] == user_id]
    external = [p for p in all_playlists if p['owner']['id'] != user_id]

    include_external = prompt('Include playlists you follow but don\'t own? (y/n)', 'n').lower() == 'y'

    playlists_to_show = owned + (external if include_external else [])
    playlist_names = [p['name'] for p in playlists_to_show]

    selected_names = choose_from_list(playlist_names, 'playlists')

    target_playlist = prompt('\nName for the target (merged) playlist', 'Syncified')

    # ── GitHub push ───────────────────────────────────────────────────────────
    detected_repo = _detect_gh_repo()
    repo = prompt('GitHub repo to push secrets/variables to (owner/repo)', detected_repo)

    if repo:
        source_playlists_str = ','.join(selected_names) if selected_names != playlist_names else ''
        print(f'\nPushing to {repo}...')
        _gh_push(
            repo=repo,
            secrets={
                'SPOTIFY_CLIENT_ID': client_id,
                'SPOTIFY_CLIENT_SECRET': client_secret,
                'SPOTIFY_REFRESH_TOKEN': refresh_token,
            },
            variables={
                k: v for k, v in {
                    'SPOTIFY_USER_ID': user_id,
                    'SPOTIFY_TARGET_PLAYLIST': target_playlist if target_playlist != 'Syncified' else '',
                    'SPOTIFY_SOURCE_PLAYLISTS': source_playlists_str,
                    'SPOTIFY_INCLUDE_EXTERNAL': 'true' if include_external else '',
                }.items() if v  # skip empty/default values
            },
        )
    else:
        print('Skipping GitHub push.')

    print('\nNext steps:')
    if not repo:
        print('  1. Add SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET as GitHub Secrets.')
        print('     (Settings → Secrets and variables → Actions → Secrets)')
    print('  - The workflow will run on the configured schedule.')
    print('  - To change playlists from your phone: make bot (requires TELEGRAM_BOT_TOKEN).')


if __name__ == '__main__':
    main()
