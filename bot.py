"""
Syncify Telegram bot — interactive playlist selection and on-demand sync.

Run with: make bot

Commands:
  /start     — show help (also reveals your chat ID for first-time setup)
  /playlists — pick which playlists to sync via an inline keyboard
  /sync      — run sync immediately using the current config
"""

import logging
import os
import re
import subprocess

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from syncify import (
    TARGET_PLAYLIST_NAME,
    USER_ID,
    get_access_token,
    get_playlists,
    on_select_playlists,
)

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    level=logging.INFO,
)

BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
_ALLOWED_CHAT_ID = int(os.environ.get('TELEGRAM_CHAT_ID') or 0)

# Per-chat state: {chat_id: {'playlists': [...], 'selected': set[str]}}
_state: dict[int, dict] = {}


# ── helpers ──────────────────────────────────────────────────────────────────

def _is_authorized(update: Update) -> bool:
    return _ALLOWED_CHAT_ID != 0 and update.effective_chat.id == _ALLOWED_CHAT_ID


def _build_keyboard(playlists: list[dict], selected: set[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            f"{'✅' if p['name'] in selected else '◻️'} {p['name']}",
            callback_data=f't:{i}',
        )]
        for i, p in enumerate(playlists)
    ]
    rows.append([
        InlineKeyboardButton('Select All', callback_data='a:all'),
        InlineKeyboardButton('Clear', callback_data='a:none'),
    ])
    rows.append([
        InlineKeyboardButton('💾 Save', callback_data='a:save'),
        InlineKeyboardButton('▶️ Save & Sync', callback_data='a:sync'),
    ])
    return InlineKeyboardMarkup(rows)


def _save_selection(source_playlists: list[str]) -> None:
    _push_gh_variable('SPOTIFY_SOURCE_PLAYLISTS', ','.join(source_playlists))


def _detect_gh_repo() -> str:
    """Detect owner/repo from git remote origin URL."""
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


def _push_gh_variable(name: str, value: str) -> None:
    """Update a GitHub Actions Variable via REST API so the next cron run picks it up."""
    token = os.environ.get('GITHUB_TOKEN')
    repo = os.environ.get('GITHUB_REPO') or _detect_gh_repo()
    if not token or not repo:
        return
    try:
        # Try PATCH (update existing), fall back to POST (create new).
        url = f'https://api.github.com/repos/{repo}/actions/variables/{name}'
        headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json'}
        resp = requests.patch(url, json={'name': name, 'value': value}, headers=headers, timeout=10)
        if resp.status_code == 404:
            requests.post(
                f'https://api.github.com/repos/{repo}/actions/variables',
                json={'name': name, 'value': value},
                headers=headers,
                timeout=10,
            ).raise_for_status()
        else:
            resp.raise_for_status()
        logging.info('Pushed %s to GitHub Variable.', name)
    except Exception as e:
        logging.warning('Failed to push %s to GitHub: %s', name, e)


def _spotify_token() -> str:
    return get_access_token(os.environ['SPOTIFY_CLIENT_ID'], os.environ['SPOTIFY_CLIENT_SECRET'])


# ── command handlers ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not _is_authorized(update):
        await update.message.reply_text(
            f'Your chat ID is `{chat_id}`.\n\n'
            'To authorize this chat, restart the bot with:\n'
            f'`TELEGRAM_CHAT_ID={chat_id} make bot`\n\n'
            'For cron notifications, add `TELEGRAM_CHAT_ID` as a '
            'GitHub Variable in your repo settings.',
            parse_mode='Markdown',
        )
        return

    await update.message.reply_text(
        '*Syncify Bot* 🎵\n\n'
        '/playlists — choose which playlists to sync\n'
        '/sync — run sync now with current config',
        parse_mode='Markdown',
    )


async def cmd_playlists(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        return

    msg = await update.message.reply_text('Fetching your playlists from Spotify…')

    try:
        token = _spotify_token()
        include_external = os.environ.get('SPOTIFY_INCLUDE_EXTERNAL', '').lower() == 'true'
        playlists = get_playlists(USER_ID, include_external, token)
    except Exception as e:
        await msg.edit_text(f'❌ Failed to fetch playlists: {e}')
        return

    if not playlists:
        await msg.edit_text('No playlists found.')
        return

    chat_id = update.effective_chat.id
    source_env = os.environ.get('SPOTIFY_SOURCE_PLAYLISTS', '')
    if source_env:
        configured = set(name.strip() for name in source_env.split(','))
    else:
        configured = set(p['name'] for p in playlists)
    _state[chat_id] = {'playlists': playlists, 'selected': configured}

    await msg.edit_text(
        f'Select playlists to sync into *{TARGET_PLAYLIST_NAME}*:',
        parse_mode='Markdown',
        reply_markup=_build_keyboard(playlists, configured),
    )


async def cmd_sync(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        return

    msg = await update.message.reply_text('Running sync…')

    try:
        token = _spotify_token()
        include_external = os.environ.get('SPOTIFY_INCLUDE_EXTERNAL', '').lower() == 'true'
        all_playlists = get_playlists(USER_ID, include_external, token)
        source_env = os.environ.get('SPOTIFY_SOURCE_PLAYLISTS', '')
        if source_env:
            source_names = set(name.strip() for name in source_env.split(','))
        else:
            source_names = set(p['name'] for p in all_playlists)
        selected = [p for p in all_playlists if p['name'] in source_names]
        count = on_select_playlists(USER_ID, selected, token)
        await msg.edit_text(
            f'✅ Synced! Added *{count}* track(s) to _{TARGET_PLAYLIST_NAME}_.',
            parse_mode='Markdown',
        )
    except Exception as e:
        await msg.edit_text(f'❌ Sync failed: {e}')


# ── inline keyboard handler ───────────────────────────────────────────────────

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    if chat_id not in _state:
        await query.edit_message_text('Session expired. Use /playlists to start again.')
        return

    playlists: list[dict] = _state[chat_id]['playlists']
    selected: set[str] = _state[chat_id]['selected']
    data: str = query.data

    if data.startswith('t:'):
        name = playlists[int(data[2:])]['name']
        selected.discard(name) if name in selected else selected.add(name)
        await query.edit_message_reply_markup(_build_keyboard(playlists, selected))

    elif data == 'a:all':
        selected.update(p['name'] for p in playlists)
        await query.edit_message_reply_markup(_build_keyboard(playlists, selected))

    elif data == 'a:none':
        selected.clear()
        await query.edit_message_reply_markup(_build_keyboard(playlists, selected))

    elif data in ('a:save', 'a:sync'):
        _save_selection(sorted(selected))
        await query.edit_message_text(f'💾 Saved: *{len(selected)}* playlist(s) selected.', parse_mode='Markdown')

        if data == 'a:sync':
            status = await query.message.reply_text('Running sync…')
            try:
                token = _spotify_token()
                selected_playlists = [p for p in playlists if p['name'] in selected]
                count = on_select_playlists(USER_ID, selected_playlists, token)
                await status.edit_text(
                    f'✅ Synced! Added *{count}* track(s) to _{TARGET_PLAYLIST_NAME}_.',
                    parse_mode='Markdown',
                )
            except Exception as e:
                await status.edit_text(f'❌ Sync failed: {e}')


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', cmd_start))
    app.add_handler(CommandHandler('playlists', cmd_playlists))
    app.add_handler(CommandHandler('sync', cmd_sync))
    app.add_handler(CallbackQueryHandler(on_button))
    app.run_polling()


if __name__ == '__main__':
    main()
