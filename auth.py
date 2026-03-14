"""
One-time Spotify OAuth authorization.

Obtains a refresh token with the scopes required by Syncify and optionally
pushes it to GitHub Secrets so the sync workflow can use it.

Run with: make auth

Before running, add https://localhost:8888/callback to your Spotify app's
Redirect URIs (Spotify Developer Dashboard → your app → Edit Settings).
"""

import os
import re
import subprocess
import sys
import urllib.parse
import webbrowser

import requests

REDIRECT_URI = 'https://localhost:8888/callback'
SCOPES = 'playlist-read-private playlist-modify-private'


def authorize(client_id: str, client_secret: str) -> tuple[str, str]:
    """Run the OAuth Authorization Code flow. Returns (access_token, refresh_token)."""
    auth_url = 'https://accounts.spotify.com/authorize?' + urllib.parse.urlencode({
        'client_id': client_id,
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'scope': SCOPES,
    })
    print('Opening browser for Spotify authorization...')
    print(f'If it does not open automatically, visit:\n  {auth_url}\n')
    webbrowser.open(auth_url)

    print('After authorizing, your browser will redirect to localhost and show a connection error.')
    print('Copy the full URL from the address bar and paste it here.')
    redirected_url = input('Redirected URL: ').strip()

    params = urllib.parse.parse_qs(urllib.parse.urlparse(redirected_url).query)
    if 'error' in params:
        print(f'Authorization denied: {params["error"][0]}')
        sys.exit(1)
    if 'code' not in params:
        print('Error: no authorization code found in URL.')
        sys.exit(1)
    auth_code = params['code'][0]

    response = requests.post(
        'https://accounts.spotify.com/api/token',
        data={
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': REDIRECT_URI,
        },
        auth=(client_id, client_secret),
    )
    response.raise_for_status()
    data = response.json()
    return data['access_token'], data['refresh_token']


def _detect_gh_repo() -> str:
    try:
        result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            capture_output=True, text=True, check=True,
        )
        m = re.search(r'github\.com[:/](.+?/[^/]+?)(?:\.git)?$', result.stdout.strip())
        if m:
            return m.group(1)
    except subprocess.CalledProcessError:
        pass
    return ''


def main() -> None:
    print('=== Syncify Auth ===')
    print('Make sure https://localhost:8888/callback is added to your Spotify app\'s Redirect URIs.\n')

    client_id = os.environ.get('SPOTIFY_CLIENT_ID') or input('Spotify Client ID: ').strip()
    client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET') or input('Spotify Client Secret: ').strip()

    if not client_id or not client_secret:
        print('Error: Client ID and Client Secret are required.')
        sys.exit(1)

    _, refresh_token = authorize(client_id, client_secret)
    print('Authorization successful!\n')

    detected_repo = _detect_gh_repo()
    suffix = f' [{detected_repo}]' if detected_repo else ''
    repo = input(f'GitHub repo to push refresh token (owner/repo){suffix}: ').strip() or detected_repo

    if repo:
        result = subprocess.run(
            ['gh', 'secret', 'set', 'SPOTIFY_REFRESH_TOKEN', '--repo', repo],
            input=refresh_token, text=True, capture_output=True,
        )
        if result.returncode == 0:
            print(f'✅ SPOTIFY_REFRESH_TOKEN pushed to {repo}.')
        else:
            print(f'❌ Failed to push secret. Set SPOTIFY_REFRESH_TOKEN manually:\n  {refresh_token}')
    else:
        print(f'SPOTIFY_REFRESH_TOKEN (add to GitHub Secrets manually):\n  {refresh_token}')


if __name__ == '__main__':
    main()
