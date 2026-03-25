import discord
from discord.ext import commands
import asyncio
import os
import datetime
import requests
from functools import wraps
from datetime import timezone
from dotenv import load_dotenv
from database import init_db, get_db

print("🚀 NinjuBot starting...", flush=True)
load_dotenv()
init_db()

from flask import Flask, jsonify, request as flask_request
from flask_cors import CORS
from threading import Thread

# ── Flask setup ────────────────────────────────────────────────
flask_app = Flask('')
CORS(flask_app, resources={r"/*": {"origins": "*"}})

start_time = datetime.datetime.now(timezone.utc)
_bot_ref   = None   # set once bot is ready

# ── Config (from env) ──────────────────────────────────────────
DISCORD_CLIENT_ID     = os.getenv('DISCORD_CLIENT_ID', '')
DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET', '')
DISCORD_API           = 'https://discord.com/api/v10'
DASHBOARD_ORIGIN      = os.getenv('DASHBOARD_ORIGIN', 'https://sohamdasbiswas.github.io')

# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════

def get_uptime():
    delta = datetime.datetime.now(timezone.utc) - start_time
    return str(delta).split('.')[0]

def discord_user_get(endpoint, token):
    """Call Discord API with a user Bearer token."""
    r = requests.get(
        f'{DISCORD_API}{endpoint}',
        headers={'Authorization': f'Bearer {token}'},
        timeout=10
    )
    r.raise_for_status()
    return r.json()

def bot_discord_get(endpoint):
    """Call Discord API with the bot token."""
    token = os.getenv('DISCORD_TOKEN', '')
    r = requests.get(
        f'{DISCORD_API}{endpoint}',
        headers={'Authorization': f'Bot {token}'},
        timeout=10
    )
    return r.json() if r.ok else {}

def require_auth(f):
    """Route decorator — just checks Bearer token is present, passes it through."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = flask_request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized'}), 401
        flask_request.discord_token = auth.split(' ', 1)[1]
        return f(*args, **kwargs)
    return decorated

# ══════════════════════════════════════════════════════════════
#  BASIC ROUTES (already existed)
# ══════════════════════════════════════════════════════════════

@flask_app.route('/')
def home():
    return "✅ NinjuBot is alive!"

@flask_app.route('/health')
def health():
    guilds = len(_bot_ref.guilds) if _bot_ref and _bot_ref.is_ready() else 0
    users  = sum(g.member_count for g in _bot_ref.guilds) if _bot_ref and _bot_ref.is_ready() else 0
    bot_name = str(_bot_ref.user) if _bot_ref and _bot_ref.is_ready() else 'NinjuBot'
    bot_id   = str(_bot_ref.user.id) if _bot_ref and _bot_ref.is_ready() else ''
    return jsonify({
        "status":   "online" if (_bot_ref and _bot_ref.is_ready()) else "starting",
        "uptime":   get_uptime(),
        "guilds":   guilds,
        "users":    users,
        "bot_name": bot_name,
        "bot_id":   bot_id,
    })

@flask_app.route('/stats')
def stats():
    if not _bot_ref or not _bot_ref.is_ready():
        return jsonify({"error": "Bot not ready"}), 503
    guild_list = [{
        "id":      str(g.id),
        "name":    g.name,
        "members": g.member_count,
        "icon":    str(g.icon.url) if g.icon else None,
    } for g in _bot_ref.guilds]
    return jsonify({
        "bot_name":    _bot_ref.user.name,
        "bot_id":      str(_bot_ref.user.id),
        "avatar":      str(_bot_ref.user.display_avatar.url),
        "guild_count": len(_bot_ref.guilds),
        "user_count":  sum(g.member_count for g in _bot_ref.guilds),
        "guilds":      guild_list,
        "uptime":      get_uptime(),
        "status":      "online",
    })

# ══════════════════════════════════════════════════════════════
#  AUTH — Discord OAuth2
# ══════════════════════════════════════════════════════════════

@flask_app.route('/auth/discord', methods=['POST', 'OPTIONS'])
def auth_discord():
    """Exchange OAuth2 code for token + user. Called by dashboard after Discord redirect."""
    if flask_request.method == 'OPTIONS':
        return _preflight()

    body         = flask_request.get_json(force=True) or {}
    code         = body.get('code')
    redirect_uri = body.get('redirect_uri')

    if not code or not redirect_uri:
        return jsonify({'error': 'Missing code or redirect_uri'}), 400

    if not DISCORD_CLIENT_SECRET:
        return jsonify({'error': 'DISCORD_CLIENT_SECRET not set on server'}), 500

    token_res = requests.post(
        f'{DISCORD_API}/oauth2/token',
        data={
            'client_id':     DISCORD_CLIENT_ID,
            'client_secret': DISCORD_CLIENT_SECRET,
            'grant_type':    'authorization_code',
            'code':          code,
            'redirect_uri':  redirect_uri,
        },
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        timeout=10
    )
    token_data = token_res.json()

    if 'access_token' not in token_data:
        return jsonify({'error': token_data.get('error_description', 'Token exchange failed')}), 400

    access_token = token_data['access_token']
    try:
        user = discord_user_get('/users/@me', access_token)
    except Exception as e:
        return jsonify({'error': f'Could not fetch user: {e}'}), 400

    return jsonify({'access_token': access_token, 'user': user})


@flask_app.route('/auth/guilds', methods=['GET', 'OPTIONS'])
def auth_guilds():
    """Return guilds where user is admin AND NinjuBot is present."""
    if flask_request.method == 'OPTIONS':
        return _preflight()

    # Manual auth check (OPTIONS must bypass @require_auth for CORS preflight to work)
    auth = flask_request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({'error': 'Unauthorized'}), 401
    flask_request.discord_token = auth.split(' ', 1)[1]

    try:
        user_guilds = discord_user_get('/users/@me/guilds', flask_request.discord_token)
    except Exception as e:
        return jsonify({'error': f'Could not fetch guilds: {e}'}), 400

    # Get bot guild IDs — prefer live bot, fall back to Discord API
    if _bot_ref and _bot_ref.is_ready():
        bot_guild_ids = {str(g.id) for g in _bot_ref.guilds}
    else:
        bot_guilds_raw = bot_discord_get('/users/@me/guilds')
        bot_guild_ids  = {g['id'] for g in bot_guilds_raw} if isinstance(bot_guilds_raw, list) else set()

    ADMINISTRATOR = 0x8
    result = []
    for g in user_guilds:
        perms    = int(g.get('permissions', 0))
        is_admin = bool(perms & ADMINISTRATOR) or g.get('owner', False)
        if is_admin and g['id'] in bot_guild_ids:
            # Try live bot cache first
            member_count = 0
            if _bot_ref and _bot_ref.is_ready():
                bot_guild = _bot_ref.get_guild(int(g['id']))
                if bot_guild:
                    member_count = bot_guild.member_count or 0
            # If still 0, fetch directly from Discord API with bot token
            if member_count == 0:
                guild_data = bot_discord_get(f'/guilds/{g["id"]}?with_counts=true')
                member_count = (guild_data.get('approximate_member_count')
                                or guild_data.get('member_count') or 0)
            result.append({
                'id':                       g['id'],
                'name':                     g['name'],
                'icon':                     g.get('icon'),
                'approximate_member_count': member_count,
                'owner':                    g.get('owner', False),  # pass Discord's owner flag
            })

    return jsonify(result)

# ══════════════════════════════════════════════════════════════
#  SETTINGS
# ══════════════════════════════════════════════════════════════

DEFAULT_SETTINGS = {
    # Bot
    'prefix': '-', 'bot_nickname': '', 'ai_model': 'deepseek',
    'ai_enabled': True, 'hinglish_mode': True, 'music_enabled': True,
    'always_247': False, 'max_queue_size': 50, 'default_volume': 50,
    # Economy
    'daily_min': 100, 'daily_max': 300, 'daily_cooldown_hours': 24,
    'work_min': 50, 'work_max': 200, 'work_cooldown_minutes': 60,
    'gambling_enabled': True, 'gamble_min_bet': 10, 'gamble_max_bet': 1000,
    'starting_balance': 500,
    # XP / Levels
    'xp_min': 15, 'xp_max': 40, 'xp_cooldown_seconds': 60,
    'xp_enabled': True, 'levelup_announcements': True,
    'levelup_message': '🎉 {user} just reached level {level}!',
    'xp_multiplier': 1, 'level_base_xp': 100,
    # Welcome / Leave
    'welcome_enabled': False, 'welcome_channel_id': '', 'welcome_message': 'Welcome {user}!',
    'welcome_card_enabled': True, 'welcome_card_bg': '#0e2a1a', 'welcome_card_color': '#4eff91',
    'leave_enabled': False, 'leave_channel_id': '', 'leave_message': '{user} has left.',
    # Streams
    'yt_alerts': False, 'yt_uploads': False, 'yt_channel_id': '',
    'yt_alert_channel_id': '', 'yt_alert_message': '🔴 {channel} is live!',
    'tw_alerts': False, 'tw_username': '', 'tw_alert_channel_id': '',
    'tw_alert_message': '🎮 {channel} just went live!', 'tw_stats_vc': False, 'yt_stats_vc': False,
    # Booster card
    'boost_enabled': True, 'boost_channel_id': '',
    'boost_message': '💎 {user} just boosted {server}!',
    'boost_gradient': 'forest', 'boost_accent': '#4eff91', 'boost_emoji': '💎',
    # Moderation
    'antispam_enabled': False, 'link_filter_enabled': False,
    'profanity_filter': False, 'raid_protection': False, 'spam_threshold': 8,
    'modlog_enabled': True, 'modlog_channel_id': '',
    'admin_role_id': '', 'mod_role_id': '', 'muted_role_id': '',
}

@flask_app.route('/settings', methods=['GET', 'OPTIONS'])
def get_settings():
    if flask_request.method == 'OPTIONS':
        return _preflight()

    # Manual auth check (OPTIONS must bypass @require_auth for CORS preflight to work)
    auth = flask_request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({'error': 'Unauthorized'}), 401
    flask_request.discord_token = auth.split(' ', 1)[1]
    guild_id = flask_request.args.get('guild_id')
    if not guild_id:
        return jsonify({'error': 'guild_id required'}), 400
    doc = get_db().guild_settings.find_one({'guild_id': guild_id}, {'_id': 0})
    merged = {**DEFAULT_SETTINGS, **(doc or {})}
    merged.pop('guild_id', None)
    return jsonify(merged)

@flask_app.route('/settings/update', methods=['POST', 'OPTIONS'])
def update_settings():
    if flask_request.method == 'OPTIONS':
        return _preflight()

    # Manual auth check (OPTIONS must bypass @require_auth for CORS preflight to work)
    auth = flask_request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({'error': 'Unauthorized'}), 401
    flask_request.discord_token = auth.split(' ', 1)[1]
    body     = flask_request.get_json(force=True) or {}
    guild_id = body.get('guild_id')
    settings = body.get('settings', {})
    if not guild_id:
        return jsonify({'error': 'guild_id required'}), 400
    get_db().guild_settings.update_one(
        {'guild_id': guild_id},
        {'$set': {**settings, 'guild_id': guild_id}},
        upsert=True
    )
    return jsonify({'success': True})

# ══════════════════════════════════════════════════════════════
#  LEADERBOARDS
# ══════════════════════════════════════════════════════════════

def resolve_username(user_id: str) -> str:
    """Try to resolve a Discord user ID to a display name using the bot cache."""
    if _bot_ref and _bot_ref.is_ready():
        user = _bot_ref.get_user(int(user_id))
        if user:
            return user.display_name or user.name
    return f'User {str(user_id)[-4:]}'  # fallback: last 4 digits of ID



@flask_app.route('/economy/leaderboard', methods=['GET', 'OPTIONS'])
def economy_leaderboard():
    if flask_request.method == 'OPTIONS':
        return _preflight()

    auth = flask_request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({'error': 'Unauthorized'}), 401
    flask_request.discord_token = auth.split(' ', 1)[1]

    guild_id = flask_request.args.get('guild_id')
    scope    = flask_request.args.get('scope', 'server')  # 'server' or 'global'

    if scope == 'global' or not guild_id:
        query = {}
    else:
        query = {'guild_id': str(guild_id)}

    docs = list(get_db().currency.find(query, {'_id': 0, 'user_id': 1, 'guild_id': 1, 'balance': 1, 'wins': 1, 'losses': 1}).sort('balance', -1).limit(10))
    result = []
    for d in docs:
        uid = str(d.get('user_id', '0'))
        result.append({
            'user_id':  uid,
            'username': resolve_username(uid),
            'balance':  d.get('balance', 0),
            'wins':     d.get('wins', 0),
            'losses':   d.get('losses', 0),
        })
    return jsonify(result)

@flask_app.route('/levels/leaderboard', methods=['GET', 'OPTIONS'])
def levels_leaderboard():
    if flask_request.method == 'OPTIONS':
        return _preflight()

    auth = flask_request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({'error': 'Unauthorized'}), 401
    flask_request.discord_token = auth.split(' ', 1)[1]

    guild_id = flask_request.args.get('guild_id')
    scope    = flask_request.args.get('scope', 'server')  # 'server' or 'global'

    if scope == 'global' or not guild_id:
        # Global XP — separate collection, fixed rate
        docs = list(get_db().xp_global.find(
            {}, {'_id': 0, 'user_id': 1, 'xp': 1, 'level': 1}
        ).sort('xp', -1).limit(10))
        result = []
        for d in docs:
            uid = str(d.get('user_id', '0'))
            result.append({
                'user_id':  uid,
                'username': resolve_username(uid),
                'xp':       d.get('xp', 0),
                'level':    d.get('level', 0),
                'scope':    'global',
            })
    else:
        # Server XP — configurable per-server
        docs = list(get_db().xp.find(
            {'guild_id': str(guild_id)},
            {'_id': 0, 'user_id': 1, 'xp': 1, 'level': 1}
        ).sort('xp', -1).limit(10))
        result = []
        for d in docs:
            uid = str(d.get('user_id', '0'))
            result.append({
                'user_id':  uid,
                'username': resolve_username(uid),
                'xp':       d.get('xp', 0),
                'level':    d.get('level', 0),
                'scope':    'server',
            })
    return jsonify(result)

# ══════════════════════════════════════════════════════════════
#  AUDIT LOG
# ══════════════════════════════════════════════════════════════

@flask_app.route('/audit/log', methods=['GET', 'OPTIONS'])
def audit_log():
    if flask_request.method == 'OPTIONS':
        return _preflight()

    # Manual auth check (OPTIONS must bypass @require_auth for CORS preflight to work)
    auth = flask_request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({'error': 'Unauthorized'}), 401
    flask_request.discord_token = auth.split(' ', 1)[1]
    guild_id = flask_request.args.get('guild_id')
    limit    = min(int(flask_request.args.get('limit', 100)), 500)
    query    = {'guild_id': str(guild_id)} if guild_id else {}
    docs     = list(get_db().audit_log.find(query, {'_id': 0}).sort('timestamp', -1).limit(limit))
    for d in docs:
        if isinstance(d.get('timestamp'), datetime.datetime):
            d['timestamp'] = d['timestamp'].isoformat()
    return jsonify({'entries': docs})

# ══════════════════════════════════════════════════════════════
#  SERVER BACKUP API
# ══════════════════════════════════════════════════════════════

@flask_app.route('/backup/list', methods=['GET','OPTIONS'])
def backup_list():
    if flask_request.method == 'OPTIONS': return _preflight()
    auth = flask_request.headers.get('Authorization','')
    if not auth.startswith('Bearer '): return jsonify({'error':'Unauthorized'}),401
    guild_id = flask_request.args.get('guild_id')
    if not guild_id: return jsonify({'error':'guild_id required'}),400
    docs = list(get_db().server_backups.find(
        {'guild_id': str(guild_id)},
        {'_id':0, 'snapshot':0}   # exclude heavy snapshot from list
    ).sort('created_at',-1).limit(20))
    return jsonify({'backups': docs})


@flask_app.route('/backup/create', methods=['POST','OPTIONS'])
def backup_create():
    if flask_request.method == 'OPTIONS': return _preflight()
    auth = flask_request.headers.get('Authorization','')
    if not auth.startswith('Bearer '): return jsonify({'error':'Unauthorized'}),401
    data     = flask_request.get_json(silent=True) or {}
    guild_id = data.get('guild_id')
    label    = data.get('label', '')
    if not guild_id: return jsonify({'error':'guild_id required'}),400

    if not _bot_ref or not _bot_ref.is_ready():
        return jsonify({'error':'Bot not ready'}),503

    guild = _bot_ref.get_guild(int(guild_id))
    if not guild: return jsonify({'error':'Guild not found'}),404

    from cogs.backup import _capture_guild
    try:
        snapshot  = _capture_guild(guild)
        backup_id = f'{guild_id}_{int(datetime.datetime.utcnow().timestamp())}'
        doc = {
            'backup_id':     backup_id,
            'guild_id':      str(guild_id),
            'guild_name':    guild.name,
            'label':         label or f'Backup {datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}',
            'created_at':    datetime.datetime.utcnow().isoformat(),
            'role_count':    len(snapshot['roles']),
            'channel_count': len(snapshot['text_channels']) + len(snapshot['voice_channels']),
            'emoji_count':   len(snapshot['emojis']),
            'member_count':  snapshot['member_count'],
            'snapshot':      snapshot,
        }
        get_db().server_backups.insert_one(doc)
        doc.pop('snapshot', None)
        doc.pop('_id', None)
        return jsonify({'success': True, 'backup': doc})
    except Exception as ex:
        return jsonify({'error': str(ex)}), 500


@flask_app.route('/backup/restore', methods=['POST','OPTIONS'])
def backup_restore():
    if flask_request.method == 'OPTIONS': return _preflight()
    auth = flask_request.headers.get('Authorization','')
    if not auth.startswith('Bearer '): return jsonify({'error':'Unauthorized'}),401
    data      = flask_request.get_json(silent=True) or {}
    guild_id  = data.get('guild_id')
    backup_id = data.get('backup_id')
    if not guild_id or not backup_id:
        return jsonify({'error':'guild_id and backup_id required'}),400

    doc = get_db().server_backups.find_one({'backup_id': backup_id, 'guild_id': str(guild_id)})
    if not doc: return jsonify({'error':'Backup not found'}),404

    if not _bot_ref or not _bot_ref.is_ready():
        return jsonify({'error':'Bot not ready'}),503
    guild = _bot_ref.get_guild(int(guild_id))
    if not guild: return jsonify({'error':'Guild not found'}),404

    from cogs.backup import _restore_guild
    async def _do_restore():
        return await _restore_guild(guild, doc['snapshot'])
    try:
        future = asyncio.run_coroutine_threadsafe(_do_restore(), _bot_ref.loop)
        logs   = future.result(timeout=120)
        return jsonify({'success': True, 'log': logs, 'count': len(logs)})
    except Exception as ex:
        return jsonify({'error': str(ex)}), 500


@flask_app.route('/backup/delete', methods=['POST','OPTIONS'])
def backup_delete():
    if flask_request.method == 'OPTIONS': return _preflight()
    auth = flask_request.headers.get('Authorization','')
    if not auth.startswith('Bearer '): return jsonify({'error':'Unauthorized'}),401
    data      = flask_request.get_json(silent=True) or {}
    guild_id  = data.get('guild_id')
    backup_id = data.get('backup_id')
    if not guild_id or not backup_id:
        return jsonify({'error':'guild_id and backup_id required'}),400
    res = get_db().server_backups.delete_one({'backup_id': backup_id, 'guild_id': str(guild_id)})
    return jsonify({'success': res.deleted_count > 0})


@flask_app.route('/backup/get', methods=['GET','OPTIONS'])
def backup_get():
    """Get full snapshot details for preview."""
    if flask_request.method == 'OPTIONS': return _preflight()
    auth = flask_request.headers.get('Authorization','')
    if not auth.startswith('Bearer '): return jsonify({'error':'Unauthorized'}),401
    guild_id  = flask_request.args.get('guild_id')
    backup_id = flask_request.args.get('backup_id')
    if not guild_id or not backup_id:
        return jsonify({'error':'guild_id and backup_id required'}),400
    doc = get_db().server_backups.find_one(
        {'backup_id': backup_id, 'guild_id': str(guild_id)}, {'_id':0}
    )
    if not doc: return jsonify({'error':'Not found'}),404
    # Return metadata + summary of snapshot (not full snapshot for performance)
    snap = doc.get('snapshot', {})
    doc['preview'] = {
        'roles':    [r['name'] for r in snap.get('roles',[])],
        'categories': [c['name'] for c in snap.get('categories',[])],
        'text_channels':  [c['name'] for c in snap.get('text_channels',[])],
        'voice_channels': [c['name'] for c in snap.get('voice_channels',[])],
        'emojis':   [e['name'] for e in snap.get('emojis',[])],
    }
    doc.pop('snapshot', None)
    return jsonify(doc)


# ══════════════════════════════════════════════════════════════
#  BOOSTER STATS
# ══════════════════════════════════════════════════════════════

@flask_app.route('/booster/stats', methods=['GET', 'OPTIONS'])
def booster_stats():
    if flask_request.method == 'OPTIONS':
        return _preflight()

    # Manual auth check (OPTIONS must bypass @require_auth for CORS preflight to work)
    auth = flask_request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({'error': 'Unauthorized'}), 401
    flask_request.discord_token = auth.split(' ', 1)[1]
    guild_id = flask_request.args.get('guild_id')
    if not guild_id:
        return jsonify({'error': 'guild_id required'}), 400
    # Get from live bot if available
    if _bot_ref and _bot_ref.is_ready():
        guild = _bot_ref.get_guild(int(guild_id))
        if guild:
            return jsonify({
                'total_boosts':    guild.premium_subscription_count or 0,
                'unique_boosters': len(guild.premium_subscribers),
                'server_level':    guild.premium_tier,
            })
    # Fallback to Discord API
    info = bot_discord_get(f'/guilds/{guild_id}?with_counts=true')
    return jsonify({
        'total_boosts':    info.get('premium_subscription_count', 0),
        'unique_boosters': 0,
        'server_level':    info.get('premium_tier', 0),
    })

# ══════════════════════════════════════════════════════════════
#  MONGODB STATS
# ══════════════════════════════════════════════════════════════

@flask_app.route('/db/stats', methods=['GET', 'OPTIONS'])
def db_stats():
    if flask_request.method == 'OPTIONS':
        return _preflight()

    # Manual auth check (OPTIONS must bypass @require_auth for CORS preflight to work)
    auth = flask_request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({'error': 'Unauthorized'}), 401
    flask_request.discord_token = auth.split(' ', 1)[1]
    try:
        db      = get_db()
        db_stat = db.command('dbStats')
        return jsonify({
            'users':           db.currency.count_documents({}),
            'guilds':          db.guild_settings.count_documents({}),
            'economy_entries': db.currency.count_documents({}),
            'xp_entries':      db.xp.count_documents({}),
            'collections':     len(db.list_collection_names()),
            'total_documents': int(db_stat.get('objects', 0)),
            'last_sync':       datetime.datetime.utcnow().strftime('%H:%M:%S UTC'),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ══════════════════════════════════════════════════════════════
#  CHANNELS — fetch text channels for a guild
# ══════════════════════════════════════════════════════════════

@flask_app.route('/channels', methods=['GET', 'OPTIONS'])
def get_channels():
    """Return text channels for a guild so dashboard can show a dropdown."""
    if flask_request.method == 'OPTIONS':
        return _preflight()

    # Manual auth check
    auth = flask_request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({'error': 'Unauthorized'}), 401

    guild_id = flask_request.args.get('guild_id')
    if not guild_id:
        return jsonify({'error': 'guild_id required'}), 400

    if _bot_ref and _bot_ref.is_ready():
        guild = _bot_ref.get_guild(int(guild_id))
        if guild:
            channels = [
                {'id': str(ch.id), 'name': ch.name, 'category': ch.category.name if ch.category else ''}
                for ch in sorted(guild.text_channels, key=lambda c: (c.category.position if c.category else 0, c.position))
            ]
            return jsonify(channels)

    # Fallback: use bot token to call Discord API
    data = bot_discord_get(f'/guilds/{guild_id}/channels')
    if isinstance(data, list):
        channels = [
            {'id': c['id'], 'name': c['name'], 'category': ''}
            for c in data if c.get('type') == 0  # type 0 = text channel
        ]
        return jsonify(sorted(channels, key=lambda c: c['name']))

    return jsonify([])


# ══════════════════════════════════════════════════════════════
#  ADMIN — Currency Manager
# ══════════════════════════════════════════════════════════════

@flask_app.route('/economy/admin', methods=['POST', 'OPTIONS'])
def economy_admin():
    """Admin-only: add/remove/set/reset a user's balance."""
    if flask_request.method == 'OPTIONS':
        return _preflight()

    auth = flask_request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({'error': 'Unauthorized'}), 401

    # Verify caller is the owner via Discord API
    try:
        caller = discord_user_get('/users/@me', auth.split(' ', 1)[1])
        if str(caller.get('id')) != '769225445803032617':
            return jsonify({'error': 'Forbidden — owner only'}), 403
    except Exception as e:
        return jsonify({'error': f'Could not verify identity: {e}'}), 401

    body     = flask_request.get_json(force=True) or {}
    action   = body.get('action')        # add | remove | set | reset
    guild_id = body.get('guild_id')
    user_id  = body.get('user_id')
    amount   = int(body.get('amount', 0))

    if not guild_id or not user_id:
        return jsonify({'error': 'guild_id and user_id required'}), 400

    from database import get_balance, set_balance
    data = get_balance(str(guild_id), str(user_id))
    old_balance = data['balance']

    if action == 'add':
        if amount <= 0: return jsonify({'error': 'Amount must be positive'}), 400
        data['balance'] += amount
    elif action == 'remove':
        if amount <= 0: return jsonify({'error': 'Amount must be positive'}), 400
        data['balance'] = max(0, data['balance'] - amount)
    elif action == 'set':
        if amount < 0: return jsonify({'error': 'Amount cannot be negative'}), 400
        data['balance'] = amount
    elif action == 'reset':
        data['balance'] = 0
    else:
        return jsonify({'error': 'Invalid action'}), 400

    set_balance(str(guild_id), str(user_id), data)

    username = resolve_username(str(user_id))
    return jsonify({
        'success':     True,
        'action':      action,
        'user_id':     user_id,
        'username':    username,
        'old_balance': old_balance,
        'new_balance': data['balance'],
    })

@flask_app.route('/economy/user', methods=['GET', 'OPTIONS'])
def economy_user():
    """Get a single user's balance. Admin only."""
    if flask_request.method == 'OPTIONS':
        return _preflight()

    auth = flask_request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        caller = discord_user_get('/users/@me', auth.split(' ', 1)[1])
        if str(caller.get('id')) != '769225445803032617':
            return jsonify({'error': 'Forbidden'}), 403
    except Exception as e:
        return jsonify({'error': str(e)}), 401

    guild_id = flask_request.args.get('guild_id')
    user_id  = flask_request.args.get('user_id')
    if not guild_id or not user_id:
        return jsonify({'error': 'guild_id and user_id required'}), 400

    from database import get_balance
    data = get_balance(str(guild_id), str(user_id))

    # Get avatar hash from bot cache
    avatar_hash = None
    discriminator = '0'
    if _bot_ref and _bot_ref.is_ready():
        user = _bot_ref.get_user(int(user_id))
        if user:
            avatar_hash = str(user.avatar.key) if user.avatar else None
            discriminator = str(user.discriminator) if hasattr(user, 'discriminator') else '0'

    return jsonify({
        'user_id':      user_id,
        'username':     resolve_username(str(user_id)),
        'avatar_hash':  avatar_hash,
        'discriminator': discriminator,
        'balance':      data['balance'],
        'wins':         data.get('wins', 0),
        'losses':       data.get('losses', 0),
    })

# # ══════════════════════════════════════════════════════════════
# #  MINECRAFT BRIDGE
# # ══════════════════════════════════════════════════════════════

# @flask_app.route('/minecraft/settings', methods=['GET', 'POST', 'OPTIONS'])
# def minecraft_settings():
#     if flask_request.method == 'OPTIONS':
#         return _preflight()
#     auth = flask_request.headers.get('Authorization', '')
#     if not auth.startswith('Bearer '):
#         return jsonify({'error': 'Unauthorized'}), 401

#     if flask_request.method == 'GET':
#         guild_id = flask_request.args.get('guild_id')
#         if not guild_id:
#             return jsonify({'error': 'guild_id required'}), 400
#         doc = get_db().minecraft_settings.find_one({'guild_id': str(guild_id)}, {'_id': 0})
#         return jsonify({'settings': doc or {}})

#     # POST — save settings
#     data     = flask_request.get_json(force=True) or {}
#     guild_id = data.get('guild_id')
#     if not guild_id:
#         return jsonify({'error': 'guild_id required'}), 400
#     get_db().minecraft_settings.update_one(
#         {'guild_id': str(guild_id)},
#         {'$set': {
#             'guild_id':        str(guild_id),
#             'chat_channel_id': str(data.get('chat_channel_id') or ''),
#             'log_channel_id':  str(data.get('log_channel_id')  or ''),
#         }},
#         upsert=True
#     )
#     return jsonify({'success': True})


# @flask_app.route('/minecraft/webhook', methods=['POST', 'OPTIONS'])
# def minecraft_webhook():
#     """
#     Called by DiscordSRV plugin on the Aternos server.
#     No auth — protected by the secret token in the payload instead.
#     """
#     if flask_request.method == 'OPTIONS':
#         return _preflight()

#     data = flask_request.get_json(force=True) or {}

#     # Optional secret check — set MINECRAFT_WEBHOOK_SECRET in env
#     secret = os.getenv('MINECRAFT_WEBHOOK_SECRET', '')
#     if secret and data.get('secret') != secret:
#         return jsonify({'error': 'Forbidden'}), 403

#     if not _bot_ref or not _bot_ref.is_ready():
#         return jsonify({'error': 'Bot not ready'}), 503

#     # Find the Minecraft cog and call handle_webhook
#     cog = _bot_ref.cogs.get('Minecraft')
#     if not cog:
#         return jsonify({'error': 'Minecraft cog not loaded'}), 500

#     future = asyncio.run_coroutine_threadsafe(
#         cog.handle_webhook(data), _bot_ref.loop
#     )
#     try:
#         future.result(timeout=10)
#     except Exception as e:
#         print(f'[Minecraft webhook] Error: {e}', flush=True)
#         return jsonify({'error': str(e)}), 500

#     return jsonify({'success': True})


# ══════════════════════════════════════════════════════════════
#  CORS preflight helper
# ══════════════════════════════════════════════════════════════

def _preflight():
    res = flask_app.make_default_options_response()
    res.headers['Access-Control-Allow-Origin']  = '*'
    res.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    res.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return res

# ══════════════════════════════════════════════════════════════
#  PUBLIC HELPER — call from your cogs to log mod actions
# ══════════════════════════════════════════════════════════════

def log_mod_action(action: str, target: str, moderator: str,
                   reason: str = '', guild_id: str = '', guild_name: str = ''):
    """
    Call this from any cog whenever a mod action happens.
    It writes to MongoDB so the Audit Log panel shows it.

    Example (inside a cog):
        from bot import log_mod_action
        log_mod_action('ban', str(member), str(ctx.author),
                       reason=reason, guild_id=str(ctx.guild.id),
                       guild_name=ctx.guild.name)
    """
    try:
        get_db().audit_log.insert_one({
            'action':     action,
            'target':     target,
            'moderator':  moderator,
            'reason':     reason,
            'guild_id':   str(guild_id),
            'guild_name': guild_name,
            'timestamp':  datetime.datetime.utcnow(),
        })
    except Exception as e:
        print(f'[AuditLog] Failed to write: {e}', flush=True)

# ══════════════════════════════════════════════════════════════
#  FLASK THREAD
# ══════════════════════════════════════════════════════════════

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

t = Thread(target=run_flask)
t.daemon = True
t.start()
print("✅ Flask thread started", flush=True)

# ══════════════════════════════════════════════════════════════
#  DISCORD BOT
# ══════════════════════════════════════════════════════════════

STATUS_CHANNEL_ID = int(os.getenv("STATUS_CHANNEL_ID", "1484110480699031672"))

COGS = [
    "cogs.music",
    "cogs.music_extras",
    "cogs.twitch",
    "cogs.ai",
    "cogs.levels",
    "cogs.fun",
    "cogs.images",
    "cogs.currency",
    "cogs.info",
    "cogs.moderation",
    "cogs.antinuke",
    "cogs.backup",
    # ── New features ──────────────────────────────────────────
    "cogs.tts",         # Text-to-Speech for Discord voice channels
    "cogs.minecraft",   # Minecraft ↔ Discord bridge + log watcher
]

def make_bot():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.voice_states    = True
    intents.members         = True
    intents.presences       = True
    return commands.Bot(
        command_prefix=os.getenv("BOT_PREFIX", "-"),
        intents=intents,
        help_command=None,
        max_messages=1000,
        chunk_guilds_at_startup=False,
    )

async def start_bot():
    global _bot_ref
    print("🔄 start_bot() called", flush=True)
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ DISCORD_TOKEN not set!", flush=True)
        return

    retry_delay = 30

    while True:
        bot = make_bot()
        _bot_ref = bot

        async def send_status(title, description, color):
            try:
                channel = bot.get_channel(STATUS_CHANNEL_ID)
                if not channel:
                    channel = await bot.fetch_channel(STATUS_CHANNEL_ID)
                embed = discord.Embed(title=title, description=description, color=color)
                embed.timestamp = datetime.datetime.now(timezone.utc)
                embed.set_footer(text="NinjuBot Status System")
                await channel.send(embed=embed)
            except Exception as e:
                print(f"[Status] Failed: {e}", flush=True)

        @bot.event
        async def on_ready():
            print(f"✅ Logged in as {bot.user} ({bot.user.id})", flush=True)
            print(f"📡 Connected to {len(bot.guilds)} server(s)", flush=True)
            # Seed audit log with a startup entry so dashboard shows data immediately
            for g in bot.guilds:
                log_mod_action(
                    action='bot_start',
                    target=f'{bot.user}',
                    moderator='System',
                    reason=f'Bot connected to {len(bot.guilds)} servers',
                    guild_id=str(g.id),
                    guild_name=g.name
                )
            try:
                synced = await bot.tree.sync()
                print(f"✅ Synced {len(synced)} global slash command(s)", flush=True)
            except Exception as e:
                print(f"❌ Slash sync failed: {e}", flush=True)
            await bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name=f"-ninju | {len(bot.guilds)} servers"
                )
            )
            await send_status(
                "✅ NinjuBot is Online!",
                f"**Servers:** {len(bot.guilds)}\n**Users:** {sum(g.member_count for g in bot.guilds):,}",
                0x2ECC71
            )

        @bot.event
        async def on_guild_join(guild):
            print(f"➕ Joined: {guild.name} ({guild.id})", flush=True)
            await bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name=f"-ninju | {len(bot.guilds)} servers"
                )
            )
            embed = discord.Embed(
                title="🥷 Hey! I'm NinjuBot!",
                description=(
                    "Thanks for adding me to **{}**!\n\n"
                    "**Getting Started:**\n"
                    "📖 `-ninju` — View all commands\n"
                    "🎵 `/play <song>` — Play music\n"
                    "💰 `-daily` — Claim daily coins\n"
                    "🎭 `-tod @user` — Truth or Dare\n"
                    "🤖 `-ask <question>` — Chat with AI\n\n"
                    "**Need help?** Use `-ninju` to see all commands!"
                ).format(guild.name),
                color=0xFF4500
            )
            embed.set_thumbnail(url=bot.user.display_avatar.url)
            embed.set_footer(text="NinjuBot | Made by sdb_darkninja")
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages:
                    try:
                        await ch.send(embed=embed)
                        break
                    except:
                        continue

        @bot.event
        async def on_guild_remove(guild):
            print(f"➖ Left: {guild.name} ({guild.id})", flush=True)
            await bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name=f"-ninju | {len(bot.guilds)} servers"
                )
            )

        @bot.event
        async def on_resumed():
            print("✅ Bot reconnected!", flush=True)
            await send_status("🔄 NinjuBot Reconnected", "Bot reconnected to Discord.", 0x3498DB)

        @bot.event
        async def on_command_error(ctx, error):
            if isinstance(error, commands.CommandNotFound):
                return
            elif isinstance(error, commands.MissingRequiredArgument):
                await ctx.send(f"❌ Missing: `{error.param.name}`. Use `-ninju` for help.")
            elif isinstance(error, commands.MissingPermissions):
                await ctx.send("❌ You don't have permission to do that.")
            elif isinstance(error, commands.BotMissingPermissions):
                await ctx.send("❌ I don't have permission to do that.")
            elif isinstance(error, commands.CommandOnCooldown):
                await ctx.send(f"⏳ Cooldown! Try again in `{error.retry_after:.1f}s`.")
            elif isinstance(error, commands.CommandInvokeError):
                if isinstance(error.original, asyncio.TimeoutError):
                    return
                print(f"[CmdError] {error}", flush=True)

        for cog in COGS:
            try:
                await bot.load_extension(cog)
                print(f"  ✅ {cog}", flush=True)
            except Exception as e:
                print(f"  ❌ {cog}: {e}", flush=True)

        try:
            print("🔄 Attempting to connect to Discord...", flush=True)
            await bot.start(token)
            break
        except discord.errors.HTTPException as e:
            if e.status == 429:
                print(f"⚠️ Rate limited. Waiting {retry_delay}s...", flush=True)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 600)
            else:
                print(f"❌ HTTP error: {e}", flush=True)
                await asyncio.sleep(60)
        except Exception as e:
            print(f"❌ Unexpected error: {type(e).__name__}: {e}", flush=True)
            await asyncio.sleep(60)

print("▶️ Calling asyncio.run(start_bot())", flush=True)
asyncio.run(start_bot())
