import os
import requests

BASE_URL = 'https://api.spotify.com'

TARGET_PLAYLIST_ID = os.environ['SPOTIFY_TARGET_PLAYLIST_ID']


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
    items = [item for item in items if item['id'] != TARGET_PLAYLIST_ID]

    if include_external:
        return items

    return [item for item in items if item['owner']['id'] == user_id]


def get_playlist_by_id(playlist_id: str, access_token: str) -> dict:
    """Fetches a playlist by its Spotify ID."""
    try:
        response = requests.get(
            f'{BASE_URL}/v1/playlists/{playlist_id}',
            headers={'Authorization': f'Bearer {access_token}'},
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching playlist '{playlist_id}': {e}")
        raise


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


def sync_selected_playlists(
    selected_playlists: list[dict],
    access_token: str,
    remove_missing: bool,
) -> tuple[int, int]:
    target_playlist = get_playlist_by_id(TARGET_PLAYLIST_ID, access_token)

    target_playlist_tracks = get_playlist_tracks(target_playlist['id'], access_token)
    existing_uris = {
        item['track']['uri']
        for item in target_playlist_tracks
        if item.get('track')
    }
    desired_uris: list[str] = []
    desired_uri_set: set[str] = set()

    for playlist in selected_playlists:
        if not playlist:
            continue

        playlist_tracks = get_playlist_tracks(playlist['id'], access_token)
        for item in playlist_tracks:
            if not item.get('track'):
                continue
            uri = item['track']['uri']
            if uri not in desired_uri_set:
                desired_uris.append(uri)
                desired_uri_set.add(uri)

    tracks_uris_to_add = [uri for uri in desired_uris if uri not in existing_uris]
    tracks_uris_to_remove = []
    if remove_missing:
        tracks_uris_to_remove = [uri for uri in existing_uris if uri not in desired_uri_set]

    if not tracks_uris_to_add and not tracks_uris_to_remove:
        print('No changes needed.')
        return 0, 0

    try:
        removed_count = 0
        for i in range(0, len(tracks_uris_to_remove), 100):
            chunk = tracks_uris_to_remove[i:i + 100]
            response = requests.delete(
                f'{BASE_URL}/v1/playlists/{target_playlist["id"]}/tracks',
                headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
                json={'tracks': [{'uri': uri} for uri in chunk]},
            )
            response.raise_for_status()
            removed_count += len(chunk)

        # Spotify caps additions at 100 URIs per request.
        added_count = 0
        for i in range(0, len(tracks_uris_to_add), 100):
            chunk = tracks_uris_to_add[i:i + 100]
            response = requests.post(
                f'{BASE_URL}/v1/playlists/{target_playlist["id"]}/tracks',
                headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
                json={'uris': chunk},
            )
            response.raise_for_status()
            added_count += len(chunk)

        action = 'Updated'
        if remove_missing:
            print(
                f"{action} playlist '{target_playlist['name']}': "
                f"added {added_count}, removed {removed_count}."
            )
        else:
            print(f"Added {added_count} tracks to playlist '{target_playlist['name']}'.")
        return added_count, removed_count
    except Exception as e:
        print(f"Error updating target playlist: {e}")
        raise

def main() -> None:
    client_id = os.environ['SPOTIFY_CLIENT_ID']
    client_secret = os.environ['SPOTIFY_CLIENT_SECRET']
    include_external = os.environ.get('SPOTIFY_INCLUDE_EXTERNAL', '').lower() == 'true'
    remove_missing = os.environ.get('SPOTIFY_REMOVE_MISSING', '').lower() == 'true'

    refresh_token = os.environ['SPOTIFY_REFRESH_TOKEN']
    access_token = get_access_token(client_id, client_secret, refresh_token)
    user_id = get_current_user_id(access_token)
    all_playlists = get_playlists(user_id, include_external, access_token)

    source_playlist_ids_env = os.environ.get('SPOTIFY_SOURCE_PLAYLIST_IDS', '')
    if source_playlist_ids_env:
        source_ids = {pid.strip() for pid in source_playlist_ids_env.split(',')}
        selected_playlists = [p for p in all_playlists if p['id'] in source_ids]
    else:
        selected_playlists = all_playlists

    sync_selected_playlists(selected_playlists, access_token, remove_missing)


if __name__ == '__main__':
    main()