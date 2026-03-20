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

    # Inject tlsInsecure into URI if not already present
    if "tlsInsecure" not in uri and "tlsAllowInvalidCertificates" not in uri:
        sep = "&" if "?" in uri else "?"
        uri = uri + sep + "tls=true&tlsInsecure=true"

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
        db = get_db()
        doc = db.currency.find_one({"key": key})
        if doc:
            return {
                "balance": doc.get("balance", 100),
                "last_daily": doc.get("last_daily", 0),
                "last_work": doc.get("last_work", 0),
                "wins": doc.get("wins", 0),
                "losses": doc.get("losses", 0),
            }
    except Exception as e:
        print(f"[DB] get_balance error: {e}")
    return {"balance": 100, "last_daily": 0, "last_work": 0, "wins": 0, "losses": 0}

def set_balance(guild_id, user_id, data):
    key = f"{guild_id}_{user_id}"
    try:
        db = get_db()
        db.currency.update_one(
            {"key": key},
            {"$set": {
                "key": key,
                "guild_id": str(guild_id),
                "user_id": str(user_id),
                "balance": data.get("balance", 100),
                "last_daily": data.get("last_daily", 0),
                "last_work": data.get("last_work", 0),
                "wins": data.get("wins", 0),
                "losses": data.get("losses", 0),
            }},
            upsert=True
        )
    except Exception as e:
        print(f"[DB] set_balance error: {e}")

def get_top_currency(guild_id, limit=10):
    try:
        db = get_db()
        docs = db.currency.find(
            {"guild_id": str(guild_id)},
            {"key": 1, "balance": 1}
        ).sort("balance", -1).limit(limit)
        return list(docs)
    except Exception as e:
        print(f"[DB] get_top_currency error: {e}")
        return []

# ── XP / Levels ───────────────────────────────────────────────────────────────

def get_xp(guild_id, user_id):
    key = f"{guild_id}_{user_id}"
    try:
        db = get_db()
        doc = db.xp.find_one({"key": key})
        if doc:
            return {"xp": doc.get("xp", 0), "level": doc.get("level", 0)}
    except Exception as e:
        print(f"[DB] get_xp error: {e}")
    return {"xp": 0, "level": 0}

def set_xp(guild_id, user_id, data):
    key = f"{guild_id}_{user_id}"
    try:
        db = get_db()
        db.xp.update_one(
            {"key": key},
            {"$set": {
                "key": key,
                "guild_id": str(guild_id),
                "user_id": str(user_id),
                "xp": data.get("xp", 0),
                "level": data.get("level", 0),
            }},
            upsert=True
        )
    except Exception as e:
        print(f"[DB] set_xp error: {e}")

def get_top_xp(guild_id, limit=10):
    try:
        db = get_db()
        docs = db.xp.find(
            {"guild_id": str(guild_id)},
            {"key": 1, "xp": 1, "level": 1}
        ).sort("xp", -1).limit(limit)
        return list(docs)
    except Exception as e:
        print(f"[DB] get_top_xp error: {e}")
        return []

# ── Twitch ────────────────────────────────────────────────────────────────────

def load_twitch_channels():
    try:
        db = get_db()
        docs = db.twitch_channels.find({})
        result = {}
        for doc in docs:
            result[int(doc["guild_id"])] = {
                "followers": int(doc["followers_vc"]),
                "status":    int(doc["status_vc"]),
                "viewers":   int(doc["viewers_vc"]),
                "game":      int(doc["game_vc"]),
            }
        return result
    except Exception as e:
        print(f"[DB] load_twitch_channels error: {e}")
        return {}

def save_twitch_channel(guild_id, ids):
    try:
        db = get_db()
        db.twitch_channels.update_one(
            {"guild_id": str(guild_id)},
            {"$set": {
                "guild_id":     str(guild_id),
                "followers_vc": str(ids["followers"]),
                "status_vc":    str(ids["status"]),
                "viewers_vc":   str(ids["viewers"]),
                "game_vc":      str(ids["game"]),
            }},
            upsert=True
        )
    except Exception as e:
        print(f"[DB] save_twitch_channel error: {e}")

def delete_twitch_channel(guild_id):
    try:
        db = get_db()
        db.twitch_channels.delete_one({"guild_id": str(guild_id)})
    except Exception as e:
        print(f"[DB] delete_twitch_channel error: {e}")

# ── Legacy shim ───────────────────────────────────────────────────────────────
def get_conn():
    class _P:
        def execute(self, *a, **k): return type('R', (), {'fetchall': lambda s: []})()
        def commit(self): pass
        def close(self): pass
    return _P()
