import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional

import requests

BASE_URL = 'https://api.spotify.com'
GUI_PORT = 8888
REDIRECT_URI = f'http://127.0.0.1:{GUI_PORT}/callback'
GUI_URL = f'http://127.0.0.1:{GUI_PORT}'
SCOPES = 'playlist-read-private playlist-modify-private'

def load_env():
    """Manually parse .env file to avoid extra dependencies."""
    env = {}
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    env[key.strip()] = value.strip().strip('"').strip("'")
    return env

ENV_VARS = load_env()

# Global state to track progress
STATE: Dict[str, Any] = {
    'step': 'credentials',
    'client_id': ENV_VARS.get('SPOTIFY_CLIENT_ID', os.environ.get('SPOTIFY_CLIENT_ID', '')),
    'client_secret': ENV_VARS.get('SPOTIFY_CLIENT_SECRET', os.environ.get('SPOTIFY_CLIENT_SECRET', '')),
    'access_token': None,
    'refresh_token': None,
    'playlists': [],
    'selected_source_ids': [],
    'target_playlist_id': None,
    'include_external': False,
    'remove_missing': False,
    'repo': '',
    'error': None,
    'pushed_items': [],
    'should_stop': False
}

def get_template(content: str) -> str:
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Syncify Setup</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary: #1DB954;
            --primary-hover: #1ed760;
            --bg: #050505;
            --surface: rgba(25, 25, 25, 0.9);
            --border: rgba(255, 255, 255, 0.1);
            --text: #ffffff;
            --text-dim: rgba(255, 255, 255, 0.6);
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg);
            color: var(--text);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(29, 185, 84, 0.05) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(29, 185, 84, 0.05) 0%, transparent 40%);
        }}
        .container {{
            background: var(--surface);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid var(--border);
            border-radius: 24px;
            padding: 2rem;
            width: 100%;
            max-width: 440px;
            box-shadow: 0 30px 60px rgba(0,0,0,0.5);
            animation: fadeIn 0.5s ease-out;
        }}
        @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        h1 {{ font-size: 1.5rem; margin-bottom: 0.5rem; font-weight: 600; letter-spacing: -0.02em; }}
        p {{ color: var(--text-dim); font-size: 0.9rem; margin-bottom: 1.5rem; line-height: 1.5; }}
        .error {{
            background: rgba(255, 85, 85, 0.1);
            border: 1px solid rgba(255, 85, 85, 0.2);
            color: #ff5555;
            padding: 0.75rem;
            border-radius: 12px;
            font-size: 0.85rem;
            margin-bottom: 1.5rem;
        }}
        .form-group {{ margin-bottom: 1.25rem; }}
        label {{ display: block; font-size: 0.8rem; font-weight: 600; color: var(--text-dim); margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.05em; }}
        input[type="text"], input[type="password"], select {{
            width: 100%;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border);
            color: #fff;
            padding: 0.8rem 1rem;
            border-radius: 12px;
            font-family: inherit;
            font-size: 0.95rem;
            transition: all 0.2s ease;
        }}
        input:focus {{ outline: none; border-color: var(--primary); background: rgba(255, 255, 255, 0.08); }}
        .btn {{
            width: 100%;
            background: var(--primary);
            color: #000;
            border: none;
            padding: 1rem;
            border-radius: 100px;
            font-family: inherit;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            margin-top: 0.5rem;
        }}
        .btn:hover {{ background: var(--primary-hover); transform: translateY(-2px); box-shadow: 0 10px 20px rgba(29, 185, 84, 0.3); }}
        .playlist-list {{
            max-height: 200px;
            overflow-y: auto;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 12px;
            padding: 0.5rem;
            margin-bottom: 1.5rem;
            border: 1px solid var(--border);
        }}
        .playlist-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 0.5rem;
            border-radius: 8px;
            cursor: pointer;
            transition: background 0.2s;
        }}
        .playlist-item:hover {{ background: rgba(255, 255, 255, 0.05); }}
        .checkbox-wrapper {{
            width: 18px;
            height: 18px;
            border: 2px solid var(--border);
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
        }}
        .playlist-item.selected .checkbox-wrapper {{
            background: var(--primary);
            border-color: var(--primary);
        }}
        .checkbox-wrapper::after {{
            content: '✓';
            color: #000;
            font-size: 12px;
            display: none;
        }}
        .playlist-item.selected .checkbox-wrapper::after {{ display: block; }}
        .toggle-group {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }}
        .toggle-text {{ font-size: 0.9rem; color: var(--text-dim); }}
        .switch {{
            position: relative;
            display: inline-block;
            width: 44px;
            height: 24px;
        }}
        .switch input {{ opacity: 0; width: 0; height: 0; }}
        .slider {{
            position: absolute;
            cursor: pointer;
            top: 0; left: 0; right: 0; bottom: 0;
            background-color: rgba(255, 255, 255, 0.1);
            transition: .4s;
            border-radius: 24px;
        }}
        .slider:before {{
            position: absolute;
            content: "";
            height: 18px; width: 18px;
            left: 3px; bottom: 3px;
            background-color: white;
            transition: .4s;
            border-radius: 50%;
        }}
        input:checked + .slider {{ background-color: var(--primary); }}
        input:checked + .slider:before {{ transform: translateX(20px); }}
    </style>
</head>
<body>
    <div class="container">
        {content}
    </div>
</body>
</html>
"""

class SetupHandler(BaseHTTPRequestHandler):
    def _send_html(self, content: str):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(get_template(content).encode('utf-8'))

    def _redirect(self, path: str):
        self.send_response(303)
        self.send_header('Location', path)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        
        if parsed.path == '/callback':
            params = urllib.parse.parse_qs(parsed.query)
            if 'code' in params:
                code = params['code'][0]
                try:
                    response = requests.post(
                        'https://accounts.spotify.com/api/token',
                        data={
                            'grant_type': 'authorization_code',
                            'code': code,
                            'redirect_uri': REDIRECT_URI,
                        },
                        auth=(STATE['client_id'], STATE['client_secret']),
                    )
                    response.raise_for_status()
                    data = response.json()
                    STATE['access_token'] = data['access_token']
                    STATE['refresh_token'] = data['refresh_token']
                    
                    # Fetch playlists immediately
                    resp = requests.get(
                        f'{BASE_URL}/v1/me/playlists',
                        headers={'Authorization': f'Bearer {STATE["access_token"]}'},
                    )
                    resp.raise_for_status()
                    STATE['playlists'] = resp.json().get('items', [])
                    STATE['step'] = 'configure'
                    self._redirect('/')
                except requests.HTTPError as e:
                    if e.response.status_code == 403:
                        STATE['error'] = (
                            "<strong>403 Forbidden:</strong> Your Spotify account is not authorized to use this App.<br><br>"
                            "1. Go to your <a href='https://developer.spotify.com/dashboard' target='_blank' style='color:var(--primary)'>Spotify Dashboard</a>.<br>"
                            "2. Click on your App &rarr; <strong>Settings</strong> &rarr; <strong>User Management</strong>.<br>"
                            "3. Add your Spotify email address to the list of authorized users.<br>"
                            "4. Try again."
                        )
                    else:
                        STATE['error'] = f"Auth failed: {e}"
                    STATE['step'] = 'credentials'
                    self._redirect('/')
                except Exception as e:
                    STATE['error'] = f"Auth failed: {e}"
                    STATE['step'] = 'credentials'
                    self._redirect('/')
            return

        if STATE['step'] == 'credentials':
            err_html = f'<div class="error">{STATE["error"]}</div>' if STATE['error'] else ''
            env_notice = ""
            if STATE['client_id'] and STATE['client_secret']:
                env_notice = '<div style="background:rgba(29,185,84,0.1); color:var(--primary); padding:0.75rem; border-radius:12px; font-size:0.85rem; margin-bottom:1.5rem; border:1px solid rgba(29,185,84,0.2);">✨ Credentials loaded from your <code>.env</code> file.</div>'
            
            self._send_html(f"""
                <h1>Spotify Credentials</h1>
                <p>Enter your Spotify App credentials. You can find these in the <a href="https://developer.spotify.com/dashboard" target="_blank" style="color:var(--primary); text-decoration:none;">Dashboard</a>.</p>
                {env_notice}
                {err_html}
                <form action="/step/credentials" method="POST">
                    <div class="form-group">
                        <label>Client ID</label>
                        <input type="text" name="client_id" value="{STATE['client_id']}" placeholder="Your Spotify Client ID" required>
                    </div>
                    <div class="form-group">
                        <label>Client Secret</label>
                        <input type="password" name="client_secret" value="{STATE['client_secret']}" placeholder="Your Spotify Client Secret" required>
                    </div>
                    <button type="submit" class="btn">Connect Spotify</button>
                </form>
            """)
        elif STATE['step'] == 'authorize':
            auth_url = 'https://accounts.spotify.com/authorize?' + urllib.parse.urlencode({
                'client_id': STATE['client_id'],
                'response_type': 'code',
                'redirect_uri': REDIRECT_URI,
                'scope': SCOPES,
            })
            self._send_html(f"""
                <h1>Authorize Syncify</h1>
                <p>Click below to authorize Syncify with your Spotify account. This will open a Spotify login page.</p>
                <a href="{auth_url}" class="btn" style="text-decoration:none; display:block; text-align:center;">Authorize with Spotify</a>
            """)
        elif STATE['step'] == 'configure':
            user_id = STATE['playlists'][0]['owner']['id'] if STATE['playlists'] else ''
            items_html = ""
            for p in STATE['playlists']:
                items_html += f"""
                    <div class="playlist-item" onclick="this.classList.toggle('selected'); updateSelected();" data-id="{p['id']}">
                        <div class="checkbox-wrapper"></div>
                        <span style="font-size:0.9rem;">{p['name']}</span>
                    </div>
                """
            
            target_options = "".join([f"<option value='{p['id']}'>{p['name']}</option>" for p in STATE['playlists'] if p['owner']['id'] == user_id])

            self._send_html(f"""
                <h1>Configure Sync</h1>
                <p>Select which playlists to sync from and where to merge them.</p>
                <form action="/step/configure" method="POST" id="configForm">
                    <label>Source Playlists</label>
                    <div class="playlist-list">
                        {{items_html}}
                    </div>
                    <input type="hidden" name="source_ids" id="source_ids">
                    
                    <div class="form-group">
                        <label>Target Playlist</label>
                        <select name="target_id">
                            {{target_options}}
                            <option value="new">[ Create New Playlist ]</option>
                        </select>
                    </div>

                    <div class="toggle-group">
                        <span class="toggle-text">Include followed playlists?</span>
                        <label class="switch"><input type="checkbox" name="include_external"><span class="slider"></span></label>
                    </div>
                    <div class="toggle-group">
                        <span class="toggle-text">Remove missing tracks?</span>
                        <label class="switch"><input type="checkbox" name="remove_missing"><span class="slider"></span></label>
                    </div>

                    <button type="submit" class="btn">Save & Continue</button>
                </form>
                <script>
                    function updateSelected() {{
                        const ids = Array.from(document.querySelectorAll('.playlist-item.selected')).map(el => el.dataset.id);
                        document.getElementById('source_ids').value = ids.join(',');
                    }}
                </script>
            """)
        elif STATE['step'] == 'deploy':
            detected_repo = _detect_gh_repo()
            self._send_html(f"""
                <h1>GitHub Deployment</h1>
                <p>Push your configuration to GitHub Actions. This will set up the scheduled sync workflow.</p>
                <form action="/step/deploy" method="POST">
                    <div class="form-group">
                        <label>GitHub Repository</label>
                        <input type="text" name="repo" value="{detected_repo}" placeholder="owner/repo" required>
                    </div>
                    <button type="submit" class="btn">Push to GitHub</button>
                </form>
            """)
        elif STATE['step'] == 'success':
            items_list = "".join([f'<div style="background:rgba(255,255,255,0.03); padding:0.5rem 1rem; border-radius:10px; margin-bottom:0.5rem; font-size:0.85rem; display:flex; align-items:center; gap:8px;"><span style="color:var(--primary)">✓</span>{item}</div>' for item in STATE['pushed_items']])
            self._send_html(f"""
                <div style="text-align:center;">
                    <div style="width:48px; height:48px; background:var(--primary); border-radius:50%; display:flex; align-items:center; justify-content:center; margin: 0 auto 1.5rem; color:#000; font-size:1.5rem;">✓</div>
                    <h1>Setup Complete!</h1>
                    <p style="margin-bottom:1rem;">Syncify is now configured for <strong>{STATE['repo']}</strong>.</p>
                    <div style="text-align:left; margin-bottom:1.5rem;">
                        {items_list}
                    </div>
                    <form action="/exit" method="POST">
                        <button type="submit" class="btn">Finish & Close</button>
                    </form>
                </div>
            """)

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = urllib.parse.parse_qs(self.rfile.read(content_length).decode('utf-8'))
        
        if self.path == '/exit':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<html><body><script>window.close();</script></body></html>")
            STATE['should_stop'] = True
            return

        if self.path == '/step/credentials':
            STATE['client_id'] = post_data.get('client_id', [''])[0]
            STATE['client_secret'] = post_data.get('client_secret', [''])[0]
            STATE['step'] = 'authorize'
            self._redirect('/')
        
        elif self.path == '/step/configure':
            STATE['selected_source_ids'] = post_data.get('source_ids', [''])[0].split(',')
            STATE['target_playlist_id'] = post_data.get('target_id', [None])[0]
            STATE['include_external'] = 'include_external' in post_data
            STATE['remove_missing'] = 'remove_missing' in post_data
            
            if STATE['target_playlist_id'] == 'new':
                # Create new playlist
                user_id = STATE['playlists'][0]['owner']['id']
                resp = requests.post(
                    f'{BASE_URL}/v1/users/{user_id}/playlists',
                    headers={'Authorization': f'Bearer {STATE["access_token"]}', 'Content-Type': 'application/json'},
                    json={'name': 'Syncified', 'description': 'Merged by Syncify', 'public': False},
                )
                resp.raise_for_status()
                STATE['target_playlist_id'] = resp.json()['id']
            
            STATE['step'] = 'deploy'
            self._redirect('/')
            
        elif self.path == '/step/deploy':
            repo = post_data.get('repo', [''])[0]
            STATE['repo'] = repo
            
            secrets = {
                'SPOTIFY_REFRESH_TOKEN': STATE['refresh_token'],
                'SPOTIFY_CLIENT_ID': STATE['client_id'],
                'SPOTIFY_CLIENT_SECRET': STATE['client_secret']
            }
            
            source_ids_str = ','.join(STATE['selected_source_ids']) if STATE['selected_source_ids'] else None
            
            variables = {
                'SPOTIFY_TARGET_PLAYLIST_ID': STATE['target_playlist_id'],
                'SPOTIFY_SOURCE_PLAYLIST_IDS': source_ids_str,
                'SPOTIFY_INCLUDE_EXTERNAL': 'true' if STATE['include_external'] else None,
                'SPOTIFY_REMOVE_MISSING': 'true' if STATE['remove_missing'] else None,
            }
            
            # Use existing _gh_push logic (need to adapt slightly for feedback)
            _gh_push(repo, secrets, variables)
            
            STATE['pushed_items'] = [
                'Spotify Refresh Token Pushed',
                f'Target Playlist Linked: {STATE["target_playlist_id"]}',
                'Sync Configuration Saved',
                'Spotify Client ID Pushed',
                'Spotify Client Secret Pushed'
            ]
            STATE['step'] = 'success'
            self._redirect('/')

    def log_message(self, format, *args): return

def _detect_gh_repo() -> str:
    try:
        user_result = subprocess.run(['gh', 'api', 'user', '-q', '.login'], capture_output=True, text=True)
        gh_user = user_result.stdout.strip().lower()
        remotes_result = subprocess.run(['git', 'remote', '-v'], capture_output=True, text=True)
        remotes = {}
        for line in remotes_result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                name, url = parts[0], parts[1]
                m = re.search(r'github\.com[:/](.+?/[^/]+?)(?:\.git)?$', url)
                if m: remotes[name] = m.group(1)
        if not remotes: return ''
        if gh_user:
            for repo_full in remotes.values():
                if repo_full.lower().startswith(f'{gh_user}/'): return repo_full
        return remotes.get('origin', list(remotes.values())[0])
    except: return ''

def _gh_push(repo: str, secrets: dict[str, str], variables: dict[str, str | None]) -> None:
    def _run(args: list[str], value: str = '') -> None:
        subprocess.run(['gh'] + args + ['--repo', repo], input=value, text=True, capture_output=True)

    for name, value in secrets.items():
        _run(['secret', 'set', name], value)
    for name, value in variables.items():
        if value is None:
            _run(['variable', 'delete', name])
        else:
            _run(['variable', 'set', name, '--body', value])

def main() -> None:
    parser = argparse.ArgumentParser(description='Syncify Setup')
    parser.add_argument('--auth-only', action='store_true', help='Only perform Spotify authorization')
    args = parser.parse_args()

    if args.auth_only:
        # We can still use a simplified GUI for auth-only if needed, but for now let's focus on the main flow
        STATE['step'] = 'credentials'

    print(f'Starting Syncify Setup GUI on {GUI_URL}...')
    server = HTTPServer(('127.0.0.1', GUI_PORT), SetupHandler)
    webbrowser.open(GUI_URL)
    
    try:
        while not STATE['should_stop']:
            server.handle_request()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print('Setup server stopped.')

if __name__ == '__main__':
    main()
