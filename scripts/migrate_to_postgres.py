#!/usr/bin/env python3
"""
Migrate StockPilot data from SQLite to PostgreSQL (Supabase).

Usage:
    DATABASE_URL=postgresql://user:pass@host:5432/dbname python scripts/migrate_to_postgres.py

This script:
  1. Reads all data from the local SQLite database
  2. Creates tables in PostgreSQL via SQLAlchemy (db.create_all)
  3. Copies all rows, handling type differences (SQLite -> PostgreSQL)
"""

import os
import sys
import sqlite3
from datetime import datetime

# Add project root to path so we can import app modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

SQLITE_PATH = os.path.join(PROJECT_ROOT, "stockpilot.db")

# Migration order respects foreign key dependencies
TABLE_ORDER = [
    "users",
    "positions",
    "alerts",
    "signal_cache",
    "trade_history",
    "watchlist",
    "investment_profiles",
    "broker_connections",
]


def get_pg_url():
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        print("ERROR: DATABASE_URL environment variable is required.")
        print("Usage: DATABASE_URL=postgresql://user:pass@host:5432/dbname python scripts/migrate_to_postgres.py")
        sys.exit(1)
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if not url.startswith("postgresql"):
        print(f"ERROR: DATABASE_URL must be a PostgreSQL URL. Got: {url[:30]}...")
        sys.exit(1)
    return url


def read_sqlite(db_path):
    """Read all table data from SQLite. Returns {table_name: (columns, rows)}."""
    if not os.path.exists(db_path):
        print(f"ERROR: SQLite database not found at {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    existing_tables = {row[0] for row in cursor.fetchall()}

    data = {}
    for table in TABLE_ORDER:
        if table not in existing_tables:
            print(f"  SKIP: Table '{table}' not found in SQLite (may not exist yet)")
            continue

        # Whitelist validation — table names must be alphanumeric/underscore only
        import re
        if not re.match(r'^[a-z_]+$', table):
            print(f"  SKIP: Invalid table name '{table}'")
            continue

        cursor.execute(f"PRAGMA table_info({table})")  # safe: table name validated above
        columns = [col[1] for col in cursor.fetchall()]

        cursor.execute(f"SELECT * FROM {table}")  # safe: table name validated above
        rows = cursor.fetchall()

        data[table] = (columns, [dict(row) for row in rows])
        print(f"  READ: {table} -> {len(rows)} rows")

    conn.close()
    return data


def convert_value(value, col_name):
    """Handle SQLite -> PostgreSQL type differences."""
    if value is None:
        return value

    # SQLite stores booleans as 0/1
    if col_name in ("is_read", "is_paper", "is_active", "onboarding_completed"):
        return bool(value)

    # SQLite datetime strings -> Python datetime
    if col_name.endswith("_at") or col_name in ("created_at", "updated_at", "added_at", "traded_at", "last_synced_at"):
        if isinstance(value, str):
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
        return value

    return value


def migrate_data(pg_url, data):
    """Insert SQLite data into PostgreSQL using SQLAlchemy."""
    # Override DATABASE_URL so Config picks up PostgreSQL
    os.environ["DATABASE_URL"] = pg_url

    # Now import the app (this picks up the PG config)
    from app import create_app
    from extensions import db
    from sqlalchemy import text, inspect

    app = create_app()

    with app.app_context():
        inspector = inspect(db.engine)
        pg_tables = set(inspector.get_table_names())
        print(f"\nPostgreSQL tables created: {', '.join(sorted(pg_tables))}")

        for table in TABLE_ORDER:
            if table not in data:
                continue

            columns, rows = data[table]
            if not rows:
                print(f"  SKIP: {table} (0 rows)")
                continue

            if table not in pg_tables:
                print(f"  SKIP: {table} (not in PostgreSQL schema)")
                continue

            # Get PG column names to only insert matching columns
            pg_columns = {col["name"] for col in inspector.get_columns(table)}
            valid_columns = [c for c in columns if c in pg_columns]

            print(f"  MIGRATING: {table} ({len(rows)} rows) ...", end=" ", flush=True)

            # Build parameterized INSERT
            col_list = ", ".join(valid_columns)
            param_list = ", ".join(f":{c}" for c in valid_columns)

            # Use ON CONFLICT DO NOTHING to skip duplicates
            # Detect primary key for conflict target
            pk_cols = inspector.get_pk_constraint(table).get("constrained_columns", [])
            if pk_cols:
                conflict_clause = f" ON CONFLICT ({', '.join(pk_cols)}) DO NOTHING"
            else:
                conflict_clause = ""

            insert_sql = text(
                f"INSERT INTO {table} ({col_list}) VALUES ({param_list}){conflict_clause}"
            )

            inserted = 0
            skipped = 0
            with db.engine.begin() as conn:
                for row in rows:
                    params = {}
                    for c in valid_columns:
                        params[c] = convert_value(row.get(c), c)
                    try:
                        result = conn.execute(insert_sql, params)
                        if result.rowcount > 0:
                            inserted += 1
                        else:
                            skipped += 1
                    except Exception as e:
                        skipped += 1
                        print(f"\n    WARN: row {row.get('id', '?')} failed: {e}")

            print(f"OK ({inserted} inserted, {skipped} skipped)")

            # Reset auto-increment sequence for tables with integer PK
            if pk_cols == ["id"]:
                try:
                    with db.engine.begin() as conn:
                        conn.execute(text(
                            f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                            f"COALESCE((SELECT MAX(id) FROM {table}), 1), true)"
                        ))
                    print(f"    Sequence reset for {table}.id")
                except Exception as e:
                    print(f"    WARN: Could not reset sequence for {table}: {e}")


def main():
    print("=" * 60)
    print("StockPilot: SQLite -> PostgreSQL Migration")
    print("=" * 60)

    pg_url = get_pg_url()
    print(f"\nTarget: {pg_url[:pg_url.index('@') + 1] if '@' in pg_url else pg_url[:30]}...")
    print(f"Source: {SQLITE_PATH}")

    # Step 1: Read SQLite
    print(f"\n--- Step 1: Reading SQLite ---")
    data = read_sqlite(SQLITE_PATH)

    if not data:
        print("No data found in SQLite. Nothing to migrate.")
        return

    # Step 2: Create tables & migrate data
    print(f"\n--- Step 2: Creating PostgreSQL tables & migrating ---")
    migrate_data(pg_url, data)

    print(f"\n{'=' * 60}")
    print("Migration complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
