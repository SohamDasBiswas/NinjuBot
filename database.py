import os
from pymongo import MongoClient

_client = None
_db = None

def get_db():
    global _client, _db
    if _db is not None:
        return _db
    uri = os.getenv("MONGODB_URI", "")
    if not uri:
        raise ValueError("MONGODB_URI not set!")
    _client = MongoClient(uri, serverSelectionTimeoutMS=30000)
    _db = _client["ninjubot"]
    print("✅ MongoDB connected")
    return _db

def init_db():
    try:
        db = get_db()
        db.currency.create_index("key", unique=True)
        db.xp.create_index("key", unique=True)
        db.twitch_channels.create_index("guild_id", unique=True)
        print("✅ MongoDB indexes created")
    except Exception as e:
        print(f"⚠️ MongoDB init warning: {e}")

# ── Currency ──────────────────────────────────────────────────────────────────

def get_balance(guild_id, user_id):
    key = f"{guild_id}_{user_id}"
    try:
        doc = get_db().currency.find_one({"key": key})
        if doc:
            return {k: doc.get(k, d) for k, d in [
                ("balance", 100), ("last_daily", 0),
                ("last_work", 0), ("wins", 0), ("losses", 0)
            ]}
    except Exception as e:
        print(f"[DB] get_balance: {e}")
    return {"balance": 100, "last_daily": 0, "last_work": 0, "wins": 0, "losses": 0}

def set_balance(guild_id, user_id, data):
    key = f"{guild_id}_{user_id}"
    try:
        get_db().currency.update_one(
            {"key": key},
            {"$set": {"key": key, "guild_id": str(guild_id), "user_id": str(user_id),
                      "balance": data.get("balance", 100), "last_daily": data.get("last_daily", 0),
                      "last_work": data.get("last_work", 0), "wins": data.get("wins", 0),
                      "losses": data.get("losses", 0)}},
            upsert=True
        )
    except Exception as e:
        print(f"[DB] set_balance: {e}")

def get_top_currency(guild_id, limit=10):
    try:
        return list(get_db().currency.find(
            {"guild_id": str(guild_id)}, {"key": 1, "balance": 1}
        ).sort("balance", -1).limit(limit))
    except Exception as e:
        print(f"[DB] get_top_currency: {e}")
        return []

# ── XP ────────────────────────────────────────────────────────────────────────

def get_xp(guild_id, user_id):
    key = f"{guild_id}_{user_id}"
    try:
        doc = get_db().xp.find_one({"key": key})
        if doc:
            return {"xp": doc.get("xp", 0), "level": doc.get("level", 0)}
    except Exception as e:
        print(f"[DB] get_xp: {e}")
    return {"xp": 0, "level": 0}

def set_xp(guild_id, user_id, data):
    key = f"{guild_id}_{user_id}"
    try:
        get_db().xp.update_one(
            {"key": key},
            {"$set": {"key": key, "guild_id": str(guild_id), "user_id": str(user_id),
                      "xp": data.get("xp", 0), "level": data.get("level", 0)}},
            upsert=True
        )
    except Exception as e:
        print(f"[DB] set_xp: {e}")

def get_top_xp(guild_id, limit=10):
    try:
        return list(get_db().xp.find(
            {"guild_id": str(guild_id)}, {"key": 1, "xp": 1, "level": 1}
        ).sort("xp", -1).limit(limit))
    except Exception as e:
        print(f"[DB] get_top_xp: {e}")
        return []

# ── Twitch ────────────────────────────────────────────────────────────────────

def load_twitch_channels():
    try:
        result = {}
        for doc in get_db().twitch_channels.find({}):
            result[int(doc["guild_id"])] = {
                "followers": int(doc["followers_vc"]),
                "status":    int(doc["status_vc"]),
                "viewers":   int(doc["viewers_vc"]),
                "game":      int(doc["game_vc"]),
            }
        return result
    except Exception as e:
        print(f"[DB] load_twitch_channels: {e}")
        return {}

def save_twitch_channel(guild_id, ids):
    try:
        get_db().twitch_channels.update_one(
            {"guild_id": str(guild_id)},
            {"$set": {"guild_id": str(guild_id), "followers_vc": str(ids["followers"]),
                      "status_vc": str(ids["status"]), "viewers_vc": str(ids["viewers"]),
                      "game_vc": str(ids["game"])}},
            upsert=True
        )
    except Exception as e:
        print(f"[DB] save_twitch_channel: {e}")

def delete_twitch_channel(guild_id):
    try:
        get_db().twitch_channels.delete_one({"guild_id": str(guild_id)})
    except Exception as e:
        print(f"[DB] delete_twitch_channel: {e}")

def get_conn():
    class _P:
        def execute(self, *a, **k): return type('R', (), {'fetchall': lambda s: []})()
        def commit(self): pass
        def close(self): pass
    return _P()
