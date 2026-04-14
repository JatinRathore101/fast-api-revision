"""
setup.py — Run this once before starting the server.
Connects to PostgreSQL and creates the user_table if it does not already exist.
"""

import sys
import psycopg2
from psycopg2 import OperationalError

# Import settings after ensuring the project root is on sys.path
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import settings

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS user_table (
    username  VARCHAR(100) PRIMARY KEY,
    name      VARCHAR(100) NOT NULL,
    email     VARCHAR(100) UNIQUE NOT NULL,
    password  VARCHAR(100) NOT NULL
);
"""


def main():
    print(f"Connecting to PostgreSQL at {settings.db_host}:{settings.db_port} ...")

    try:
        conn = psycopg2.connect(
            host=settings.db_host,
            port=settings.db_port,
            dbname=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
        )
    except OperationalError as exc:
        print(f"[ERROR] Could not connect to PostgreSQL: {exc}")
        sys.exit(1)

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(CREATE_TABLE_SQL)
        print("user_table created (or already exists). Setup complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
