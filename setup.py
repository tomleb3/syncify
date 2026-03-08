"""
Interactive setup for Syncify.
Run once locally to generate syncify.config.yml.
Requires SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET to be set in the environment.
"""

import os
import sys
import requests
import yaml

BASE_URL = 'https://api.spotify.com'


def get_access_token(client_id: str, client_secret: str) -> str:
    response = requests.post(
        'https://accounts.spotify.com/api/token',
        data={'grant_type': 'client_credentials'},
        auth=(client_id, client_secret),
    )
    response.raise_for_status()
    return response.json()['access_token']


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


def main() -> None:
    print('=== Syncify Setup ===\n')

    client_id = os.environ.get('SPOTIFY_CLIENT_ID') or prompt('Spotify Client ID')
    client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET') or prompt('Spotify Client Secret')
    user_id = prompt('Spotify User ID (the segment after /user/ in your profile URL)')

    if not all([client_id, client_secret, user_id]):
        print('Error: Client ID, Client Secret, and User ID are all required.')
        sys.exit(1)

    print('\nFetching your playlists...')
    try:
        access_token = get_access_token(client_id, client_secret)
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

    config = {
        'user_id': user_id,
        'target_playlist': target_playlist,
        'source_playlists': selected_names if selected_names != playlist_names else [],
        'include_external': include_external,
    }

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'syncify.config.yml')
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f'\nConfig saved to {config_path}')
    print('\nNext steps:')
    print('  1. Commit syncify.config.yml to your fork.')
    print('  2. Add SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET as GitHub Secrets.')
    print('     (Settings → Secrets and variables → Actions → Secrets)')
    print('  3. The workflow will run on the configured schedule, or trigger it manually.')


if __name__ == '__main__':
    main()
