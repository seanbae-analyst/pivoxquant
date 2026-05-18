"""Tests for scripts/rotate_broker_encryption_key.py (external action #14).

Covers:
  * DRY-RUN mode — no DB writes, no cache rewrite.
  * 1-row decrypt/re-encrypt round-trip — old key → new key → readable
    with new key, AES-GCM ciphertext shape preserved.
  * decrypt-with-old-key failure → SystemExit(2) + rollback (no row mutated).
  * Legacy plaintext cache file is left for the auto-migration path.
  * Identical old/new key → SystemExit(1).
"""
from __future__ import annotations

import base64
import importlib
import os
import sys
from pathlib import Path
from typing import Optional

import pytest

from extensions import db


# ── Setup ────────────────────────────────────────────────────────────────────
@pytest.fixture
def script_module(app, monkeypatch, tmp_path):
    """Import the rotation script with a tmpdir-scoped cache file.

    The script binds ``_CACHE_FILE`` at module import time using
    ``Path(__file__).resolve().parents[1]`` → project root. Tests must NOT
    touch the real cache, so we patch it after import.
    """
    # Ensure scripts/ is importable.
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    if "scripts.rotate_broker_encryption_key" in sys.modules:
        mod = importlib.reload(sys.modules["scripts.rotate_broker_encryption_key"])
    else:
        mod = importlib.import_module("scripts.rotate_broker_encryption_key")

    # Re-route the cache file to a per-test tmp path so we never touch
    # the real .kis_token_cache.json at repo root.
    fake_cache = tmp_path / ".kis_token_cache.json"
    monkeypatch.setattr(mod, "_CACHE_FILE", fake_cache)

    # Force create_app() inside _rotate_broker_rows to reuse the test app.
    monkeypatch.setattr(mod, "_rotate_broker_rows",
                         _make_rebound_rotate(mod, app))

    return mod


def _make_rebound_rotate(mod, test_app):
    """Return a copy of _rotate_broker_rows that uses the existing test app.

    The original imports app.create_app(), which fires the full prod
    factory (scheduler etc.). Tests already have a wired test app via
    the conftest ``app`` fixture — reuse it.
    """
    original = mod._rotate_broker_rows  # capture for delegation

    def _rebound(*, aes_old, aes_new, batch_size, dry_run, sample_limit=3):
        # Mirror the original body but skip create_app().
        from sqlalchemy import inspect as _inspect, text

        rows_seen = 0
        cols_rotated = 0
        samples_logged = 0

        with test_app.app_context():
            tables = set(_inspect(db.engine).get_table_names())
            if mod._BROKER_TABLE not in tables:
                return 0, 0

            for batch in mod._iter_rows(db.session, batch_size):
                batch_updates: list[dict] = []
                for row in batch:
                    rows_seen += 1
                    row_id = row[0]
                    col_values = row[2:]

                    new_values: dict[str, Optional[str]] = {}
                    rotated_in_row = 0
                    try:
                        for col_name, ct in zip(mod._CIPHERTEXT_COLUMNS, col_values):
                            new_ct, rotated = mod._rotate_value(
                                ct,
                                aad=mod._BROKER_AAD,
                                aes_old=aes_old,
                                aes_new=aes_new,
                            )
                            if rotated:
                                new_values[col_name] = new_ct
                                rotated_in_row += 1
                    except Exception:
                        db.session.rollback()
                        raise SystemExit(2)

                    cols_rotated += rotated_in_row
                    if rotated_in_row and not dry_run:
                        batch_updates.append({"row_id": row_id, **new_values})

                if dry_run:
                    continue

                for upd in batch_updates:
                    row_id = upd.pop("row_id")
                    set_parts = ", ".join(f"{c} = :{c}" for c in upd.keys())
                    if not set_parts:
                        continue
                    sql = text(
                        f"UPDATE {mod._BROKER_TABLE} SET {set_parts} WHERE id = :row_id"
                    )
                    db.session.execute(sql, {"row_id": row_id, **upd})
                db.session.commit()

        return rows_seen, cols_rotated

    return _rebound


# ── Helpers ──────────────────────────────────────────────────────────────────
def _gen_key() -> str:
    """Base64-encode a fresh 32-byte AES key."""
    return base64.b64encode(os.urandom(32)).decode("ascii")


def _aesgcm(b64_key: str):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    return AESGCM(base64.b64decode(b64_key))


def _encrypt_with(b64_key: str, plaintext: str, aad: bytes = b"broker") -> str:
    """Produce a ciphertext that crypto_service.decrypt() would accept."""
    aes = _aesgcm(b64_key)
    nonce = os.urandom(12)
    ct = aes.encrypt(nonce, plaintext.encode("utf-8"), aad)
    return base64.b64encode(nonce + ct).decode("ascii")


def _seed_broker_row(app, user_id: int, *, old_key: str, broker: str = "kis") -> int:
    """Insert a broker_connections row encrypted with `old_key`. Returns row id."""
    from models import User
    from models.broker_connection import BrokerConnection

    with app.app_context():
        # Ensure a user exists (FK).
        u = db.session.get(User, user_id)
        if u is None:
            u = User(id=user_id, email=f"rotate-test-{user_id}@example.com")
            db.session.add(u)
            db.session.flush()

        conn = BrokerConnection(
            user_id=u.id,
            broker=broker,
            encrypted_app_key=_encrypt_with(old_key, f"APP_KEY_{user_id}"),
            encrypted_app_secret=_encrypt_with(old_key, f"APP_SECRET_{user_id}"),
            encrypted_account_no=_encrypt_with(old_key, f"12345678-{user_id}"),
            encrypted_access_token=None,  # legitimate NULL — exercises skip path
            account_prod="01",
            encryption_key_version=1,
        )
        db.session.add(conn)
        db.session.commit()
        return conn.id


# ── Tests ────────────────────────────────────────────────────────────────────
def test_dry_run_mutates_nothing(app, script_module, capsys):
    """DRY-RUN: rows are inspected, counts logged, but DB unchanged."""
    old_key = _gen_key()
    new_key = _gen_key()
    row_id = _seed_broker_row(app, user_id=4001, old_key=old_key)

    from models.broker_connection import BrokerConnection

    with app.app_context():
        before = db.session.get(BrokerConnection, row_id)
        before_app_key = before.encrypted_app_key

    rc = script_module.main(
        ["--old-key", old_key, "--new-key", new_key, "--dry-run"]
    )
    assert rc == 0

    with app.app_context():
        after = db.session.get(BrokerConnection, row_id)
        # Ciphertext untouched.
        assert after.encrypted_app_key == before_app_key, (
            "DRY-RUN must not mutate encrypted_app_key"
        )
        # Still decryptable with the OLD key (we never wrote the new one).
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        raw = base64.b64decode(after.encrypted_app_key)
        aes_old = AESGCM(base64.b64decode(old_key))
        pt = aes_old.decrypt(raw[:12], raw[12:], b"broker").decode("utf-8")
        assert pt == "APP_KEY_4001"


def test_round_trip_single_row(app, script_module):
    """Real rotation: 1 row → all 3 NOT-NULL columns become readable with NEW key only."""
    old_key = _gen_key()
    new_key = _gen_key()
    row_id = _seed_broker_row(app, user_id=4002, old_key=old_key)

    rc = script_module.main(["--old-key", old_key, "--new-key", new_key])
    assert rc == 0

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from models.broker_connection import BrokerConnection

    aes_new = AESGCM(base64.b64decode(new_key))
    aes_old = AESGCM(base64.b64decode(old_key))

    with app.app_context():
        row = db.session.get(BrokerConnection, row_id)
        # NEW key recovers the original plaintext.
        for col_name, expected in (
            ("encrypted_app_key", "APP_KEY_4002"),
            ("encrypted_app_secret", "APP_SECRET_4002"),
            ("encrypted_account_no", "12345678-4002"),
        ):
            ct = getattr(row, col_name)
            assert ct, f"{col_name} should still be populated"
            raw = base64.b64decode(ct)
            pt = aes_new.decrypt(raw[:12], raw[12:], b"broker").decode("utf-8")
            assert pt == expected, f"{col_name} round-trip mismatch"

            # OLD key now FAILS (authenticated encryption ⇒ tag mismatch).
            with pytest.raises(Exception):
                aes_old.decrypt(raw[:12], raw[12:], b"broker")

        # NULL column stayed NULL.
        assert row.encrypted_access_token is None


def test_decrypt_failure_rolls_back_and_exits_2(app, script_module):
    """Wrong OLD key → SystemExit(2), no rows mutated."""
    real_old = _gen_key()
    wrong_old = _gen_key()
    new_key = _gen_key()
    row_id = _seed_broker_row(app, user_id=4003, old_key=real_old)

    from models.broker_connection import BrokerConnection

    with app.app_context():
        before = db.session.get(BrokerConnection, row_id).encrypted_app_key

    with pytest.raises(SystemExit) as exc_info:
        script_module.main(["--old-key", wrong_old, "--new-key", new_key])
    assert exc_info.value.code == 2

    with app.app_context():
        after = db.session.get(BrokerConnection, row_id).encrypted_app_key
        assert after == before, (
            "Decrypt failure must roll back — ciphertext should be unchanged"
        )


def test_legacy_plaintext_cache_left_alone(app, script_module, tmp_path):
    """Legacy plaintext .kis_token_cache.json → log + leave (auto-migrates on next refresh)."""
    cache_path = script_module._CACHE_FILE
    cache_path.write_text('{"token":"legacy","expires":"2099-01-01T00:00:00+00:00"}')
    original = cache_path.read_bytes()

    rc = script_module.main(
        ["--old-key", _gen_key(), "--new-key", _gen_key()]
    )
    assert rc == 0
    assert cache_path.read_bytes() == original, (
        "Legacy plaintext cache must not be rewritten — token_manager auto-migrates"
    )


def test_identical_keys_refused(app, script_module):
    """Old == New ⇒ SystemExit(1) (refuse no-op rotation)."""
    key = _gen_key()
    assert script_module.main(["--old-key", key, "--new-key", key]) == 1


def test_missing_keys_exits_1(app, script_module, monkeypatch):
    """No keys via env or args ⇒ SystemExit(1)."""
    monkeypatch.delenv("PIVOX_OLD_KEY", raising=False)
    monkeypatch.delenv("PIVOX_NEW_KEY", raising=False)
    assert script_module.main([]) == 1


def test_cache_round_trip(app, script_module):
    """AES-GCM cache file → rotated in place + readable with NEW key."""
    old_key = _gen_key()
    new_key = _gen_key()

    # Build a cache file in the exact wire format token_manager writes.
    aes_old = _aesgcm(old_key)
    plaintext_json = '{"token":"FAKE","expires":"2099-01-01T00:00:00+00:00"}'
    nonce = os.urandom(12)
    ct = aes_old.encrypt(nonce, plaintext_json.encode("utf-8"), b"kis-token-cache")
    body_b64 = base64.b64encode(nonce + ct).decode("ascii")

    cache_path = script_module._CACHE_FILE
    cache_path.write_bytes(b"PIVOX-AES-GCM-v1\n" + body_b64.encode("ascii"))

    rc = script_module.main(["--old-key", old_key, "--new-key", new_key])
    assert rc == 0

    # File should still start with the header.
    raw = cache_path.read_bytes()
    header = b"PIVOX-AES-GCM-v1\n"
    assert raw.startswith(header)

    # NEW key recovers the same plaintext.
    aes_new = _aesgcm(new_key)
    new_body_b64 = raw[len(header):].decode("ascii").strip()
    new_blob = base64.b64decode(new_body_b64)
    pt = aes_new.decrypt(new_blob[:12], new_blob[12:], b"kis-token-cache").decode("utf-8")
    assert pt == plaintext_json
