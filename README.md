# CMT Voice Cloud 🎙️🇿🇦

**South African Voice AI as a service.** One API key. 11 languages. No Azure account, no Claude account, no ElevenLabs account needed.

Developed by Mzwandile Zulu | Creative Minds Technologies AI | Sala Innovation Labs

## What this is

Two things run together:

1. **`main.py`** — the FastAPI backend. This is what developers call.
2. **`dashboard.py`** — the Streamlit developer dashboard. Sign up, get an API key, buy credits, see docs.

## Local setup

```bash
pip install -r requirements.txt

setx CMT_CLAUDE_KEY "your-claude-key"
setx CMT_ELEVENLABS_KEY "your-elevenlabs-key"
setx CMT_YOCO_SECRET_KEY "your-yoco-key"
```

Run the API:
```bash
uvicorn main:app --reload --port 8000
```

Run the dashboard (separate terminal):
```bash
streamlit run dashboard.py
```

Interactive API docs (Swagger): `http://localhost:8000/docs`

## How developers use it

```python
import requests

API_KEY = "cmt_..."

response = requests.post(
    "https://voicecloud.cmt.africa/v1/speak",
    json={"text": "Sawubona Mzansi!", "language": "isizulu"},
    headers={"X-API-Key": API_KEY}
)
audio_base64 = response.json()["audio_base64"]
```

## Pricing model

| Service | Price |
|---|---|
| Text-to-speech | R0.50 per 1,000 characters |
| Speech-to-text | R2.00 per minute |
| AI chat | R1.00 per 1,000 tokens |
| Voice cloning | R50.00 once per voice |

New developers get **R20 free credit** on signup — enough to test everything before paying.

## Deployment

**Backend (main.py):** Deploy to Render, Railway, or a VPS — needs to run continuously as a server (not Streamlit Cloud, which is for the dashboard only).

**Dashboard (dashboard.py):** Deploy to Streamlit Community Cloud, same as your other CMT apps.

Point the dashboard's API calls at your deployed backend URL once both are live.

## Revenue model

This is the first CMT product that charges for API usage rather than being free on PyPI. Every existing CMT library (CMT-IsiZulu, CMT-SALanguages, CMT-SA-Accent, CMT-SA-Assistant) remains free — this wraps them into a hosted, metered service for developers who don't want to manage their own API keys.

---

*Sikhona. We exist — and now, developers can build on us.* 🇿🇦
