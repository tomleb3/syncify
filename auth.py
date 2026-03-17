"""
One-time Spotify OAuth authorization.

Obtains a refresh token with the scopes required by Syncify and optionally
pushes it to GitHub Secrets so the sync workflow can use it.

Run with: make auth

Before running, add http://127.0.0.1:8888/callback to your Spotify app's
Redirect URIs (Spotify Developer Dashboard → your app → Edit Settings).
"""

import os
import re
import subprocess
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

REDIRECT_URI = 'http://127.0.0.1:8888/callback'
SCOPES = 'playlist-read-private playlist-modify-private'


def _parse_redirect_params(redirected_url: str) -> dict[str, list[str]]:
    return urllib.parse.parse_qs(urllib.parse.urlparse(redirected_url).query)


def _prompt_for_redirect(auth_url: str) -> dict[str, list[str]]:
    print('Open the following URL in your browser to authorize Syncify:')
    print(f'  {auth_url}\n')
    print('After authorizing, copy the full redirected URL from the address bar and paste it here.')
    redirected_url = input('Redirected URL: ').strip()
    return _parse_redirect_params(redirected_url)


def _listen_for_redirect(auth_url: str, timeout_seconds: int = 120) -> dict[str, list[str]]:
    callback_data: dict[str, dict[str, list[str]]] = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != '/callback':
                self.send_response(404)
                self.end_headers()
                return

            callback_data['params'] = urllib.parse.parse_qs(parsed.query)
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(
                b'<html><body><h1>Syncify authorization complete.</h1>'
                b'<p>You can close this tab and return to the terminal.</p></body></html>'
            )

        def log_message(self, format: str, *args: object) -> None:
            return

    with HTTPServer(('127.0.0.1', 8888), CallbackHandler) as server:
        print('Open the following URL in your browser to authorize Syncify:')
        print(f'  {auth_url}\n')
        print('After approving access, Spotify will redirect back to http://127.0.0.1:8888/callback.')
        print('Waiting for Spotify to redirect back...')

        deadline = time.monotonic() + timeout_seconds
        while 'params' not in callback_data:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Timed out waiting for the Spotify redirect.')
            server.timeout = min(1.0, remaining)
            server.handle_request()

    return callback_data['params']


def _get_authorization_params(auth_url: str) -> dict[str, list[str]]:
    try:
        return _listen_for_redirect(auth_url)
    except OSError as exc:
        print(f'Could not start the local callback listener: {exc}')
    except TimeoutError as exc:
        print(str(exc))

    print('Falling back to manual redirect capture.\n')
    return _prompt_for_redirect(auth_url)


def authorize(client_id: str, client_secret: str) -> tuple[str, str]:
    """Run the OAuth Authorization Code flow. Returns (access_token, refresh_token)."""
    auth_url = 'https://accounts.spotify.com/authorize?' + urllib.parse.urlencode({
        'client_id': client_id,
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'scope': SCOPES,
    })
    params = _get_authorization_params(auth_url)
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
    print('Make sure http://127.0.0.1:8888/callback is added to your Spotify app\'s Redirect URIs.\n')

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
