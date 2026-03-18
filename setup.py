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


def fetch_playlists(access_token: str) -> list[dict]:
    response = requests.get(
        f'{BASE_URL}/v1/me/playlists',
        headers={'Authorization': f'Bearer {access_token}'},
    )
    response.raise_for_status()
    return response.json().get('items', [])


def prompt(question: str, default: str = '') -> str:
    suffix = f' [{default}]' if default else ''
    answer = input(f'{question}{suffix}: ').strip()
    return answer if answer else default


def prompt_yes_no(question: str, default: bool = False) -> bool:
    default_text = 'y' if default else 'n'
    return prompt(f'{question} (y/n)', default_text).lower() == 'y'


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


def _gh_secret_names(repo: str) -> set[str]:
    """Return the names of GitHub Actions secrets configured for a repo."""
    result = subprocess.run(
        ['gh', 'secret', 'list', '--repo', repo],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return set()

    secret_names: set[str] = set()
    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        if parts:
            secret_names.add(parts[0])
    return secret_names


def _gh_push(repo: str, secrets: dict[str, str], variables: dict[str, str | None]) -> None:
    """Push secrets and variables to GitHub via the gh CLI."""
    def _run(args: list[str], value: str = '') -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ['gh'] + args + ['--repo', repo],
            input=value, text=True, capture_output=True,
        )

    print()
    all_ok = True
    for name, value in secrets.items():
        result = _run(['secret', 'set', name], value)
        ok = result.returncode == 0
        print(f'  {"✅" if ok else "❌"} secret  {name}')
        all_ok = all_ok and ok

    for name, value in variables.items():
        if value is None:
            result = _run(['variable', 'delete', name])
            ok = result.returncode == 0 or 'not found' in result.stderr.lower()
            action = 'cleared'
        else:
            result = _run(['variable', 'set', name, '--body', value])
            ok = result.returncode == 0
            action = 'set'
        print(f'  {"✅" if ok else "❌"} variable {name} ({action})')
        all_ok = all_ok and ok

    if not all_ok:
        print('\n  Some values failed. Make sure `gh` is installed and authenticated (`gh auth login`).')


def main() -> None:
    print('=== Syncify Setup ===\n')

    client_id = os.environ.get('SPOTIFY_CLIENT_ID') or prompt('Spotify Client ID')
    client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET') or prompt('Spotify Client Secret')

    if not all([client_id, client_secret]):
        print('Error: Client ID and Client Secret are required.')
        sys.exit(1)

    print('\nAuthorizing with Spotify...')
    print('Make sure http://127.0.0.1:8888/callback is in your Spotify app\'s Redirect URIs.')
    try:
        access_token, refresh_token = authorize(client_id, client_secret)
        all_playlists = fetch_playlists(access_token)
    except requests.HTTPError as e:
        print(f'Error: {e}')
        sys.exit(1)

    if not all_playlists:
        print('No playlists found.')
        sys.exit(1)

    # Determine user ID from the first owned playlist.
    user_id = all_playlists[0]['owner']['id']
    owned = [p for p in all_playlists if p['owner']['id'] == user_id]
    external = [p for p in all_playlists if p['owner']['id'] != user_id]

    include_external = prompt_yes_no('Include playlists you follow but don\'t own?')

    playlists_to_show = owned + (external if include_external else [])
    playlist_names = [p['name'] for p in playlists_to_show]

    selected_names = choose_from_list(playlist_names, 'playlists')
    selected_ids = [p['id'] for p in playlists_to_show if p['name'] in set(selected_names)]

    # Target playlist: pick an existing one or create a new one.
    print('\nWhich playlist should Syncify merge tracks into?')
    owned_names = [p['name'] for p in owned]
    for i, name in enumerate(owned_names, 1):
        print(f'  {i:2}. {name}')
    print(f'  {len(owned_names) + 1:2}. [Create new playlist]')
    print()

    while True:
        raw = input('Enter number: ').strip()
        try:
            choice = int(raw)
            if 1 <= choice <= len(owned_names) + 1:
                break
        except ValueError:
            pass
        print(f'  Invalid input. Enter a number between 1 and {len(owned_names) + 1}.')

    if choice <= len(owned_names):
        target_playlist_id = owned[choice - 1]['id']
    else:
        name = prompt('New playlist name', 'Syncified')
        try:
            response = requests.post(
                f'{BASE_URL}/v1/users/{user_id}/playlists',
                headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
                json={'name': name, 'description': '', 'public': False},
            )
            response.raise_for_status()
            target_playlist_id = response.json()['id']
            print(f'Created playlist "{name}" ({target_playlist_id})')
        except requests.HTTPError as e:
            print(f'Error creating playlist: {e}')
            sys.exit(1)

    remove_missing = prompt_yes_no(
        'Remove tracks from the target playlist when they are removed from the source playlists?'
    )

    # ── GitHub push ───────────────────────────────────────────────────────────
    detected_repo = _detect_gh_repo()
    repo = prompt('GitHub repo to push secrets/variables to (owner/repo)', detected_repo)

    if repo:
        existing_secret_names = _gh_secret_names(repo)
        secrets_to_push = {
            'SPOTIFY_REFRESH_TOKEN': refresh_token,
        }

        if 'SPOTIFY_CLIENT_ID' in existing_secret_names:
            overwrite_client_id = prompt_yes_no('Overwrite existing GitHub secret SPOTIFY_CLIENT_ID?')
            if overwrite_client_id:
                secrets_to_push['SPOTIFY_CLIENT_ID'] = client_id
        else:
            secrets_to_push['SPOTIFY_CLIENT_ID'] = client_id

        if 'SPOTIFY_CLIENT_SECRET' in existing_secret_names:
            overwrite_client_secret = prompt_yes_no('Overwrite existing GitHub secret SPOTIFY_CLIENT_SECRET?')
            if overwrite_client_secret:
                secrets_to_push['SPOTIFY_CLIENT_SECRET'] = client_secret
        else:
            secrets_to_push['SPOTIFY_CLIENT_SECRET'] = client_secret

        source_playlist_ids_str = ','.join(selected_ids) if selected_names != playlist_names else None
        print(f'\nPushing to {repo}...')
        _gh_push(
            repo=repo,
            secrets=secrets_to_push,
            variables={
                'SPOTIFY_TARGET_PLAYLIST_ID': target_playlist_id,
                'SPOTIFY_SOURCE_PLAYLIST_IDS': source_playlist_ids_str,
                'SPOTIFY_INCLUDE_EXTERNAL': 'true' if include_external else None,
                'SPOTIFY_REMOVE_MISSING': 'true' if remove_missing else None,
            },
        )
    else:
        print('Skipping GitHub push.')

    print('\nNext steps:')
    if not repo:
        print('  1. Add SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET as GitHub Secrets.')
        print('     (Settings → Secrets and variables → Actions → Secrets)')
    print('  - The workflow will run on the configured schedule.')
    print('  - Re-run `make setup` any time you want to change playlist selection or sync mode.')


if __name__ == '__main__':
    main()
