"""
init_database.py — Run this ONCE to create all tables in your Neon Postgres database.

Usage:
    python init_database.py
"""

import os

# Paste your connection string here for this one-time setup
os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_sDCW2EZ3tXrJ@ep-proud-art-ax8jiwtf.c-4.us-east-2.aws.neon.tech/neondb?sslmode=require"

import db

print("Connecting to Neon Postgres...")
db.init_db()
print("✅ All tables created successfully!")
print()
print("Your database is ready. Now:")
print("1. Sign up on your dashboard to create a test account")
print("2. Copy the API key shown")
print("3. Run test_api.py or debug_key.py with that key")
print("4. It should now work since both services share this database!")
