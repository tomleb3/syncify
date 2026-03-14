import os
import requests

BASE_URL = 'https://api.spotify.com'

TARGET_PLAYLIST_NAME = os.environ.get('SPOTIFY_TARGET_PLAYLIST') or 'Syncified'


def get_current_user_id(access_token: str) -> str:
    """Fetches the current user's Spotify ID from the token."""
    try:
        response = requests.get(
            f'{BASE_URL}/v1/me',
            headers={'Authorization': f'Bearer {access_token}'},
        )
        response.raise_for_status()
        return response.json()['id']
    except Exception as e:
        print(f"Error fetching current user: {e}")
        raise


def get_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    """Fetches a fresh Spotify access token using the refresh token."""
    try:
        response = requests.post(
            'https://accounts.spotify.com/api/token',
            data={'grant_type': 'refresh_token', 'refresh_token': refresh_token},
            auth=(client_id, client_secret),
        )
        response.raise_for_status()
        token_data = response.json()
    except Exception as e:
        print(f"Error fetching access token: {e}")
        raise

    return token_data['access_token']


# `include_external` = playlists not owned by the user.
def get_playlists(user_id: str, include_external: bool, access_token: str) -> list[dict]:
    """Fetches the user's playlists from Spotify API."""
    items: list[dict] = []
    url: str | None = f'{BASE_URL}/v1/me/playlists?limit=50'
    try:
        while url:
            response = requests.get(
                url,
                headers={'Authorization': f'Bearer {access_token}'},
            )
            response.raise_for_status()
            data = response.json()
            items.extend(data.get('items', []))
            url = data.get('next')
    except Exception as e:
        print(f"Error fetching playlists: {e}")
        raise

    # Filter out target playlist.
    items = [item for item in items if item['name'] != TARGET_PLAYLIST_NAME]

    if include_external:
        return items

    return [item for item in items if item['owner']['id'] == user_id]


def get_playlist_by_name(playlist_name: str, access_token: str) -> dict | None:
    """Fetches a playlist by name, searching all playlists including the target."""
    url: str | None = f'{BASE_URL}/v1/me/playlists?limit=50'
    try:
        while url:
            response = requests.get(url, headers={'Authorization': f'Bearer {access_token}'})
            response.raise_for_status()
            data = response.json()
            for playlist in data.get('items', []):
                if playlist['name'] == playlist_name:
                    return playlist
            url = data.get('next')
    except Exception as e:
        print(f"Error searching for playlist '{playlist_name}': {e}")
        raise
    return None


def get_playlist_tracks(playlist_id: str, access_token: str) -> list[dict]:
    """Fetches all tracks of a given playlist, handling pagination."""
    items: list[dict] = []
    url: str | None = f'{BASE_URL}/v1/playlists/{playlist_id}/tracks?limit=100'
    try:
        while url:
            response = requests.get(
                url,
                headers={'Authorization': f'Bearer {access_token}'},
            )
            response.raise_for_status()
            data = response.json()
            items.extend(data.get('items', []))
            url = data.get('next')
        return items
    except Exception as e:
        print(f"Error fetching playlist tracks: {e}")
        raise


def get_or_create_playlist(user_id: str, playlist_name: str, access_token: str) -> dict:
    """Fetches a playlist or creates it if it doesn't exist."""
    target_playlist = get_playlist_by_name(playlist_name, access_token)

    if target_playlist:
        return target_playlist

    try:
        response = requests.post(
            f'{BASE_URL}/v1/users/{user_id}/playlists',
            headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
            json={'name': playlist_name, 'description': '', 'public': False}
        )
        response.raise_for_status()
        target_playlist = response.json()
        return target_playlist
    except Exception as e:
        print(f"Error creating target playlist: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response body: {e.response.text}")
        raise


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
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
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
    include_external = os.environ.get('SPOTIFY_INCLUDE_EXTERNAL', '').lower() == 'true'

    refresh_token = os.environ['SPOTIFY_REFRESH_TOKEN']
    access_token = get_access_token(client_id, client_secret, refresh_token)
    user_id = get_current_user_id(access_token)
    all_playlists = get_playlists(user_id, include_external, access_token)

    source_playlists_env = os.environ.get('SPOTIFY_SOURCE_PLAYLISTS', '')
    if source_playlists_env:
        source_names = {name.strip() for name in source_playlists_env.split(',')}
        selected_playlists = [p for p in all_playlists if p['name'] in source_names]
    else:
        selected_playlists = all_playlists

    try:
        count = on_select_playlists(user_id, selected_playlists, access_token)
        _notify_telegram(f'✅ *Syncify*: added {count} track(s) to _{TARGET_PLAYLIST_NAME}_.')
    except Exception as e:
        _notify_telegram(f'❌ *Syncify* sync failed: {e}')
        raise


if __name__ == '__main__':
    main()