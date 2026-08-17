"""
agent_example.py — A simple voice AI agent built on CMT Voice Cloud.

This shows developers exactly how to build ANYTHING on top of your API —
a chatbot, a robot, a WhatsApp bot, a call centre agent — using only
ONE API key. No Azure, no Claude, no ElevenLabs accounts needed.

Usage:
    python agent_example.py
"""

import requests
import base64

# ── Your CMT Voice Cloud API key ───────────────────────────────────────────────
API_KEY = "cmt_YOUR_KEY_HERE"
BASE_URL = "https://cmt-voice-cloud.onrender.com"

# ── The agent's memory (conversation history) ──────────────────────────────────
conversation_history = []


def think(message: str, language: str = "isizulu", personality: str = "assistant") -> str:
    """Ask the AI agent to think of a reply."""
    response = requests.post(
        f"{BASE_URL}/v1/chat",
        json={
            "message": message,
            "language": language,
            "personality": personality,
            "history": conversation_history,
        },
        headers={"X-API-Key": API_KEY},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    # Remember this exchange for context in future replies
    conversation_history.append({"role": "user", "content": message})
    conversation_history.append({"role": "assistant", "content": data["reply"]})

    return data["reply"]


def speak(text: str, language: str = "isizulu", gender: str = "Female", save_as: str = "reply.mp3"):
    """Turn the agent's reply into real speech and save it as an MP3."""
    response = requests.post(
        f"{BASE_URL}/v1/speak",
        json={"text": text, "language": language, "gender": gender},
        headers={"X-API-Key": API_KEY},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    audio_bytes = base64.b64decode(data["audio_base64"])
    with open(save_as, "wb") as f:
        f.write(audio_bytes)

    return save_as


def translate(text: str, from_language: str, to_language: str) -> str:
    """Translate text between any two SA languages."""
    response = requests.post(
        f"{BASE_URL}/v1/translate",
        json={"text": text, "from_language": from_language, "to_language": to_language},
        headers={"X-API-Key": API_KEY},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["translation"]


# ══════════════════════════════════════════════════════════
# EXAMPLE 1 — Simple text-in, text-out agent
# ══════════════════════════════════════════════════════════
def run_simple_agent():
    print("🤖 CMT Voice Cloud Agent (type 'quit' to exit)\n")

    while True:
        user_input = input("You: ")
        if user_input.lower() in ("quit", "exit"):
            break

        reply = think(user_input, language="isizulu", personality="tutor")
        print(f"Agent: {reply}\n")


# ══════════════════════════════════════════════════════════
# EXAMPLE 2 — Agent that also SPEAKS its replies out loud
# ══════════════════════════════════════════════════════════
def run_voice_agent():
    print("🎙️ CMT Voice Cloud Voice Agent\n")

    user_input = "Ngicela ungisize nge Python."
    print(f"You: {user_input}")

    reply = think(user_input, language="isizulu", personality="coder")
    print(f"Agent: {reply}")

    audio_file = speak(reply, language="isizulu", gender="Male")
    print(f"🔊 Saved reply audio to: {audio_file}")


# ══════════════════════════════════════════════════════════
# EXAMPLE 3 — Multi-language customer service agent
# ══════════════════════════════════════════════════════════
def run_customer_service_agent(customer_message: str, customer_language: str):
    """
    Example: a business uses this to auto-reply to customers
    in whatever SA language they wrote in.
    """
    system_context = (
        "You are a helpful customer service agent for a small business. "
        "Be polite, professional, and solve the customer's problem."
    )

    reply = think(
        f"{system_context}\n\nCustomer says: {customer_message}",
        language=customer_language,
        personality="assistant",
    )

    audio_file = speak(reply, language=customer_language, gender="Female",
                       save_as=f"reply_{customer_language}.mp3")

    return {"text_reply": reply, "audio_file": audio_file}


if __name__ == "__main__":
    print("=" * 60)
    print("  CMT Voice Cloud — Agent Examples")
    print("=" * 60)
    print()
    print("1. Simple text chat agent")
    print("2. Voice agent (speaks its reply)")
    print("3. Customer service agent example")
    print()

    choice = input("Which example? (1/2/3): ")

    if choice == "1":
        run_simple_agent()
    elif choice == "2":
        run_voice_agent()
    elif choice == "3":
        result = run_customer_service_agent(
            "Sawubona, ngicela ukwazi ukuthi ihora lini eniyavula ngalo?",
            "isizulu"
        )
        print(f"Reply: {result['text_reply']}")
        print(f"Audio: {result['audio_file']}")
