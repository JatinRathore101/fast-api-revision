"""
setup.py — Run this once before starting the server.

Runs two sequential setup steps:

  1. PostgreSQL — creates user_table if it does not already exist.
  2. MongoDB    — creates companies_collection with schema validation and indexes,
                  then bulk-inserts records from app/data/companies.json.

Both steps are idempotent: safe to run multiple times without side effects.
"""

import json
import os
import sys

import psycopg2
from psycopg2 import OperationalError
from pymongo import ASCENDING, MongoClient
from pymongo.errors import BulkWriteError, CollectionInvalid, ConnectionFailure

# Ensure the project root is on sys.path so app.config is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import settings

# ─── Constants ────────────────────────────────────────────────────────────────────

# Absolute path to the companies data file, resolved relative to this script
DATA_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "app", "data", "companies.json"
)

# ─── PostgreSQL ───────────────────────────────────────────────────────────────────

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS user_table (
    username  VARCHAR(100) PRIMARY KEY,
    name      VARCHAR(100) NOT NULL,
    email     VARCHAR(100) UNIQUE NOT NULL,
    password  VARCHAR(100) NOT NULL
);
"""

# ─── MongoDB ──────────────────────────────────────────────────────────────────────

# JSON Schema validator applied to every document written to companies_collection.
# Only `domain` is required — all other fields are optional strings.
COMPANIES_SCHEMA_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["domain"],
        "properties": {
            "domain":          {"bsonType": "string", "description": "Unique company domain (required)"},
            "companyName":     {"bsonType": "string", "description": "Company display name"},
            "companyCategory": {"bsonType": "string", "description": "Business category"},
            "city":            {"bsonType": "string", "description": "City"},
            "state":           {"bsonType": "string", "description": "State or region"},
            "country":         {"bsonType": "string", "description": "Country code"},
            "zipcode":         {"bsonType": "string", "description": "Postal code"},
        },
    }
}


# ─── Step 1: PostgreSQL setup ─────────────────────────────────────────────────────

def setup_postgres() -> None:
    """
    Connect to PostgreSQL and create user_table if it does not already exist.

    Uses CREATE TABLE IF NOT EXISTS so the statement is safe to re-run.
    Exits the process with code 1 if the connection cannot be established.
    """
    print(f"\n[PostgreSQL] Connecting to {settings.db_host}:{settings.db_port} ...")

    try:
        conn = psycopg2.connect(
            host=settings.db_host,
            port=settings.db_port,
            dbname=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
        )
    except OperationalError as exc:
        print(f"[PostgreSQL] [ERROR] Could not connect: {exc}")
        sys.exit(1)

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(CREATE_TABLE_SQL)
        print("[PostgreSQL] user_table created (or already exists). Setup complete.")
    finally:
        conn.close()


# ─── Step 2: MongoDB setup ────────────────────────────────────────────────────────

def setup_mongodb() -> None:
    """
    Connect to MongoDB and initialize companies_collection.

    Steps (all idempotent):
      1. Verify connectivity via admin ping.
      2. Create companies_collection with JSON Schema validation.
         CollectionInvalid is caught when the collection already exists.
      3. Create a unique index on `domain` and plain indexes on
         `companyCategory` and `country`. create_index() is a no-op when the
         same index already exists.
      4. Load app/data/companies.json and bulk-insert with ordered=False so
         duplicate-domain errors are skipped rather than aborting the batch.

    Exits the process with code 1 if the connection or data file cannot be read.
    """
    print(f"\n[MongoDB] Connecting to {settings.mongo_host}:{settings.mongo_port} ...")

    try:
        client = MongoClient(
            host=settings.mongo_host,
            port=settings.mongo_port,
            serverSelectionTimeoutMS=5000,  # Fail fast if server unreachable
        )
        # admin.command("ping") forces an actual network round-trip, making
        # connection errors surface here rather than on first collection access
        client.admin.command("ping")
    except ConnectionFailure as exc:
        print(f"[MongoDB] [ERROR] Could not connect: {exc}")
        sys.exit(1)

    db = client[settings.mongo_db_name]

    # ── Create collection with schema validation ──────────────────────────────
    # create_collection raises CollectionInvalid when the collection already
    # exists, which we treat as a successful idempotent no-op.
    print(f"[MongoDB] Setting up 'companies_collection' in '{settings.mongo_db_name}' ...")
    try:
        db.create_collection(
            "companies_collection",
            validator=COMPANIES_SCHEMA_VALIDATOR,
            validationAction="error",   # Reject documents that fail the schema
        )
        print("[MongoDB] Collection 'companies_collection' created.")
    except CollectionInvalid:
        print("[MongoDB] Collection 'companies_collection' already exists — skipping creation.")

    collection = db["companies_collection"]

    # ── Create indexes ────────────────────────────────────────────────────────
    # create_index() is idempotent: calling it again with the same key spec
    # and name returns the existing index name without creating a duplicate.
    collection.create_index(
        [("domain", ASCENDING)],
        unique=True,
        name="idx_domain_unique",
    )
    print("[MongoDB] Index on 'domain' (unique) ensured.")

    collection.create_index(
        [("companyCategory", ASCENDING)],
        name="idx_company_category",
    )
    print("[MongoDB] Index on 'companyCategory' ensured.")

    collection.create_index(
        [("country", ASCENDING)],
        name="idx_country",
    )
    print("[MongoDB] Index on 'country' ensured.")

    # ── Load data file ────────────────────────────────────────────────────────
    print(f"[MongoDB] Reading data from {DATA_FILE} ...")
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            companies = json.load(f)
    except FileNotFoundError:
        print(f"[MongoDB] [ERROR] Data file not found: {DATA_FILE}")
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"[MongoDB] [ERROR] Failed to parse JSON: {exc}")
        sys.exit(1)

    print(f"[MongoDB] Loaded {len(companies)} records. Performing bulk insert ...")

    # ── Bulk insert ───────────────────────────────────────────────────────────
    # ordered=False: MongoDB continues processing remaining documents even when
    # a duplicate-key error (code 11000) is encountered for `domain`.
    # BulkWriteError is raised at the end summarising all skipped documents.
    try:
        result = collection.insert_many(companies, ordered=False)
        print(f"[MongoDB] Inserted {len(result.inserted_ids)} new records.")
    except BulkWriteError as exc:
        inserted = exc.details.get("nInserted", 0)
        write_errors = exc.details.get("writeErrors", [])
        dup_count = sum(1 for e in write_errors if e.get("code") == 11000)
        other_errors = [e for e in write_errors if e.get("code") != 11000]

        print(f"[MongoDB] Inserted {inserted} new records.")
        if dup_count:
            print(
                f"[MongoDB] Skipped {dup_count} duplicate domain(s) "
                "— already in collection."
            )
        if other_errors:
            print(f"[MongoDB] [WARNING] {len(other_errors)} unexpected write error(s):")
            for err in other_errors:
                print(f"          code={err.get('code')} | {err.get('errmsg')}")

    print("[MongoDB] Setup complete.")
    client.close()


# ─── Entry point ──────────────────────────────────────────────────────────────────

def main() -> None:
    setup_postgres()
    setup_mongodb()


if __name__ == "__main__":
    main()
