"""
test_neon_connection.py — Test if your Neon connection string actually works.
"""

import psycopg2

# PASTE your current connection string from Neon's "Connect" button here
DATABASE_URL = "PASTE_YOUR_FULL_CONNECTION_STRING_HERE"

print("Testing connection to Neon...")
print(f"Connection string starts with: {DATABASE_URL[:30]}...")
print()

try:
    conn = psycopg2.connect(DATABASE_URL)
    print("✅ SUCCESS! Connected to Neon database.")

    cur = conn.cursor()
    cur.execute("SELECT version();")
    version = cur.fetchone()
    print(f"Postgres version: {version[0][:50]}...")

    cur.execute("SELECT COUNT(*) FROM developers;")
    count = cur.fetchone()
    print(f"Developers in database: {count[0]}")

    cur.close()
    conn.close()
except Exception as e:
    print(f"❌ FAILED: {e}")
    print()
    print("This means the connection string itself is wrong.")
    print("Go back to Neon > Connect and copy the EXACT string shown there.")
