"""
db.py — CMT Voice Cloud database layer.
Uses Postgres (via DATABASE_URL) so the dashboard (Streamlit) and the
API (Render) share the SAME database — fixing the "invalid key" issue
that happens when each service has its own isolated local file.

Set DATABASE_URL environment variable to your Neon/Postgres connection string.
"""

import os
import secrets
import hashlib
import datetime
import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Pricing (in South African cents, to avoid float issues)
PRICE_PER_1000_CHARS_TTS = 50
PRICE_PER_MINUTE_STT = 200
PRICE_PER_VOICE_CLONE = 5000
PRICE_PER_1000_TOKENS_CHAT = 100

FREE_CREDITS_CENTS = 2000

PLANS = {
    "payg":    {"label": "Pay As You Go", "monthly_price": 0,     "included_credits": 0},
    "starter": {"label": "Starter",       "monthly_price": 19900, "included_credits": 25000},
    "growth":  {"label": "Growth",        "monthly_price": 49900, "included_credits": 70000},
}


def get_conn():
    if not DATABASE_URL:
        raise EnvironmentError(
            "\n\nNo DATABASE_URL set!\n"
            "Get a free Postgres database at https://neon.tech\n"
            "Then set: setx DATABASE_URL \"postgresql://...\"\n"
        )
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS developers (
            email TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            company_name TEXT,
            plan TEXT DEFAULT 'payg',
            plan_expires_at TEXT,
            credits_cents INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS api_keys (
            api_key TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            label TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            last_used_at TEXT
        );
        CREATE TABLE IF NOT EXISTS usage_log (
            id SERIAL PRIMARY KEY,
            email TEXT NOT NULL,
            api_key TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            cost_cents INTEGER NOT NULL,
            meta TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS topups (
            id SERIAL PRIMARY KEY,
            email TEXT NOT NULL,
            amount_cents INTEGER NOT NULL,
            checkout_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS cloned_voices (
            voice_id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            language_key TEXT,
            voice_name TEXT NOT NULL,
            elevenlabs_voice_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS contributions (
            id SERIAL PRIMARY KEY,
            language_key TEXT NOT NULL,
            original_text TEXT NOT NULL,
            english_translation TEXT NOT NULL,
            audio_base64 TEXT NOT NULL,
            contributor_name TEXT,
            contributor_email TEXT,
            elevenlabs_voice_id TEXT,
            created_at TEXT NOT NULL
        );
    """)
    conn.commit()
    c.close()
    conn.close()


# ── Auth ──────────────────────────────────────────────────────────────────────
def _hash(pw, salt):
    return hashlib.sha256((salt + pw).encode()).hexdigest()


def create_developer(email, password, company_name=""):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM developers WHERE email=%s", (email,))
    if c.fetchone():
        c.close()
        conn.close()
        return None

    salt = secrets.token_hex(16)
    now = datetime.datetime.now().isoformat()
    c.execute(
        "INSERT INTO developers (email,password_hash,salt,company_name,credits_cents,created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (email, _hash(password, salt), salt, company_name, FREE_CREDITS_CENTS, now))

    api_key = _generate_key()
    c.execute("INSERT INTO api_keys (api_key,email,label,created_at) VALUES (%s,%s,%s,%s)",
              (api_key, email, "Default key", now))
    conn.commit()
    c.close()
    conn.close()
    return api_key


def verify_login(email, password):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT password_hash,salt FROM developers WHERE email=%s", (email,))
    row = c.fetchone()
    c.close()
    conn.close()
    return row and _hash(password, row["salt"]) == row["password_hash"]


def get_developer(email):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM developers WHERE email=%s", (email,))
    row = c.fetchone()
    c.close()
    conn.close()
    return dict(row) if row else None


# ── API keys ──────────────────────────────────────────────────────────────────
def _generate_key():
    return "cmt_" + secrets.token_urlsafe(32)


def create_api_key(email, label="New key"):
    key = _generate_key()
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO api_keys (api_key,email,label,created_at) VALUES (%s,%s,%s,%s)",
              (key, email, label, datetime.datetime.now().isoformat()))
    conn.commit()
    c.close()
    conn.close()
    return key


def get_api_keys(email):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM api_keys WHERE email=%s ORDER BY created_at DESC", (email,))
    rows = c.fetchall()
    c.close()
    conn.close()
    return [dict(r) for r in rows]


def get_email_for_key(api_key):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT email FROM api_keys WHERE api_key=%s AND active=1", (api_key,))
    row = c.fetchone()
    c.close()
    conn.close()
    return row["email"] if row else None


def revoke_api_key(api_key):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE api_keys SET active=0 WHERE api_key=%s", (api_key,))
    conn.commit()
    c.close()
    conn.close()


def touch_api_key(api_key):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE api_keys SET last_used_at=%s WHERE api_key=%s",
              (datetime.datetime.now().isoformat(), api_key))
    conn.commit()
    c.close()
    conn.close()


# ── Credits & billing ──────────────────────────────────────────────────────────
def get_balance(email) -> int:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT credits_cents FROM developers WHERE email=%s", (email,))
    row = c.fetchone()
    c.close()
    conn.close()
    return row["credits_cents"] if row else 0


def has_sufficient_balance(email, cost_cents) -> bool:
    return get_balance(email) >= cost_cents


def deduct_credits(email, cost_cents, endpoint, meta=""):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE developers SET credits_cents = credits_cents - %s WHERE email=%s",
              (cost_cents, email))
    c.execute(
        "INSERT INTO usage_log (email,api_key,endpoint,cost_cents,meta,created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (email, "", endpoint, cost_cents, meta, datetime.datetime.now().isoformat()))
    conn.commit()
    c.close()
    conn.close()


def add_credits(email, amount_cents):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE developers SET credits_cents = credits_cents + %s WHERE email=%s",
              (amount_cents, email))
    conn.commit()
    c.close()
    conn.close()


def get_usage_history(email, limit=50):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM usage_log WHERE email=%s ORDER BY created_at DESC LIMIT %s",
        (email, limit))
    rows = c.fetchall()
    c.close()
    conn.close()
    return [dict(r) for r in rows]


def get_usage_summary(email):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT COUNT(*) as calls, COALESCE(SUM(cost_cents),0) as total_spent "
        "FROM usage_log WHERE email=%s", (email,))
    row = c.fetchone()
    c.close()
    conn.close()
    return dict(row)


# ── Topups (Yoco payments) ──────────────────────────────────────────────────────
def create_topup(email, amount_cents, checkout_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO topups (email,amount_cents,checkout_id,created_at) VALUES (%s,%s,%s,%s)",
              (email, amount_cents, checkout_id, datetime.datetime.now().isoformat()))
    conn.commit()
    c.close()
    conn.close()


def complete_topup(checkout_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM topups WHERE checkout_id=%s AND status='pending'", (checkout_id,))
    row = c.fetchone()
    if not row:
        c.close()
        conn.close()
        return False
    c.execute("UPDATE topups SET status='completed' WHERE checkout_id=%s", (checkout_id,))
    c.execute("UPDATE developers SET credits_cents = credits_cents + %s WHERE email=%s",
              (row["amount_cents"], row["email"]))
    conn.commit()
    c.close()
    conn.close()
    return True


# ── Cloned voices ────────────────────────────────────────────────────────────────
def save_cloned_voice(voice_id, email, language_key, voice_name, elevenlabs_voice_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO cloned_voices (voice_id,email,language_key,voice_name,elevenlabs_voice_id,created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (voice_id, email, language_key, voice_name, elevenlabs_voice_id,
         datetime.datetime.now().isoformat()))
    conn.commit()
    c.close()
    conn.close()


def get_cloned_voices(email):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM cloned_voices WHERE email=%s ORDER BY created_at DESC", (email,))
    rows = c.fetchall()
    c.close()
    conn.close()
    return [dict(r) for r in rows]


def get_cloned_voice(voice_id, email):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM cloned_voices WHERE voice_id=%s AND email=%s", (voice_id, email))
    row = c.fetchone()
    c.close()
    conn.close()
    return dict(row) if row else None


# ── Admin ─────────────────────────────────────────────────────────────────────
def platform_stats():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as n FROM developers")
    total_developers = c.fetchone()["n"]
    c.execute("SELECT COUNT(*) as n FROM usage_log")
    total_api_calls = c.fetchone()["n"]
    c.execute("SELECT COALESCE(SUM(amount_cents),0) as n FROM topups WHERE status='completed'")
    total_revenue_cents = c.fetchone()["n"]
    c.execute("SELECT COUNT(*) as n FROM cloned_voices")
    total_cloned_voices = c.fetchone()["n"]
    c.close()
    conn.close()
    return {
        "total_developers": total_developers,
        "total_api_calls": total_api_calls,
        "total_revenue_cents": total_revenue_cents,
        "total_cloned_voices": total_cloned_voices,
    }


# ── Community language contributions ──────────────────────────────────────────
def save_contribution(language_key, original_text, english_translation, audio_base64,
                       contributor_name=None, contributor_email=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO contributions "
        "(language_key, original_text, english_translation, audio_base64, "
        "contributor_name, contributor_email, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (language_key, original_text, english_translation, audio_base64,
         contributor_name, contributor_email, datetime.datetime.now().isoformat()))
    new_id = c.fetchone()["id"]
    conn.commit()
    c.close()
    conn.close()
    return new_id


def get_contribution_stats():
    """Returns count of contributions per language, for a public leaderboard."""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT language_key, COUNT(*) as count FROM contributions "
        "GROUP BY language_key ORDER BY count DESC"
    )
    rows = c.fetchall()
    c.execute("SELECT COUNT(*) as total FROM contributions")
    total = c.fetchone()["total"]
    c.execute("SELECT COUNT(DISTINCT contributor_email) as n FROM contributions WHERE contributor_email IS NOT NULL")
    contributors = c.fetchone()["n"]
    c.close()
    conn.close()
    return {
        "by_language": {r["language_key"]: r["count"] for r in rows},
        "total_contributions": total,
        "total_contributors": contributors,
    }


def get_contributions(language_key=None, limit=100):
    conn = get_conn()
    c = conn.cursor()
    if language_key:
        c.execute(
            "SELECT id, language_key, original_text, english_translation, "
            "contributor_name, created_at FROM contributions "
            "WHERE language_key=%s ORDER BY created_at DESC LIMIT %s",
            (language_key, limit))
    else:
        c.execute(
            "SELECT id, language_key, original_text, english_translation, "
            "contributor_name, created_at FROM contributions "
            "ORDER BY created_at DESC LIMIT %s", (limit,))
    rows = c.fetchall()
    c.close()
    conn.close()
    return [dict(r) for r in rows]
