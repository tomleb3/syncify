import requests

BASE_URL = 'https://api.spotify.com'
USER_ID = '' # TODO: dynamic
TARGET_PLAYLIST_NAME = 'Syncified' # TODO: dynamic


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
            f'{BASE_URL}/v1/users/f{user_id}/playlists',
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


def on_select_playlists(user_id: str, selected_playlists: list[dict], access_token: str) -> None:
    target_playlist = get_or_create_playlist(user_id, TARGET_PLAYLIST_NAME, access_token)
    target_playlist_tracks = get_playlist_tracks(target_playlist['id'], access_token)
    target_playlist_tracks_uris = [track for tracks in target_playlist_tracks for track in tracks['track']['uri']]
    tracks_uris_to_add = []

    for playlist in selected_playlists:
        if not playlist:
            continue

        playlist_tracks_uris = [track for tracks in playlist['tracks']['items'] for track in tracks['track']['uri']]
        for track_uri in playlist_tracks_uris:
            if track_uri not in target_playlist_tracks_uris:
                tracks_uris_to_add.append(track_uri)

    try:
        response = requests.post(
            f'{BASE_URL}/v1/playlists/{target_playlist["id"]}/tracks',
            headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
            json={'uris': tracks_uris_to_add},
        )
        response.raise_for_status()
        print(f"Added {len(tracks_uris_to_add)} tracks to playlist '{TARGET_PLAYLIST_NAME}'.")
    except Exception as e:
        print(f"Error adding tracks to target playlist: {e}")

def main() -> None:
    # TODO: `include_external` flag?
    access_token = get_access_token('', '')  # TODO: dynamic
    playlists = get_playlists(USER_ID, False, access_token)
    selected_playlists: list[dict] = []  # TODO: dynamic selection logic
    on_select_playlists(USER_ID, selected_playlists, access_token)

main()