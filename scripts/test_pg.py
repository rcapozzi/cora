# uv run python -m django check
import os

import psycopg2
from dotenv import load_dotenv

# Load variables from .env
load_dotenv()

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "dbname": os.getenv("POSTGRES_NAME"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
}

try:
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database();")
            database = cur.fetchone()[0]

            cur.execute("SELECT current_user;")
            user = cur.fetchone()[0]

            cur.execute("SELECT version();")
            version = cur.fetchone()[0]

    print("✅ Successfully connected to PostgreSQL")
    print(f"Database : {database}")
    print(f"User     : {user}")
    print(f"Version  : {version}")

except Exception as e:
    print("❌ Connection failed")
    print(e)
