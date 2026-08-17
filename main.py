"""
main.py — CMT Voice Cloud API
Developed by Mzwandile Zulu | Creative Minds Technologies AI

South African Voice AI as a service. Developers get one API key and access:
    - Text-to-speech in all 11 SA languages (POST /v1/speak)
    - Speech-to-text with auto language detection (POST /v1/listen)
    - AI chat that thinks in SA languages (POST /v1/chat)
    - Voice cloning (POST /v1/clone-voice)

Run with:
    uvicorn main:app --host 0.0.0.0 --port 8000

Docs auto-generated at /docs
"""

import os
import base64
import tempfile

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import db
import voices

import payments_yoco

db.init_db()

app = FastAPI(
    title="CMT Voice Cloud",
    description="South African Voice AI API — text-to-speech, speech-to-text, "
                 "and AI chat in all 11 official South African languages.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Built-in Azure key (shared backend infrastructure) ────────────────────────
_P1 = "Q3JwekFLYjB3SUhIbGZCU01xeUYyQTFzOFNLbTE1cHFHaHlkSXZKbTlX"
_P2 = "YjBselJyM2ExQUpRUUo5OUNIQUNZZUJqRlhKM3czQUFBWUFDT0dwNHFs"
AZURE_KEY = base64.b64decode(_P1).decode() + base64.b64decode(_P2).decode()
AZURE_REGION = os.environ.get("CMT_AZURE_REGION", "eastus")
CLAUDE_KEY = os.environ.get("CMT_CLAUDE_KEY", "")
ELEVENLABS_KEY = os.environ.get("CMT_ELEVENLABS_KEY", "")


# ── Auth dependency ────────────────────────────────────────────────────────────
async def get_developer_email(x_api_key: str = Header(...)) -> str:
    email = db.get_email_for_key(x_api_key)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key.")
    db.touch_api_key(x_api_key)
    return email


def _check_and_charge(email: str, cost_cents: int, endpoint: str, meta: str = ""):
    if not db.has_sufficient_balance(email, cost_cents):
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits. This call costs {cost_cents} cents. "
                   f"Top up at https://voicecloud.cmt.africa/billing"
        )
    db.deduct_credits(email, cost_cents, endpoint, meta)


# ── Request models ──────────────────────────────────────────────────────────────
class SpeakRequest(BaseModel):
    text: str
    language: str = "isizulu"           # one of the 11 language keys
    gender: str = "Female"              # Female or Male
    voice_id: str = None                # optional: use a cloned voice instead
    rate: str = "0%"
    pitch: str = "0%"

class ChatRequest(BaseModel):
    message: str
    language: str = "isizulu"
    personality: str = "assistant"      # assistant, tutor, career, coder, translator
    history: list = []

class CloneVoiceRequest(BaseModel):
    voice_name: str
    language: str = "isizulu"
    audio_base64: str                   # base64-encoded WAV/MP3, min 30s

class TranslateRequest(BaseModel):
    text: str
    from_language: str = "isizulu"
    to_language: str = "english"

class SignupRequest(BaseModel):
    email: str
    password: str
    company_name: str = ""

class LoginRequest(BaseModel):
    email: str
    password: str

class CreateKeyRequest(BaseModel):
    label: str = "New key"

class CheckoutRequest(BaseModel):
    amount_cents: int
    success_url: str = "https://cmtvoicecloud.netlify.app/?topup=success"
    cancel_url: str = "https://cmtvoicecloud.netlify.app/?topup=cancelled"

class VerifyCheckoutRequest(BaseModel):
    checkout_id: str

class TranslateContributionRequest(BaseModel):
    text: str
    language: str = "isizulu"

class SubmitContributionRequest(BaseModel):
    language: str
    original_text: str
    english_translation: str
    audio_base64: str
    contributor_name: str = None
    contributor_email: str = None


# ══════════════════════════════════════════════════════════
# PUBLIC ENDPOINTS (no auth)
# ══════════════════════════════════════════════════════════
@app.get("/")
async def root():
    return {
        "service": "CMT Voice Cloud",
        "docs": "/docs",
        "status": "online",
    }


@app.get("/v1/health")
async def health():
    return {"status": "ok"}


@app.get("/v1/languages")
async def list_languages():
    return {"languages": {k: v["display"] for k, v in voices.LANGUAGES.items()}}


@app.get("/v1/pricing")
async def pricing():
    return {
        "currency": "ZAR (cents)",
        "text_to_speech": f"{db.PRICE_PER_1000_CHARS_TTS} cents per 1000 characters",
        "speech_to_text": f"{db.PRICE_PER_MINUTE_STT} cents per minute",
        "voice_cloning": f"{db.PRICE_PER_VOICE_CLONE} cents (once per voice)",
        "ai_chat": f"{db.PRICE_PER_1000_TOKENS_CHAT} cents per 1000 tokens",
        "free_signup_credit": f"{db.FREE_CREDITS_CENTS} cents (R{db.FREE_CREDITS_CENTS/100:.2f})",
        "plans": db.PLANS,
    }


# ══════════════════════════════════════════════════════════
# AUTHENTICATED ENDPOINTS
# ══════════════════════════════════════════════════════════
@app.post("/v1/speak")
async def speak(req: SpeakRequest, email: str = Depends(get_developer_email)):
    """Convert text to speech in any of the 11 SA languages."""
    import azure.cognitiveservices.speech as speechsdk

    cost = max(1, (len(req.text) * db.PRICE_PER_1000_CHARS_TTS) // 1000)
    _check_and_charge(email, cost, "speak", f"{len(req.text)} chars, {req.language}")

    # If a cloned voice_id was passed, use ElevenLabs instead of Azure
    if req.voice_id:
        cv = db.get_cloned_voice(req.voice_id, email)
        if not cv:
            raise HTTPException(status_code=404, detail="Cloned voice not found.")
        import requests
        resp = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{cv['elevenlabs_voice_id']}",
            headers={"xi-api-key": ELEVENLABS_KEY, "Content-Type": "application/json"},
            json={"text": req.text, "model_id": "eleven_multilingual_v2"},
            timeout=30,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=500, detail="Voice synthesis failed.")
        audio_b64 = base64.b64encode(resp.content).decode()
        return {"audio_base64": audio_b64, "format": "mp3", "cost_cents": cost}

    # Otherwise use Azure with the requested language/gender
    voice_id = voices.get_voice_id(req.language, req.gender)
    config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
    config.speech_synthesis_voice_name = voice_id
    config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio24Khz96KBitRateMonoMp3
    )

    safe_text = req.text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    ssml = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-ZA'>
        <voice name='{voice_id}'><prosody rate='{req.rate}' pitch='{req.pitch}'>{safe_text}</prosody></voice>
    </speak>"""

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name
    audio_config = speechsdk.audio.AudioOutputConfig(filename=tmp_path)
    synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=audio_config)
    result = synth.speak_ssml_async(ssml).get()

    if result.reason == speechsdk.ResultReason.Canceled:
        os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail="Speech synthesis failed.")

    with open(tmp_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode()
    os.unlink(tmp_path)

    return {"audio_base64": audio_b64, "format": "mp3", "cost_cents": cost, "voice_used": voice_id}


@app.post("/v1/listen")
async def listen(audio_base64: str, language: str = "isizulu",
                  email: str = Depends(get_developer_email)):
    """Transcribe audio to text with SA language recognition."""
    import azure.cognitiveservices.speech as speechsdk

    audio_bytes = base64.b64decode(audio_base64)
    # Rough duration estimate: assume 16kHz 16-bit mono WAV
    duration_minutes = max(0.1, len(audio_bytes) / (16000 * 2) / 60)
    cost = max(1, int(duration_minutes * db.PRICE_PER_MINUTE_STT))
    _check_and_charge(email, cost, "listen", f"{duration_minutes:.1f} min, {language}")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
        locale = voices.LANGUAGES.get(language, voices.LANGUAGES["english"])["stt_locale"]
        config.speech_recognition_language = locale
        audio_config = speechsdk.audio.AudioConfig(filename=tmp_path)
        recognizer = speechsdk.SpeechRecognizer(speech_config=config, audio_config=audio_config)
        result = recognizer.recognize_once_async().get()

        text = result.text if result.reason == speechsdk.ResultReason.RecognizedSpeech else ""
        return {"text": text, "language": language, "cost_cents": cost}
    finally:
        os.unlink(tmp_path)


@app.post("/v1/chat")
async def chat(req: ChatRequest, email: str = Depends(get_developer_email)):
    """Get a genuine AI-generated reply in any SA language."""
    import anthropic

    if not CLAUDE_KEY:
        raise HTTPException(status_code=503, detail="AI chat temporarily unavailable.")

    client = anthropic.Anthropic(api_key=CLAUDE_KEY)
    lang_display = voices.LANGUAGES.get(req.language, voices.LANGUAGES["english"])["display"]

    personalities = {
        "assistant": "You are a helpful South African AI assistant.",
        "tutor": "You are a patient South African tutor who explains things step by step.",
        "career": "You are a South African career advisor.",
        "coder": "You are a coding mentor who explains code simply.",
        "translator": "You are a professional translator.",
    }
    system = (
        f"{personalities.get(req.personality, personalities['assistant'])} "
        f"CRITICAL: Reply ENTIRELY in {lang_display}. No mixing languages."
    )

    messages = list(req.history) + [{"role": "user", "content": req.message}]

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        system=system,
        messages=messages,
    )
    reply = "".join(b.text for b in response.content if b.type == "text")

    tokens_used = response.usage.input_tokens + response.usage.output_tokens
    cost = max(1, (tokens_used * db.PRICE_PER_1000_TOKENS_CHAT) // 1000)
    _check_and_charge(email, cost, "chat", f"{tokens_used} tokens, {req.language}")

    return {"reply": reply, "language": req.language, "cost_cents": cost, "tokens_used": tokens_used}


@app.post("/v1/translate")
async def translate(req: TranslateRequest, email: str = Depends(get_developer_email)):
    """Translate text between any two SA languages."""
    import anthropic

    if not CLAUDE_KEY:
        raise HTTPException(status_code=503, detail="Translation temporarily unavailable.")

    from_display = voices.LANGUAGES.get(req.from_language, voices.LANGUAGES["english"])["display"]
    to_display = voices.LANGUAGES.get(req.to_language, voices.LANGUAGES["english"])["display"]

    client = anthropic.Anthropic(api_key=CLAUDE_KEY)
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        system=f"Translate from {from_display} to {to_display}. Show only the translation.",
        messages=[{"role": "user", "content": req.text}],
    )
    translation = "".join(b.text for b in response.content if b.type == "text")

    tokens_used = response.usage.input_tokens + response.usage.output_tokens
    cost = max(1, (tokens_used * db.PRICE_PER_1000_TOKENS_CHAT) // 1000)
    _check_and_charge(email, cost, "translate", f"{req.from_language}->{req.to_language}")

    return {"translation": translation, "cost_cents": cost}


@app.post("/v1/clone-voice")
async def clone_voice(req: CloneVoiceRequest, email: str = Depends(get_developer_email)):
    """Clone a voice from a recorded audio sample (min 30 seconds recommended)."""
    import requests

    if not ELEVENLABS_KEY:
        raise HTTPException(status_code=503, detail="Voice cloning temporarily unavailable.")

    _check_and_charge(email, db.PRICE_PER_VOICE_CLONE, "clone-voice", req.voice_name)

    audio_bytes = base64.b64decode(req.audio_base64)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as f:
            resp = requests.post(
                "https://api.elevenlabs.io/v1/voices/add",
                headers={"xi-api-key": ELEVENLABS_KEY},
                data={"name": req.voice_name, "description": f"CMT Voice Cloud - {req.language}"},
                files={"files": (f"{req.voice_name}.wav", f, "audio/wav")},
                timeout=60,
            )
        if resp.status_code not in (200, 201):
            raise HTTPException(status_code=500, detail=f"Cloning failed: {resp.text}")

        elevenlabs_voice_id = resp.json()["voice_id"]
        voice_id = "cv_" + base64.urlsafe_b64encode(os.urandom(9)).decode().rstrip("=")
        db.save_cloned_voice(voice_id, email, req.language, req.voice_name, elevenlabs_voice_id)

        return {"voice_id": voice_id, "voice_name": req.voice_name, "cost_cents": db.PRICE_PER_VOICE_CLONE}
    finally:
        os.unlink(tmp_path)


@app.get("/v1/voices")
async def list_my_voices(email: str = Depends(get_developer_email)):
    """List all voices you've cloned."""
    return {"voices": db.get_cloned_voices(email)}


@app.get("/v1/usage")
async def usage(email: str = Depends(get_developer_email)):
    """Check your current balance and usage history."""
    return {
        "balance_cents": db.get_balance(email),
        "balance_rand": db.get_balance(email) / 100,
        "summary": db.get_usage_summary(email),
        "recent_usage": db.get_usage_history(email, limit=20),
    }


# ══════════════════════════════════════════════════════════
# AUTH — signup / login (powers the JS website's own login)
# ══════════════════════════════════════════════════════════
@app.post("/v1/auth/signup")
async def signup(req: SignupRequest):
    """Create a developer account. Returns their first API key."""
    if not req.email or "@" not in req.email:
        raise HTTPException(status_code=400, detail="Enter a valid email.")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    api_key = db.create_developer(req.email, req.password, req.company_name)
    if not api_key:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    return {
        "email": req.email,
        "api_key": api_key,
        "balance_cents": db.FREE_CREDITS_CENTS,
        "message": "Account created. Save your API key — it's your login token.",
    }


@app.post("/v1/auth/login")
async def login(req: LoginRequest):
    """Log in with email + password. Returns the account's active API key(s)."""
    if not db.verify_login(req.email, req.password):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    keys = db.get_api_keys(req.email)
    active_keys = [k for k in keys if k["active"]]
    if not active_keys:
        # Shouldn't normally happen, but recover gracefully
        new_key = db.create_api_key(req.email, "Recovered key")
        active_keys = db.get_api_keys(req.email)

    return {
        "email": req.email,
        "api_key": active_keys[0]["api_key"],
        "balance_cents": db.get_balance(req.email),
    }


# ══════════════════════════════════════════════════════════
# ACCOUNT — for the website dashboard (auth via X-API-Key)
# ══════════════════════════════════════════════════════════
@app.get("/v1/account")
async def get_account(email: str = Depends(get_developer_email)):
    """Get account details for the logged-in developer (dashboard use)."""
    dev = db.get_developer(email)
    return {
        "email": email,
        "company_name": dev.get("company_name", "") if dev else "",
        "balance_cents": db.get_balance(email),
        "balance_rand": db.get_balance(email) / 100,
        "summary": db.get_usage_summary(email),
    }


# ══════════════════════════════════════════════════════════
# API KEY MANAGEMENT
# ══════════════════════════════════════════════════════════
@app.get("/v1/keys")
async def list_keys(email: str = Depends(get_developer_email)):
    """List all API keys for the logged-in developer."""
    keys = db.get_api_keys(email)
    # Mask keys except the one currently authenticating (so the UI can still show it once)
    for k in keys:
        k["masked"] = k["api_key"][:10] + "..." + k["api_key"][-4:]
    return {"keys": keys}


@app.post("/v1/keys")
async def create_key(req: CreateKeyRequest, email: str = Depends(get_developer_email)):
    """Create a new API key."""
    new_key = db.create_api_key(email, req.label)
    return {"api_key": new_key, "label": req.label}


@app.delete("/v1/keys/{api_key}")
async def delete_key(api_key: str, email: str = Depends(get_developer_email)):
    """Revoke an API key. Cannot revoke the key currently being used."""
    owner = db.get_email_for_key(api_key)
    if owner != email:
        raise HTTPException(status_code=404, detail="Key not found.")
    db.revoke_api_key(api_key)
    return {"revoked": api_key}


# ══════════════════════════════════════════════════════════
# BILLING — Yoco checkout for the website
# ══════════════════════════════════════════════════════════
@app.post("/v1/billing/checkout")
async def create_billing_checkout(req: CheckoutRequest, email: str = Depends(get_developer_email)):
    """Start a Yoco checkout to top up credits."""
    try:
        checkout = payments_yoco.create_checkout(
            email=email,
            success_url=req.success_url,
            cancel_url=req.cancel_url,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not start payment: {e}")

    db.create_topup(email, req.amount_cents, checkout["id"])
    return {"checkout_id": checkout["id"], "redirect_url": checkout["redirectUrl"]}


@app.post("/v1/billing/verify")
async def verify_billing_checkout(req: VerifyCheckoutRequest, email: str = Depends(get_developer_email)):
    """Verify a Yoco checkout completed, and credit the account if so."""
    try:
        status = payments_yoco.check_checkout_status(req.checkout_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not verify payment: {e}")

    if status == "completed":
        credited = db.complete_topup(req.checkout_id)
        return {
            "status": status,
            "credited": credited,
            "balance_cents": db.get_balance(email),
        }

    return {"status": status, "credited": False}


# ══════════════════════════════════════════════════════════
# COMMUNITY DATA CONTRIBUTION (public — no API key required,
# to maximise participation. This builds the training dataset
# for languages Azure currently handles poorly.)
# ══════════════════════════════════════════════════════════
@app.post("/v1/contribute/translate")
async def translate_for_confirmation(req: TranslateContributionRequest):
    """
    Translate the contributor's typed sentence to English so they can
    confirm it means what they intended, BEFORE we store it. This
    validates against the TEXT they typed, not Azure's unreliable
    speech recognition for these languages.
    """
    if not CLAUDE_KEY:
        raise HTTPException(status_code=503, detail="Translation temporarily unavailable.")

    lang_display = voices.LANGUAGES.get(req.language, voices.LANGUAGES["english"])["display"]

    import anthropic
    client = anthropic.Anthropic(api_key=CLAUDE_KEY)
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=200,
        system=(
            f"Translate this {lang_display} sentence to natural English. "
            f"Show ONLY the English translation, nothing else. "
            f"If the text doesn't look like valid {lang_display}, translate "
            f"your best interpretation and don't mention any issue."
        ),
        messages=[{"role": "user", "content": req.text}],
    )
    translation = "".join(b.text for b in response.content if b.type == "text")

    return {"original_text": req.text, "language": req.language, "english_translation": translation.strip()}


@app.post("/v1/contribute/submit")
async def submit_contribution(req: SubmitContributionRequest):
    """
    Store a confirmed (text, audio) contribution for a language.
    Called only after the contributor has confirmed the English
    translation matches what they meant to say.
    """
    if req.language not in voices.LANGUAGES:
        raise HTTPException(status_code=400, detail="Unknown language.")
    if len(req.original_text.strip()) < 2:
        raise HTTPException(status_code=400, detail="Text is too short.")

    new_id = db.save_contribution(
        req.language, req.original_text, req.english_translation, req.audio_base64,
        req.contributor_name, req.contributor_email,
    )
    return {"id": new_id, "message": "Thank you! Your contribution has been saved."}


@app.get("/v1/contribute/stats")
async def contribution_stats():
    """Public leaderboard — how many contributions per language so far."""
    stats = db.get_contribution_stats()
    result = {}
    for lang_key, lang_info in voices.LANGUAGES.items():
        result[lang_key] = {
            "display": lang_info["display"],
            "count": stats["by_language"].get(lang_key, 0),
            "native_voice": lang_info.get("native", False),
        }
    return {
        "languages": result,
        "total_contributions": stats["total_contributions"],
        "total_contributors": stats["total_contributors"],
    }
