"""
dashboard.py — CMT Voice Cloud Developer Dashboard
Developed by Mzwandile Zulu | Creative Minds Technologies AI

Run with: streamlit run dashboard.py
"""

import streamlit as st
import os
import requests

import db
import payments_yoco

st.set_page_config(page_title="CMT Voice Cloud", page_icon="🎙️", layout="wide")
db.init_db()

# ── Theme ─────────────────────────────────────────────────────────────────────
st.markdown("""<style>
    .stApp { background-color: #0D1B2A; color: #F0F4F8; }
    .stSidebar { background-color: #14283D !important; }
    h1,h2,h3,h4,p,span,label { color: #F0F4F8 !important; }
    .stButton>button[kind="primary"] { background-color: #00C9A7 !important; border: none; color: #0D1B2A !important; }
    .stButton>button { background-color: #14283D !important; color: #F0F4F8 !important; border: 1px solid #2A3F5A !important; }
    code { color: #00C9A7 !important; background: #14283D !important; }
    a { color: #00C9A7 !important; font-weight: bold; }
    table { color: #F0F4F8 !important; }
    thead tr th { background-color: #14283D !important; color: #00C9A7 !important; }
    tbody tr td { background-color: #0D1B2A !important; color: #F0F4F8 !important; }
    .stAlert { background-color: #14283D !important; }
    .pay-link-box {
        background: #00C9A7; color: #0D1B2A !important; padding: 16px;
        border-radius: 8px; text-align: center; font-weight: bold; font-size: 16px;
        margin: 12px 0;
    }
    .pay-link-box a { color: #0D1B2A !important; text-decoration: underline; }
</style>""", unsafe_allow_html=True)

DEFAULTS = {"logged_in": False, "email": None}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ══════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════
def show_auth():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("# 🎙️ CMT Voice Cloud")
        st.caption("South African Voice AI — one API key, 11 languages, no setup.")
        st.markdown("---")

        tab1, tab2 = st.tabs(["Log In", "Sign Up"])

        with tab1:
            email = st.text_input("Email", key="li_email")
            pw = st.text_input("Password", type="password", key="li_pw")
            if st.button("Log In", type="primary", use_container_width=True):
                if db.verify_login(email, pw):
                    st.session_state.logged_in = True
                    st.session_state.email = email
                    st.rerun()
                else:
                    st.error("Incorrect email or password.")

        with tab2:
            company = st.text_input("Company / Project name (optional)", key="su_company")
            new_email = st.text_input("Email", key="su_email")
            new_pw = st.text_input("Password (min 6 chars)", type="password", key="su_pw")
            if st.button("Create Developer Account", type="primary", use_container_width=True):
                if not new_email or "@" not in new_email:
                    st.error("Enter a valid email.")
                elif len(new_pw) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    api_key = db.create_developer(new_email, new_pw, company)
                    if api_key:
                        st.success(
                            f"Account created! You have R{db.FREE_CREDITS_CENTS/100:.2f} free credit.\n\n"
                            f"Your API key:\n```\n{api_key}\n```\n"
                            f"Save this now — log in to see it again anytime."
                        )
                    else:
                        st.error("Email already registered.")


# ══════════════════════════════════════════════════════════
# DASHBOARD HOME
# ══════════════════════════════════════════════════════════
def show_dashboard():
    email = st.session_state.email
    dev = db.get_developer(email)
    balance = db.get_balance(email)

    with st.sidebar:
        st.markdown(f"### 🎙️ CMT Voice Cloud")
        st.caption(f"{email}")
        st.metric("Balance", f"R{balance/100:.2f}")
        st.divider()

        page = st.radio("Navigate", [
            "📊 Overview", "🔑 API Keys", "💳 Billing", "🎤 My Voices",
            "📖 API Docs", "📈 Usage History",
        ])

        st.divider()
        if st.button("🚪 Log Out", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.email = None
            st.rerun()

    if page == "📊 Overview":
        show_overview(email, balance)
    elif page == "🔑 API Keys":
        show_api_keys(email)
    elif page == "💳 Billing":
        show_billing(email, balance)
    elif page == "🎤 My Voices":
        show_voices(email)
    elif page == "📖 API Docs":
        show_docs()
    elif page == "📈 Usage History":
        show_usage_history(email)


def show_overview(email, balance):
    st.markdown("# 📊 Overview")

    summary = db.get_usage_summary(email)
    col1, col2, col3 = st.columns(3)
    col1.metric("Balance", f"R{balance/100:.2f}")
    col2.metric("Total API Calls", summary["calls"])
    col3.metric("Total Spent", f"R{summary['total_spent']/100:.2f}")

    st.divider()
    st.markdown("### Quick Start")
    st.code('''
import requests

API_KEY = "your-api-key-here"

# Speak in isiZulu
response = requests.post(
    "https://voicecloud.cmt.africa/v1/speak",
    json={"text": "Sawubona Mzansi!", "language": "isizulu"},
    headers={"X-API-Key": API_KEY}
)

audio_base64 = response.json()["audio_base64"]
    ''', language="python")

    st.markdown("### Supported Languages")
    langs = ["isiZulu", "isiXhosa", "Afrikaans", "Sesotho", "Setswana",
             "Sepedi", "siSwati", "isiNdebele", "Tshivenda", "Xitsonga", "English (SA)"]
    st.write(" · ".join(langs))


def show_api_keys(email):
    st.markdown("# 🔑 API Keys")
    st.warning("Keep your API keys secret. Never share them or commit them to public code.")

    keys = db.get_api_keys(email)
    for k in keys:
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            status = "🟢 Active" if k["active"] else "🔴 Revoked"
            masked = k["api_key"][:12] + "..." + k["api_key"][-4:]
            st.code(masked)
            st.caption(f"{k['label']} — {status}")
        with col2:
            st.caption(f"Created: {k['created_at'][:10]}")
            if k["last_used_at"]:
                st.caption(f"Last used: {k['last_used_at'][:16]}")
        with col3:
            if k["active"] and st.button("Revoke", key=f"revoke_{k['api_key']}"):
                db.revoke_api_key(k["api_key"])
                st.rerun()

    st.divider()
    new_label = st.text_input("New key label (e.g. 'Production', 'Testing')")
    if st.button("➕ Generate New Key", type="primary"):
        new_key = db.create_api_key(email, new_label or "New key")
        st.success(f"New key created:\n```\n{new_key}\n```\nSave this now — it won't be shown again in full.")


def show_billing(email, balance):
    st.markdown("# 💳 Billing")
    st.metric("Current Balance", f"R{balance/100:.2f}")

    st.markdown("### Top up credits")
    col1, col2, col3, col4 = st.columns(4)
    amounts = [("R50", 5000), ("R100", 10000), ("R250", 25000), ("R500", 50000)]
    for col, (label, cents) in zip([col1,col2,col3,col4], amounts):
        with col:
            if st.button(label, use_container_width=True, key=f"topup_{cents}"):
                start_topup(email, cents)
                st.rerun()

    # Show the pending payment link persistently (survives reruns)
    if st.session_state.get("pending_checkout_url"):
        st.markdown(
            f'<div class="pay-link-box">💳 '
            f'<a href="{st.session_state.pending_checkout_url}" target="_blank">'
            f'Click here to pay R{st.session_state.get("pending_amount", 0)/100:.2f} on Yoco</a>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.info("After completing payment on Yoco, come back here and click verify.")

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("✅ I've paid — verify", type="primary", use_container_width=True):
                try:
                    status = payments_yoco.check_checkout_status(st.session_state.pending_checkout)
                    if status == "completed":
                        if db.complete_topup(st.session_state.pending_checkout):
                            st.success("Credits added!")
                            st.session_state.pending_checkout = None
                            st.session_state.pending_checkout_url = None
                            st.session_state.pending_amount = None
                            st.rerun()
                    else:
                        st.warning(f"Payment status: {status}. If you just paid, wait a moment and try again.")
                except Exception as e:
                    st.error(f"Verification error: {e}")
        with col_b:
            if st.button("❌ Cancel this payment", use_container_width=True):
                st.session_state.pending_checkout = None
                st.session_state.pending_checkout_url = None
                st.session_state.pending_amount = None
                st.rerun()

    st.divider()
    st.markdown("### Pricing")
    pricing_html = """
    <table style="width:100%; border-collapse:collapse; margin-top:8px;">
        <tr><th style="text-align:left; padding:10px; background:#14283D; color:#00C9A7;">Service</th>
            <th style="text-align:left; padding:10px; background:#14283D; color:#00C9A7;">Price</th></tr>
        <tr><td style="padding:10px; border-bottom:1px solid #2A3F5A;">Text-to-speech</td>
            <td style="padding:10px; border-bottom:1px solid #2A3F5A;">R0.50 per 1,000 characters</td></tr>
        <tr><td style="padding:10px; border-bottom:1px solid #2A3F5A;">Speech-to-text</td>
            <td style="padding:10px; border-bottom:1px solid #2A3F5A;">R2.00 per minute</td></tr>
        <tr><td style="padding:10px; border-bottom:1px solid #2A3F5A;">AI chat</td>
            <td style="padding:10px; border-bottom:1px solid #2A3F5A;">R1.00 per 1,000 tokens</td></tr>
        <tr><td style="padding:10px;">Voice cloning</td>
            <td style="padding:10px;">R50.00 once per voice</td></tr>
    </table>
    """
    st.markdown(pricing_html, unsafe_allow_html=True)


def start_topup(email, amount_cents):
    try:
        checkout = payments_yoco.create_checkout(
            email=email,
            success_url="https://cmt-voice-cloud-6dzu8d47bdtxbx9htnrttv.streamlit.app/?topup=success",
            cancel_url="https://cmt-voice-cloud-6dzu8d47bdtxbx9htnrttv.streamlit.app/?topup=cancelled",
        )
        db.create_topup(email, amount_cents, checkout["id"])
        st.session_state.pending_checkout = checkout["id"]
        st.session_state.pending_checkout_url = checkout["redirectUrl"]
        st.session_state.pending_amount = amount_cents
    except Exception as e:
        st.error(f"Payment error: {e}")


def show_voices(email):
    st.markdown("# 🎤 My Cloned Voices")
    voices_list = db.get_cloned_voices(email)

    if not voices_list:
        st.info("No cloned voices yet. Use the /v1/clone-voice API endpoint to create one.")
        st.code('''
import requests, base64

with open("my_voice.wav", "rb") as f:
    audio_b64 = base64.b64encode(f.read()).decode()

response = requests.post(
    "https://voicecloud.cmt.africa/v1/clone-voice",
    json={"voice_name": "My Voice", "language": "isixhosa", "audio_base64": audio_b64},
    headers={"X-API-Key": "your-api-key"}
)
print(response.json())
        ''', language="python")
    else:
        for v in voices_list:
            st.markdown(f"**🎙️ {v['voice_name']}** ({v['language_key']})")
            st.caption(f"Voice ID: `{v['voice_id']}` — Created {v['created_at'][:10]}")
            st.divider()


def show_docs():
    st.markdown("# 📖 API Documentation")
    st.markdown("Base URL: `https://voicecloud.cmt.africa`")
    st.markdown("All requests need header: `X-API-Key: your-api-key`")

    st.markdown("## POST /v1/speak")
    st.code('''
{
  "text": "Sawubona Mzansi!",
  "language": "isizulu",
  "gender": "Female",
  "rate": "0%",
  "pitch": "0%"
}
    ''', language="json")

    st.markdown("## POST /v1/listen")
    st.code('''
{
  "audio_base64": "<base64 wav audio>",
  "language": "isizulu"
}
    ''', language="json")

    st.markdown("## POST /v1/chat")
    st.code('''
{
  "message": "Ngitshele ngesayensi",
  "language": "isizulu",
  "personality": "tutor",
  "history": []
}
    ''', language="json")

    st.markdown("## POST /v1/translate")
    st.code('''
{
  "text": "Hello, how are you?",
  "from_language": "english",
  "to_language": "isizulu"
}
    ''', language="json")

    st.markdown("## POST /v1/clone-voice")
    st.code('''
{
  "voice_name": "My Voice",
  "language": "isixhosa",
  "audio_base64": "<base64 wav audio, min 30s>"
}
    ''', language="json")

    st.markdown("## GET /v1/usage")
    st.caption("Check your balance and usage history (no body needed).")

    st.markdown("---")
    st.markdown("Full interactive docs also available at `/docs` on the API server (Swagger UI).")


def show_usage_history(email):
    st.markdown("# 📈 Usage History")
    history = db.get_usage_history(email, limit=100)

    if not history:
        st.info("No API calls yet.")
        return

    for h in history:
        col1, col2, col3 = st.columns([2, 3, 1])
        with col1:
            st.caption(h["created_at"][:16])
        with col2:
            st.write(f"**{h['endpoint']}** — {h['meta']}")
        with col3:
            st.write(f"R{h['cost_cents']/100:.2f}")


# ══════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    show_auth()
else:
    show_dashboard()
