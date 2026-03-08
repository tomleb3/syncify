import os
import yaml
import requests

BASE_URL = 'https://api.spotify.com'


def _load_config() -> dict:
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'syncify.config.yml')
    if os.path.exists(config_path):
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    return {}


_config = _load_config()

USER_ID = os.environ.get('SPOTIFY_USER_ID') or _config.get('user_id', '')
TARGET_PLAYLIST_NAME = os.environ.get('SPOTIFY_TARGET_PLAYLIST') or _config.get('target_playlist', 'Syncified')


def get_access_token(client_id: str, client_secret: str) -> str:
    """Fetches the Spotify API access token using Client Credentials Flow."""
    try:
        response = requests.post(
            'https://accounts.spotify.com/api/token',
            data={'grant_type': 'client_credentials'},
            auth=(client_id, client_secret),
        )
        response.raise_for_status()
        token_data = response.json()
    except Exception as e:
        print(f"Error fetching access token: {e}")
        return ""

    return token_data['access_token']


# `include_external` = playlists not owned by the user.
def get_playlists(user_id: str, include_external: bool, access_token: str) -> list[dict]:
    """Fetches the user's playlists from Spotify API."""
    try:
        response = requests.get(
            f'{BASE_URL}/v1/users/{user_id}/playlists',
            headers={'Authorization': f'Bearer {access_token}'},
        )
        items = response.json().get('items', [])
    except Exception as e:
        print(f"Error fetching playlists: {e}")
        return []

    # Filter out target playlist.
    items = [item for item in items if item['name'] != TARGET_PLAYLIST_NAME]

    if include_external:
        return items

    return [item for item in items if item['owner']['id'] == user_id]


def get_playlist_by_name(user_id:str, playlist_name: str, access_token: str) -> dict | None:
    """Fetches a playlist by its name."""
    playlists = get_playlists(user_id, True, access_token)
    for playlist in playlists:
        if playlist['name'] == playlist_name:
            return playlist
    return None


def get_playlist_tracks(playlist_id: str, access_token: str) -> list[dict]:
    """Fetches the tracks of a given playlist."""
    try:
        response = requests.get(
            f'{BASE_URL}/v1/playlists/{playlist_id}/tracks',
            headers={'Authorization': f'Bearer {access_token}'},
        )
        response.raise_for_status()
        return response.json().get('items', [])
    except Exception as e:
        print(f"Error fetching playlist tracks: {e}")
        return []


def get_or_create_playlist(user_id: str, playlist_name: str, access_token: str) -> dict:
    """Fetches a playlist or creates it if it doesn't exist."""
    target_playlist = get_playlist_by_name(user_id, playlist_name, access_token)

    if target_playlist:
        return target_playlist


    try:
        response = requests.post(
            f'{BASE_URL}/v1/users/{user_id}/playlists',
            headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
            json={'name': playlist_name, 'public': False}
        )
        response.raise_for_status()
        target_playlist = response.json()
        return target_playlist
    except Exception as e:
        print(f"Error creating target playlist: {e}")
        return {}


def on_select_playlists(user_id: str, selected_playlists: list[dict], access_token: str) -> int:
    target_playlist = get_or_create_playlist(user_id, TARGET_PLAYLIST_NAME, access_token)
    if not target_playlist:
        return 0

    target_playlist_tracks = get_playlist_tracks(target_playlist['id'], access_token)
    existing_uris = {
        item['track']['uri']
        for item in target_playlist_tracks
        if item.get('track')
    }
    tracks_uris_to_add = []

    for playlist in selected_playlists:
        if not playlist:
            continue

        playlist_tracks = get_playlist_tracks(playlist['id'], access_token)
        for item in playlist_tracks:
            if not item.get('track'):
                continue
            uri = item['track']['uri']
            if uri not in existing_uris:
                tracks_uris_to_add.append(uri)
                existing_uris.add(uri)

    if not tracks_uris_to_add:
        print('No new tracks to add.')
        return 0

    try:
        # Spotify caps additions at 100 URIs per request.
        for i in range(0, len(tracks_uris_to_add), 100):
            chunk = tracks_uris_to_add[i:i + 100]
            response = requests.post(
                f'{BASE_URL}/v1/playlists/{target_playlist["id"]}/tracks',
                headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
                json={'uris': chunk},
            )
            response.raise_for_status()
        print(f"Added {len(tracks_uris_to_add)} tracks to playlist '{TARGET_PLAYLIST_NAME}'.")
        return len(tracks_uris_to_add)
    except Exception as e:
        print(f"Error adding tracks to target playlist: {e}")
        raise


def _notify_telegram(message: str) -> None:
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = _config.get('telegram', {}).get('chat_id')
    if not token or not chat_id:
        return
    try:
        requests.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown'},
            timeout=10,
        )
    except Exception:
        pass  # Notifications are best-effort.

def main() -> None:
    client_id = os.environ['SPOTIFY_CLIENT_ID']
    client_secret = os.environ['SPOTIFY_CLIENT_SECRET']

    include_external_env = os.environ.get('SPOTIFY_INCLUDE_EXTERNAL')
    include_external = (
        include_external_env.lower() == 'true'
        if include_external_env is not None
        else _config.get('include_external', False)
    )

    source_playlists_env = os.environ.get('SPOTIFY_SOURCE_PLAYLISTS')
    source_names_config: list[str] = _config.get('source_playlists', [])

    access_token = get_access_token(client_id, client_secret)
    all_playlists = get_playlists(USER_ID, include_external, access_token)

    if source_playlists_env:
        source_names = {name.strip() for name in source_playlists_env.split(',')}
        selected_playlists = [p for p in all_playlists if p['name'] in source_names]
    elif source_names_config:
        selected_playlists = [p for p in all_playlists if p['name'] in set(source_names_config)]
    else:
        selected_playlists = all_playlists

    try:
        count = on_select_playlists(USER_ID, selected_playlists, access_token)
        _notify_telegram(f'✅ *Syncify*: added {count} track(s) to _{TARGET_PLAYLIST_NAME}_.')
    except Exception as e:
        _notify_telegram(f'❌ *Syncify* sync failed: {e}')
        raise


if __name__ == '__main__':
    main()