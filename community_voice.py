"""
community_voice.py — Auto-builds a growing "community voice" per language
from crowdsourced audio contributions, using ElevenLabs voice cloning.

This is an ADD-ON module for your existing CMT Voice Cloud project.
It does not modify db.py or main.py directly — instead, import and call
these functions from your existing files (see the wiring instructions
at the bottom of this file).

How it works:
    1. Someone contributes audio via /v1/contribute/submit (existing endpoint)
    2. After saving, call rebuild_community_voice(language_key)
    3. That function pulls the most recent N audio samples for that
       language from the contributions table, sends them ALL to
       ElevenLabs to (re)create a cloned voice, and stores the
       resulting voice_id — so the voice literally gets better/more
       representative as more people contribute.
    4. The old ElevenLabs voice is deleted after a successful rebuild,
       so you don't accumulate unused voices on your ElevenLabs account.
"""

import os
import base64
import tempfile
import requests
import datetime

ELEVENLABS_API = "https://api.elevenlabs.io/v1"

# How many of the most recent contributions to use when (re)building a
# language's community voice. Capped to keep ElevenLabs requests fast
# and reliable — using every single contribution ever made would make
# the clone slow to build and could hit ElevenLabs' upload limits.
MAX_SAMPLES_PER_VOICE = 20

# Only rebuild the voice every N contributions (not every single one) to
# avoid hammering the ElevenLabs API. Set to 1 to rebuild on every
# contribution (fine while volume is low); raise it once you have many
# contributors so you're not re-cloning constantly.
REBUILD_EVERY_N_CONTRIBUTIONS = 1


def _get_elevenlabs_key():
    key = os.environ.get("CMT_ELEVENLABS_KEY", "")
    if not key:
        raise EnvironmentError(
            "No ElevenLabs key found. Set CMT_ELEVENLABS_KEY environment variable."
        )
    return key


# ── Database functions (Postgres — matches your existing db.py style) ─────────
def init_community_voice_table(get_conn):
    """Call this once at startup, same pattern as your other init_db() calls."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS community_voices (
            language_key TEXT PRIMARY KEY,
            elevenlabs_voice_id TEXT NOT NULL,
            sample_count INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
    """)
    conn.commit()
    c.close()
    conn.close()


def get_community_voice(get_conn, language_key):
    """Returns {elevenlabs_voice_id, sample_count, updated_at} or None."""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM community_voices WHERE language_key=%s", (language_key,)
    )
    row = c.fetchone()
    c.close()
    conn.close()
    return dict(row) if row else None


def get_all_community_voices(get_conn):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM community_voices")
    rows = c.fetchall()
    c.close()
    conn.close()
    return [dict(r) for r in rows]


def _save_community_voice(get_conn, language_key, elevenlabs_voice_id, sample_count):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO community_voices (language_key, elevenlabs_voice_id, sample_count, updated_at) "
        "VALUES (%s,%s,%s,%s) "
        "ON CONFLICT (language_key) DO UPDATE SET "
        "elevenlabs_voice_id=%s, sample_count=%s, updated_at=%s",
        (language_key, elevenlabs_voice_id, sample_count, datetime.datetime.now().isoformat(),
         elevenlabs_voice_id, sample_count, datetime.datetime.now().isoformat()),
    )
    conn.commit()
    c.close()
    conn.close()


def _get_recent_contribution_audio(get_conn, language_key, limit):
    """Fetch the most recent N audio samples (base64) for a language."""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT audio_base64 FROM contributions "
        "WHERE language_key=%s ORDER BY created_at DESC LIMIT %s",
        (language_key, limit),
    )
    rows = c.fetchall()
    c.close()
    conn.close()
    return [r["audio_base64"] for r in rows]


def _count_contributions(get_conn, language_key):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT COUNT(*) as n FROM contributions WHERE language_key=%s",
        (language_key,),
    )
    n = c.fetchone()["n"]
    c.close()
    conn.close()
    return n


# ── ElevenLabs integration ─────────────────────────────────────────────────────
def rebuild_community_voice(get_conn, language_key, voices_display_name=None):
    """
    (Re)build the ElevenLabs community voice for a language using the most
    recent contributed audio samples. Call this after a new contribution
    is saved (see wiring instructions below).

    Automatically throttled by REBUILD_EVERY_N_CONTRIBUTIONS so it doesn't
    rebuild on literally every single submission once volume grows.

    Returns the new voice_id, or None if a rebuild wasn't needed/possible.
    """
    total = _count_contributions(get_conn, language_key)

    # Need at least a couple of samples before cloning is worthwhile
    if total < 2:
        return None

    # Throttle: only rebuild every Nth contribution
    if total % REBUILD_EVERY_N_CONTRIBUTIONS != 0:
        return None

    key = _get_elevenlabs_key()
    audio_samples_b64 = _get_recent_contribution_audio(
        get_conn, language_key, MAX_SAMPLES_PER_VOICE
    )
    if not audio_samples_b64:
        return None

    # Decode each sample to a temp file for upload
    temp_files = []
    try:
        for i, b64 in enumerate(audio_samples_b64):
            audio_bytes = base64.b64decode(b64)
            tmp = tempfile.NamedTemporaryFile(suffix=f"_{i}.webm", delete=False)
            tmp.write(audio_bytes)
            tmp.close()
            temp_files.append(tmp.name)

        display_name = voices_display_name or f"CMT Community — {language_key}"

        files_payload = []
        opened_files = []
        for path in temp_files:
            f = open(path, "rb")
            opened_files.append(f)
            files_payload.append(("files", (os.path.basename(path), f, "audio/webm")))

        try:
            resp = requests.post(
                f"{ELEVENLABS_API}/voices/add",
                headers={"xi-api-key": key},
                data={
                    "name": display_name,
                    "description": f"Community-contributed voice for {language_key}, "
                                    f"built from {len(temp_files)} contributed samples.",
                },
                files=files_payload,
                timeout=120,
            )
        finally:
            for f in opened_files:
                f.close()

        if resp.status_code not in (200, 201):
            raise RuntimeError(f"ElevenLabs voice creation failed: {resp.status_code} {resp.text}")

        new_voice_id = resp.json()["voice_id"]

        # Clean up the OLD voice on ElevenLabs so voices don't pile up
        existing = get_community_voice(get_conn, language_key)
        if existing and existing.get("elevenlabs_voice_id"):
            try:
                requests.delete(
                    f"{ELEVENLABS_API}/voices/{existing['elevenlabs_voice_id']}",
                    headers={"xi-api-key": key},
                    timeout=15,
                )
            except Exception:
                pass  # Non-critical if cleanup fails

        _save_community_voice(get_conn, language_key, new_voice_id, len(temp_files))
        return new_voice_id

    finally:
        for path in temp_files:
            try:
                os.unlink(path)
            except OSError:
                pass


def speak_with_community_voice(text: str, language_key: str, get_conn) -> bytes:
    """
    Generate speech using a language's community voice.
    Returns MP3 audio bytes, or raises if no community voice exists yet.
    """
    voice_info = get_community_voice(get_conn, language_key)
    if not voice_info:
        raise ValueError(f"No community voice exists yet for '{language_key}'.")

    key = _get_elevenlabs_key()
    resp = requests.post(
        f"{ELEVENLABS_API}/text-to-speech/{voice_info['elevenlabs_voice_id']}",
        headers={"xi-api-key": key, "Content-Type": "application/json"},
        json={"text": text, "model_id": "eleven_multilingual_v2"},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Community voice TTS failed: {resp.status_code} {resp.text}")
    return resp.content


# ══════════════════════════════════════════════════════════════════════════════
# WIRING INSTRUCTIONS — add these small snippets to your existing files
# ══════════════════════════════════════════════════════════════════════════════
#
# 1) In db.py, add near the top:
#
#       import community_voice
#
#    And inside your existing init_db() function, add one line:
#
#       community_voice.init_community_voice_table(get_conn)
#
# 2) In main.py, find the existing submit_contribution() endpoint and add
#    ONE line at the end, right before the return statement:
#
#       import community_voice
#       try:
#           community_voice.rebuild_community_voice(db.get_conn, req.language)
#       except Exception as e:
#           print(f"Community voice rebuild skipped: {e}")  # non-fatal
#
# 3) Add these two new PUBLIC endpoints to main.py:
#
#       @app.get("/v1/contribute/community-voice/{language}")
#       async def get_community_voice_info(language: str):
#           import community_voice
#           info = community_voice.get_community_voice(db.get_conn, language)
#           if not info:
#               return {"available": False, "language": language}
#           return {
#               "available": True,
#               "language": language,
#               "sample_count": info["sample_count"],
#               "updated_at": info["updated_at"],
#           }
#
#       @app.post("/v1/contribute/community-voice/{language}/preview")
#       async def preview_community_voice(language: str, text: str = "Sawubona!"):
#           import community_voice, base64
#           try:
#               audio_bytes = community_voice.speak_with_community_voice(
#                   text, language, db.get_conn
#               )
#               return {"audio_base64": base64.b64encode(audio_bytes).decode()}
#           except ValueError as e:
#               raise HTTPException(status_code=404, detail=str(e))
#           except Exception as e:
#               raise HTTPException(status_code=500, detail=str(e))
#
# 4) Set your ElevenLabs key on Render (same as before, if not already set):
#       CMT_ELEVENLABS_KEY = your-elevenlabs-key
