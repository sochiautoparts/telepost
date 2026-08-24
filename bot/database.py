"""Telepost Database — SQLite async (aiosqlite), WAL mode."""
import logging, time
from typing import List, Optional, Dict, Any
import aiosqlite
from bot.config import config

logger = logging.getLogger("telepost.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT DEFAULT '',
    first_name TEXT DEFAULT '',
    last_name TEXT DEFAULT '',
    is_bot INTEGER DEFAULT 0,
    first_seen INTEGER NOT NULL,
    last_seen INTEGER NOT NULL,
    msg_count INTEGER DEFAULT 0,
    ads_count INTEGER DEFAULT 0,
    is_banned INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    price REAL,
    currency TEXT DEFAULT 'RUB',
    category TEXT DEFAULT 'other',
    city TEXT DEFAULT '',
    lat REAL,
    lng REAL,
    address TEXT DEFAULT '',
    photos TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    tg_message_id INTEGER,
    tg_post_url TEXT DEFAULT '',
    view_count INTEGER DEFAULT 0,
    created_at INTEGER NOT NULL,
    expires_at INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_ads_user ON ads(user_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_ads_status ON ads(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ads_category ON ads(category, status);

CREATE TABLE IF NOT EXISTS places (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    category TEXT DEFAULT 'other',
    phone TEXT DEFAULT '',
    website TEXT DEFAULT '',
    address TEXT DEFAULT '',
    city TEXT DEFAULT '',
    lat REAL,
    lng REAL,
    description TEXT DEFAULT '',
    photos TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    tg_message_id INTEGER,
    tg_post_url TEXT DEFAULT '',
    created_at INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_places_user ON places(user_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_places_status ON places(status, created_at DESC);

CREATE TABLE IF NOT EXISTS donations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    stars_amount INTEGER,
    telegram_charge_id TEXT,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_donations_user ON donations(user_id);

CREATE TABLE IF NOT EXISTS user_state (
    user_id INTEGER PRIMARY KEY,
    state TEXT DEFAULT '',
    data TEXT DEFAULT '{}',
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS channel_posts (
    message_id INTEGER PRIMARY KEY,
    ad_id INTEGER,
    place_id INTEGER,
    post_type TEXT DEFAULT 'ad',
    created_at INTEGER NOT NULL
);
"""

_db: Optional[aiosqlite.Connection] = None

async def init_db():
    global _db
    import os
    os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)
    _db = await aiosqlite.connect(config.DB_PATH)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL;")
    await _db.execute("PRAGMA synchronous=NORMAL;")
    await _db.executescript(_SCHEMA)
    await _db.commit()
    logger.info(f"DB ready at {config.DB_PATH}")

async def close_db():
    global _db
    if _db: await _db.close(); _db = None

def _conn():
    if _db is None: raise RuntimeError("DB not initialised")
    return _db

# ─── Users ──────────────────────────────────────────────────────────────────

async def upsert_user(user_id: int, username: str = "", first_name: str = "", last_name: str = "", is_bot: bool = False):
    now = int(time.time())
    await _conn().execute(
        "INSERT INTO users(user_id, username, first_name, last_name, is_bot, first_seen, last_seen, msg_count) "
        "VALUES(?,?,?,?,?,?,?,1) ON CONFLICT(user_id) DO UPDATE SET "
        "username=excluded.username, first_name=excluded.first_name, last_name=excluded.last_name, "
        "last_seen=excluded.last_seen, msg_count=users.msg_count+1",
        (user_id, username, first_name, last_name, int(is_bot), now, now)
    )
    await _conn().commit()

async def get_user(user_id: int) -> Optional[Dict]:
    cur = await _conn().execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = await cur.fetchone()
    return dict(row) if row else None

async def ban_user(user_id: int, banned: bool = True):
    await _conn().execute("UPDATE users SET is_banned=? WHERE user_id=?", (int(banned), user_id))
    await _conn().commit()

async def is_banned(user_id: int) -> bool:
    cur = await _conn().execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,))
    row = await cur.fetchone()
    return bool(row and row["is_banned"])

# ─── Ads ────────────────────────────────────────────────────────────────────

async def create_ad(user_id: int, title: str, description: str, price: float, currency: str,
                    category: str, city: str, lat: float, lng: float, address: str, photos: str) -> int:
    now = int(time.time())
    expires = now + config.AD_EXPIRE_DAYS * 86400
    cur = await _conn().execute(
        "INSERT INTO ads(user_id, title, description, price, currency, category, city, lat, lng, address, photos, status, created_at, expires_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,'active',?,?)",
        (user_id, title, description, price, currency, category, city, lat, lng, address, photos, now, expires)
    )
    await _conn().commit()
    await _conn().execute("UPDATE users SET ads_count=ads_count+1 WHERE user_id=?", (user_id,))
    await _conn().commit()
    return cur.lastrowid

async def update_ad_tg(ad_id: int, message_id: int, post_url: str):
    await _conn().execute("UPDATE ads SET tg_message_id=?, tg_post_url=? WHERE id=?", (message_id, post_url, ad_id))
    await _conn().commit()

async def get_ad(ad_id: int) -> Optional[Dict]:
    cur = await _conn().execute("SELECT * FROM ads WHERE id=?", (ad_id,))
    row = await cur.fetchone()
    return dict(row) if row else None

async def get_user_ads(user_id: int, limit: int = 10) -> List[Dict]:
    cur = await _conn().execute("SELECT * FROM ads WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit))
    return [dict(r) for r in await cur.fetchall()]

async def delete_ad(ad_id: int, user_id: int) -> bool:
    cur = await _conn().execute("UPDATE ads SET status='deleted' WHERE id=? AND user_id=?", (ad_id, user_id))
    await _conn().commit()
    return cur.rowcount > 0

async def get_recent_ads(limit: int = 20) -> List[Dict]:
    cur = await _conn().execute("SELECT * FROM ads WHERE status='active' ORDER BY id DESC LIMIT ?", (limit,))
    return [dict(r) for r in await cur.fetchall()]

# ─── Places ─────────────────────────────────────────────────────────────────

async def create_place(user_id: int, name: str, category: str, phone: str, website: str,
                       address: str, city: str, lat: float, lng: float, description: str, photos: str) -> int:
    now = int(time.time())
    cur = await _conn().execute(
        "INSERT INTO places(user_id, name, category, phone, website, address, city, lat, lng, description, photos, status, created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,'active',?)",
        (user_id, name, category, phone, website, address, city, lat, lng, description, photos, now)
    )
    await _conn().commit()
    return cur.lastrowid

async def update_place_tg(place_id: int, message_id: int, post_url: str):
    await _conn().execute("UPDATE places SET tg_message_id=?, tg_post_url=? WHERE id=?", (message_id, post_url, place_id))
    await _conn().commit()

async def get_user_places(user_id: int, limit: int = 10) -> List[Dict]:
    cur = await _conn().execute("SELECT * FROM places WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit))
    return [dict(r) for r in await cur.fetchall()]

# ─── Donations ──────────────────────────────────────────────────────────────

async def record_donation(user_id: int, stars: int, charge_id: str):
    await _conn().execute("INSERT INTO donations(user_id, stars_amount, telegram_charge_id, created_at) VALUES(?,?,?,?)",
                          (user_id, stars, charge_id, int(time.time())))
    await _conn().commit()

async def get_total_donated(user_id: int) -> int:
    cur = await _conn().execute("SELECT COALESCE(SUM(stars_amount),0) as total FROM donations WHERE user_id=?", (user_id,))
    row = await cur.fetchone()
    return int(row["total"]) if row else 0

# ─── User State (FSM) ───────────────────────────────────────────────────────

async def set_state(user_id: int, state: str, data: str = "{}"):
    await _conn().execute(
        "INSERT INTO user_state(user_id, state, data, updated_at) VALUES(?,?,?,?) "
        "ON CONFLICT(user_id) DO UPDATE SET state=excluded.state, data=excluded.data, updated_at=excluded.updated_at",
        (user_id, state, data, int(time.time()))
    )
    await _conn().commit()

async def get_state(user_id: int) -> tuple[str, str]:
    cur = await _conn().execute("SELECT state, data FROM user_state WHERE user_id=?", (user_id,))
    row = await cur.fetchone()
    if row: return row["state"], row["data"]
    return "", "{}"

async def clear_state(user_id: int):
    await _conn().execute("UPDATE user_state SET state='', data='{}' WHERE user_id=?", (user_id,))
    await _conn().commit()

# ─── Channel Posts ──────────────────────────────────────────────────────────

async def record_channel_post(message_id: int, ad_id: int = None, place_id: int = None, post_type: str = "ad"):
    await _conn().execute(
        "INSERT OR REPLACE INTO channel_posts(message_id, ad_id, place_id, post_type, created_at) VALUES(?,?,?,?,?)",
        (message_id, ad_id, place_id, post_type, int(time.time()))
    )
    await _conn().commit()

# ─── Stats ──────────────────────────────────────────────────────────────────

async def get_stats() -> Dict[str, int]:
    stats = {}
    cur = await _conn().execute("SELECT COUNT(*) as c FROM users")
    stats["users"] = (await cur.fetchone())["c"]
    cur = await _conn().execute("SELECT COUNT(*) as c FROM ads WHERE status='active'")
    stats["ads"] = (await cur.fetchone())["c"]
    cur = await _conn().execute("SELECT COUNT(*) as c FROM places WHERE status='active'")
    stats["places"] = (await cur.fetchone())["c"]
    cur = await _conn().execute("SELECT COALESCE(SUM(stars_amount),0) as s FROM donations")
    stats["stars"] = (await cur.fetchone())["s"]
    return stats
