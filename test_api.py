"""
test_api.py — Test your live CMT Voice Cloud API end-to-end.

Usage:
    python test_api.py

Just paste your API key below and run it. It will test each endpoint
and tell you clearly what worked and what didn't.
"""

import requests
import base64
import json

# ── PASTE YOUR API KEY HERE ────────────────────────────────────────────────────
API_KEY = "cmt_PASTE_YOUR_KEY_HERE"

BASE_URL = "https://cmt-voice-cloud.onrender.com"

print("=" * 60)
print("  CMT Voice Cloud — API Test")
print("=" * 60)
print(f"\nTesting: {BASE_URL}")
print("(Free tier sleeps after inactivity — first call may take ~50s)\n")


def test(name, func):
    print(f"▶ {name}...")
    try:
        result = func()
        print(f"  ✅ PASSED")
        return result
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        return None


# ── Test 1: Health check ──────────────────────────────────────────────────────
def check_health():
    r = requests.get(f"{BASE_URL}/v1/health", timeout=60)
    assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
    return r.json()

test("Health check", check_health)


# ── Test 2: List languages ────────────────────────────────────────────────────
def check_languages():
    r = requests.get(f"{BASE_URL}/v1/languages", timeout=30)
    assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
    data = r.json()
    assert len(data["languages"]) == 11, f"Expected 11 languages, got {len(data['languages'])}"
    return data

result = test("List 11 languages", check_languages)
if result:
    print(f"  Languages: {', '.join(result['languages'].values())}")


# ── Test 3: Check your balance (requires valid API key) ───────────────────────
def check_balance():
    r = requests.get(f"{BASE_URL}/v1/usage",
                     headers={"X-API-Key": API_KEY}, timeout=30)
    if r.status_code == 401:
        raise Exception("Invalid API key — check you pasted it correctly")
    assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
    return r.json()

result = test("Check balance (validates your API key)", check_balance)
if result:
    print(f"  Balance: R{result['balance_rand']:.2f}")


# ── Test 4: THE REAL TEST — generate actual speech ────────────────────────────
def test_speak():
    r = requests.post(
        f"{BASE_URL}/v1/speak",
        json={"text": "Sawubona Mzansi! Uhlelo lwami luyasebenza kahle.", "language": "isizulu"},
        headers={"X-API-Key": API_KEY},
        timeout=60,
    )
    if r.status_code == 402:
        raise Exception("Insufficient credits — top up on your dashboard")
    if r.status_code == 401:
        raise Exception("Invalid API key")
    assert r.status_code == 200, f"Status {r.status_code}: {r.text}"

    data = r.json()
    audio_bytes = base64.b64decode(data["audio_base64"])

    # Save the actual audio file so you can listen to it
    with open("test_output.mp3", "wb") as f:
        f.write(audio_bytes)

    return data

result = test("Generate isiZulu speech (the real test)", test_speak)
if result:
    print(f"  Cost: {result['cost_cents']} cents")
    print(f"  Voice used: {result.get('voice_used', 'N/A')}")
    print(f"  Audio saved to: test_output.mp3 — OPEN THIS FILE AND LISTEN TO IT")


# ── Test 5: AI Chat ────────────────────────────────────────────────────────────
def test_chat():
    r = requests.post(
        f"{BASE_URL}/v1/chat",
        json={"message": "Sawubona, unjani?", "language": "isizulu"},
        headers={"X-API-Key": API_KEY},
        timeout=30,
    )
    if r.status_code == 402:
        raise Exception("Insufficient credits — top up on your dashboard")
    if r.status_code == 503:
        raise Exception("Claude API key not configured on the server")
    assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
    return r.json()

result = test("AI chat reply in isiZulu", test_chat)
if result:
    print(f"  Reply: {result['reply']}")
    print(f"  Cost: {result['cost_cents']} cents")


# ── Test 6: Wrong API key should be rejected ──────────────────────────────────
def test_invalid_key():
    r = requests.get(f"{BASE_URL}/v1/usage",
                     headers={"X-API-Key": "cmt_definitely_fake_key_123"}, timeout=30)
    assert r.status_code == 401, f"Expected 401, got {r.status_code} — SECURITY ISSUE!"
    return "correctly rejected"

test("Invalid API key is correctly blocked", test_invalid_key)


print("\n" + "=" * 60)
print("  DONE — check results above")
print("  If 'Generate isiZulu speech' passed, open test_output.mp3")
print("  and listen to confirm it actually sounds right!")
print("=" * 60)
