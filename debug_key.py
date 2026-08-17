"""
debug_key.py — Diagnose why your API key isn't working.
"""

import requests

# ── PASTE YOUR API KEY HERE ────────────────────────────────────────────────────
API_KEY = "cmt_PASTE_YOUR_KEY_HERE"

BASE_URL = "https://cmt-voice-cloud.onrender.com"

print("=" * 60)
print("  API KEY DEBUG")
print("=" * 60)
print(f"Key length: {len(API_KEY)} characters")
print(f"Key starts with: {API_KEY[:10]}")
print(f"Key ends with: {API_KEY[-10:]}")
print(f"Has spaces: {' ' in API_KEY}")
print(f"Has newlines: {chr(10) in API_KEY}")
print(f"Has tabs: {chr(9) in API_KEY}")
print()

print("Sending request...")
r = requests.get(
    f"{BASE_URL}/v1/usage",
    headers={"X-API-Key": API_KEY},
    timeout=60,
)

print(f"Status code: {r.status_code}")
print(f"Response: {r.text}")
print()

if r.status_code == 200:
    print("✅ SUCCESS — your key works!")
elif r.status_code == 401:
    print("❌ Key rejected. Possible causes:")
    print("   1. Key was copied incorrectly (check length/spaces above)")
    print("   2. Key was revoked")
    print("   3. This key doesn't exist in the database")
    print()
    print("   Try creating a completely NEW account with a NEW email")
    print("   on the dashboard, then use that fresh key immediately.")
