import re
import sys
import io
import threading
from collections import deque
from datetime import datetime, timezone

# Fix Windows console encoding for emojis
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import discord
from flask import Flask, jsonify, request as flask_request

# ═══════════════════════════════════════════════════════════════
# CONFIG — edit here
# ═══════════════════════════════════════════════════════════════

DISCORD_TOKEN = "MTUwMzgyODI1MTgzNDA1NjcxNg.GjjVf7.gX6Nsrt42kqQF2CpsGeoENRYK51OZqcpvHv1Qk"

# Optional Roblox place ID (None = only from Discord messages / game.PlaceId in Lua)
PLACE_ID = None

# Discord channel IDs to monitor
CHANNEL_IDS = [
    1511261850787119258,
    1511032792459382784,
    1511032750277394522,
    1511301452415373342,
]

# Flask server
FLASK_HOST = "127.0.0.1"
FLASK_PORT = 5000

# ═══════════════════════════════════════════════════════════════

if not DISCORD_TOKEN or DISCORD_TOKEN == "YOUR_TOKEN_HERE":
    raise RuntimeError("Set DISCORD_TOKEN at the top of main.py")

DEFAULT_PLACE_ID = PLACE_ID

session_store = deque(maxlen=200)
store_lock = threading.Lock()

UUID_RE = re.compile(
    r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
)
HEX32_RE = re.compile(r'(?<![0-9a-fA-F])[0-9a-fA-F]{32}(?![0-9a-fA-F])')


def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        text = ' '.join(str(a) for a in args)
        print(text.encode('ascii', errors='replace').decode('ascii'), **kwargs)


def normalize_job_id(raw: str) -> str:
    """Roblox job IDs are 32 lowercase hex chars (no dashes)."""
    cleaned = raw.replace('-', '').lower()
    if len(cleaned) == 32 and re.fullmatch(r'[0-9a-f]{32}', cleaned):
        return cleaned
    return raw


def extract_job_id(text: str):
    m = UUID_RE.search(text)
    if m:
        return normalize_job_id(m.group(0))
    m = HEX32_RE.search(text)
    if m:
        return normalize_job_id(m.group(0))
    return None


client = discord.Client()


@client.event
async def on_ready():
    safe_print(f'[OK] Connected as {client.user} (ID: {client.user.id})')
    safe_print(f'[OK] Monitoring {len(CHANNEL_IDS)} channels')


@client.event
async def on_message(message):
    if message.channel.id not in CHANNEL_IDS:
        return

    safe_print(f'\n[MSG] Channel: {message.channel.id} | Author: {message.author}')

    text_parts = []
    if message.content:
        text_parts.append(message.content)
        safe_print(f'[MSG] Content: {message.content[:200]}')

    for embed in message.embeds:
        safe_print(f'[MSG] Embed found: title={embed.title}')
        if embed.title:
            text_parts.append(embed.title)
        if embed.description:
            text_parts.append(embed.description)
        for field in embed.fields:
            text_parts.append(f'{field.name}: {field.value}')
            safe_print(f'  Field: {field.name} = {field.value}')

    full_text = '\n'.join(text_parts)
    if not full_text.strip():
        safe_print('[SKIP] Empty message')
        return

    job_id = extract_job_id(full_text)
    if not job_id:
        safe_print('[SKIP] No job ID found in message')
        return

    rate = '?'
    rate_match = re.search(r'\$[\d,.]+[MBKmk]/s', full_text)
    if rate_match:
        rate = rate_match.group(0)

    players = '?'
    players_match = re.search(r'(\d+\s*/\s*\d+)', full_text)
    if players_match:
        players = players_match.group(1).replace(' ', '')

    mutation = 'None'
    for pat in (r'[Mm]utation[:\s]*([^\n]+)', r'Mutation\s*\n\s*(\S+)'):
        m = re.search(pat, full_text)
        if m:
            val = m.group(1).strip()
            if val and val.lower() != 'none':
                mutation = val
            break

    name = 'Unknown'
    brainrot_match = re.search(r'[Bb]rainrot[:\s]*\n?\s*([^\n$]+)', full_text)
    if brainrot_match:
        name = brainrot_match.group(1).strip()
    else:
        for line in full_text.split('\n'):
            clean = re.sub(r"[^\w\s'-]", '', line).strip()
            if clean and len(clean) > 2 and '$' not in line and '/' not in clean:
                name = clean
                break

    name = re.sub(r'\[?(LOW|MED|HIGH|VERY HIGH)\]?', '', name).strip()

    place_id = DEFAULT_PLACE_ID
    place_match = re.search(r'place[_\s-]*id[:\s]*(\d{6,})', full_text, re.I)
    if place_match:
        place_id = int(place_match.group(1))

    entry = {
        'timestamp': int(datetime.now(timezone.utc).timestamp() * 1000),
        'job_id': job_id,
        'name': name,
        'rate': rate,
        'mutation': mutation,
        'players': players,
        'place_id': place_id,
    }
    with store_lock:
        session_store.append(entry)
    safe_print(f'[STORED] {name} | {rate} | {mutation} | {players} | {job_id[:8]}...')


app = Flask(__name__)


@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


@app.route('/sessions', methods=['GET'])
def get_sessions():
    since = flask_request.args.get('since', type=int)
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    with store_lock:
        if since is not None and since > 0:
            filtered = [e for e in session_store if e['timestamp'] > since]
        else:
            cutoff = now_ms - 120_000
            filtered = [e for e in session_store if e['timestamp'] >= cutoff]
    return jsonify(filtered)


@app.route('/health', methods=['GET'])
def health():
    with store_lock:
        count = len(session_store)
    return jsonify({'ok': True, 'stored': count}), 200


@app.route('/debug', methods=['GET'])
def debug():
    with store_lock:
        all_entries = list(session_store)
    return jsonify({'count': len(all_entries), 'entries': all_entries})


def run_flask():
    app.run(host=FLASK_HOST, port=FLASK_PORT, use_reloader=False, threaded=True)


if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    safe_print(f'[OK] Flask server started on http://{FLASK_HOST}:{FLASK_PORT}')
    safe_print(f'[OK] Sessions: http://{FLASK_HOST}:{FLASK_PORT}/sessions')
    safe_print(f'[OK] Health:   http://{FLASK_HOST}:{FLASK_PORT}/health')
    safe_print('[OK] Starting Discord connection...')
    client.run(DISCORD_TOKEN)
