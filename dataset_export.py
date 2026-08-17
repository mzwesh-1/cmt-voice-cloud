"""
dataset_export.py — Preserves and exports your voice contribution dataset
for future AI model training (STT fine-tuning, TTS training, translation
model training, etc).

This is an ADD-ON module, same pattern as community_voice.py — it doesn't
modify your existing db.py/main.py directly. Wiring instructions are at
the bottom of this file.

Design decision: rather than cloning an individual ElevenLabs voice per
contributor (which hits ElevenLabs' voice-count limits fast and produces
poor quality from single short samples), this preserves the raw
(text, translation, audio) archive — the actual reusable training data
format used by real voice datasets like Mozilla Common Voice.

Nothing is ever deleted. Every contribution's audio stays in the database
permanently. This module adds:
    1. Traceability — which contributions fed into which community voice
       version (so you know the lineage even after a voice gets rebuilt)
    2. Export — pull the full dataset (or one language's) in a standard
       ML-friendly format (JSONL) whenever you're ready to actually train
       something with it
"""

import base64
import json
import datetime


# ── Traceability: mark which contributions built which voice version ─────────
def mark_contributions_used(get_conn, contribution_ids: list, elevenlabs_voice_id: str):
    """
    After a community voice rebuild, record which specific contributions
    were used to build that voice version. Called automatically by
    community_voice.py's rebuild_community_voice() — see wiring below.
    """
    if not contribution_ids:
        return
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "UPDATE contributions SET elevenlabs_voice_id=%s WHERE id = ANY(%s)",
        (elevenlabs_voice_id, contribution_ids),
    )
    conn.commit()
    c.close()
    conn.close()


# ── Dataset export ──────────────────────────────────────────────────────────
def get_full_dataset(get_conn, language_key: str = None, include_audio: bool = True):
    """
    Returns the full contribution dataset, optionally filtered by language.
    This is your reusable training data — every (text, translation, audio)
    triple ever contributed, in full, nothing discarded.
    """
    conn = get_conn()
    c = conn.cursor()
    if language_key:
        c.execute(
            "SELECT * FROM contributions WHERE language_key=%s ORDER BY created_at ASC",
            (language_key,),
        )
    else:
        c.execute("SELECT * FROM contributions ORDER BY language_key, created_at ASC")
    rows = c.fetchall()
    c.close()
    conn.close()

    dataset = []
    for r in rows:
        entry = {
            "id": r["id"],
            "language": r["language_key"],
            "text": r["original_text"],
            "english_translation": r["english_translation"],
            "contributor_name": r["contributor_name"],
            "contributed_at": r["created_at"],
            "used_in_voice_version": r.get("elevenlabs_voice_id"),
        }
        if include_audio:
            entry["audio_base64"] = r["audio_base64"]
        dataset.append(entry)
    return dataset


def export_as_jsonl(get_conn, language_key: str = None) -> str:
    """
    Export the dataset as JSONL (one JSON object per line) — the standard
    format used for ML training datasets. Each line is one training example.
    """
    dataset = get_full_dataset(get_conn, language_key, include_audio=True)
    lines = [json.dumps(entry, ensure_ascii=False) for entry in dataset]
    return "\n".join(lines)


def export_summary(get_conn) -> dict:
    """
    Quick overview of your full dataset — how much training data you have
    per language, useful for deciding when you have "enough" to actually
    train something.
    """
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT language_key, COUNT(*) as count, "
        "MIN(created_at) as first_contribution, MAX(created_at) as latest_contribution "
        "FROM contributions GROUP BY language_key ORDER BY count DESC"
    )
    rows = c.fetchall()
    c.close()
    conn.close()
    return {
        "languages": [dict(r) for r in rows],
        "generated_at": datetime.datetime.now().isoformat(),
    }


def save_audio_files_to_disk(get_conn, output_dir: str, language_key: str = None):
    """
    Optional helper: decode all base64 audio and write real .webm files
    to disk, plus a manifest.csv — the classic format most STT/TTS
    training pipelines expect (audio file + text transcript pairs).

    Run this locally when you're ready to actually prepare a training run.
    """
    import os
    import csv

    os.makedirs(output_dir, exist_ok=True)
    dataset = get_full_dataset(get_conn, language_key, include_audio=True)

    manifest_path = os.path.join(output_dir, "manifest.csv")
    with open(manifest_path, "w", newline="", encoding="utf-8") as manifest:
        writer = csv.writer(manifest)
        writer.writerow(["audio_file", "text", "english_translation", "language", "contributor"])

        for entry in dataset:
            filename = f"{entry['language']}_{entry['id']}.webm"
            filepath = os.path.join(output_dir, filename)

            audio_bytes = base64.b64decode(entry["audio_base64"])
            with open(filepath, "wb") as f:
                f.write(audio_bytes)

            writer.writerow([
                filename, entry["text"], entry["english_translation"],
                entry["language"], entry["contributor_name"] or "anonymous",
            ])

    return {
        "output_dir": output_dir,
        "manifest": manifest_path,
        "total_files": len(dataset),
    }


# ══════════════════════════════════════════════════════════════════════════════
# WIRING INSTRUCTIONS
# ══════════════════════════════════════════════════════════════════════════════
#
# 1) In community_voice.py's rebuild_community_voice() function, after this
#    existing line:
#
#       _save_community_voice(get_conn, language_key, new_voice_id, len(temp_files))
#
#    Add these two lines right after it, to record which contributions
#    were used to build this specific voice version:
#
#       import dataset_export
#       # (you already have the contribution IDs available if you fetch
#       #  them alongside the audio in _get_recent_contribution_audio —
#       #  see the small tweak below)
#
#    Then update _get_recent_contribution_audio() in community_voice.py to
#    also return the ids, so you can pass them to mark_contributions_used().
#    (This is a 2-line tweak — ask me and I'll hand you the exact diff if
#    you want this level of traceability; it's optional, everything else
#    below works without it.)
#
# 2) Add these THREE new endpoints to main.py. These should be protected
#    since they expose contributor names + raw audio — add a simple admin
#    key check (reuses the same pattern you'd use anywhere else):
#
#       import dataset_export
#
#       def _check_admin_key(x_admin_key: str = Header(...)):
#           import os
#           if x_admin_key != os.environ.get("CMT_ADMIN_EXPORT_KEY"):
#               raise HTTPException(status_code=401, detail="Invalid admin key")
#           return True
#
#       @app.get("/v1/admin/dataset/summary")
#       async def dataset_summary(_: bool = Depends(_check_admin_key)):
#           return dataset_export.export_summary(db.get_conn)
#
#       @app.get("/v1/admin/dataset/export")
#       async def dataset_export_endpoint(language: str = None, _: bool = Depends(_check_admin_key)):
#           jsonl = dataset_export.export_as_jsonl(db.get_conn, language)
#           return Response(content=jsonl, media_type="application/x-ndjson")
#
#    (Response needs: from fastapi.responses import Response — add to your
#    existing imports at the top of main.py)
#
# 3) Set an admin key on Render (pick any long random string):
#       CMT_ADMIN_EXPORT_KEY = your-own-secret-string-here
#
# 4) To pull your dataset later, from anywhere:
#
#       curl -H "X-Admin-Key: your-secret" \
#            "https://cmt-voice-cloud.onrender.com/v1/admin/dataset/summary"
#
#       curl -H "X-Admin-Key: your-secret" \
#            "https://cmt-voice-cloud.onrender.com/v1/admin/dataset/export?language=tshivenda" \
#            -o tshivenda_dataset.jsonl
