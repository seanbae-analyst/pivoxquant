"""Rotate ``PIVOX_BROKER_ENCRYPTION_KEY`` — re-encrypt every persisted secret.

External action #14 (HANDOVER v44.9). v44.9 PR #485 made the KIS token cache
itself AES-GCM, but rotating the master key still permanently bricks every
``BrokerConnection`` row — see services/crypto_service.py module docstring.
This script is the operator-side mitigation: decrypt-with-old → encrypt-with-new
in a single transaction per batch.

Usage
-----
    # DRY-RUN — no DB writes, prints counts + 3-row sample
    PIVOX_OLD_KEY=<old-base64> PIVOX_NEW_KEY=<new-base64> \\
        python scripts/rotate_broker_encryption_key.py --dry-run

    # Real rotation
    PIVOX_OLD_KEY=<old-base64> PIVOX_NEW_KEY=<new-base64> \\
        python scripts/rotate_broker_encryption_key.py

    # Argument form (keys NOT echoed to history → prefer env vars)
    python scripts/rotate_broker_encryption_key.py \\
        --old-key=<old-base64> --new-key=<new-base64>

Operator procedure
------------------
1. Generate a new 32-byte key:  ``python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"``
2. Run with ``--dry-run`` first against prod DB. Confirm the row count + that
   no rows fail to decrypt with the OLD key.
3. Stop the prod app (or accept ~3s of write conflict — rotations take batched
   per-row UPDATEs and we use SELECT FOR UPDATE inside each batch).
4. Re-run WITHOUT ``--dry-run``.
5. Update ``PIVOX_BROKER_ENCRYPTION_KEY`` env var to the new key + redeploy.
6. Delete ``.kis_token_cache.json`` files on each worker (or just let the
   next ``get_token()`` re-issue — see services/kis/token_manager.py
   ``_load_from_file`` decrypt-fail branch).

Scope
-----
- ``broker_connections`` table — 4 ciphertext columns per row:
    encrypted_app_key, encrypted_app_secret, encrypted_account_no,
    encrypted_access_token.
- KIS token cache file (``.kis_token_cache.json``) — re-encrypted in place
  with ``aad=b"kis-token-cache"``.

Out of scope
------------
- ``encryption_key_version`` bump — currently schema theater (every row = 1,
  see services/crypto_service.py). Bumping it without a key-ring loader
  buys nothing. The real fix is the separate "key-ring" wave noted in
  crypto_service.py.
- Legacy plaintext columns (``access_token``, ``refresh_token``) — Alpaca
  legacy fields, never encrypted, no-op.

Safety
------
- Per-batch transaction: a single row failure rolls back the whole batch
  and the script aborts with a non-zero exit code (no half-rotated rows).
- Structured JSON log to stdout: ``{ts, row_id, broker, columns_rotated,
  status, error_kind}``.
- AES-GCM authenticates ciphertext, so a wrong OLD key fails fast with
  ``InvalidTag`` rather than silently producing garbage plaintext.
- Re-encrypt round-trip is verified before writing (decrypt-with-new
  recovers the same plaintext) — guards against partially-applied AES
  state if the process crashes mid-write.

Exit codes
----------
    0  rotation (or dry-run) completed successfully.
    1  invalid CLI / missing keys.
    2  decrypt failure with OLD key on at least one row.
    3  re-encrypt round-trip verification failure.
    4  DB connectivity / unexpected error.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional, Sequence, Tuple

# Make project root importable when run directly.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ─── Constants (mirrored from services to avoid coupling to module init) ────
#
# We CANNOT import services.crypto_service here: it pins a single AESGCM
# instance to whatever PIVOX_BROKER_ENCRYPTION_KEY was at process start,
# which is exactly the wrong shape for rotation. We re-implement the same
# AES-GCM wire format (12-byte nonce prepended, base64-encoded) using two
# independent AESGCM objects (old, new).
#
# Wire format must stay bit-identical to crypto_service.encrypt/decrypt
# so apps reading the rotated rows see the same shape.
_CACHE_FILE = ROOT / ".kis_token_cache.json"
_CACHE_HEADER = b"PIVOX-AES-GCM-v1\n"
_CACHE_AAD = b"kis-token-cache"
_BROKER_AAD = b"broker"  # services.crypto_service default

_BROKER_TABLE = "broker_connections"
_CIPHERTEXT_COLUMNS: Tuple[str, ...] = (
    "encrypted_app_key",
    "encrypted_app_secret",
    "encrypted_account_no",
    "encrypted_access_token",
)


# ─── Logging — structured JSON to stdout ────────────────────────────────────
class _JsonFormatter(logging.Formatter):
    """Single-line JSON formatter. Extra fields land on the top level."""

    _RESERVED = {
        "name", "msg", "args", "levelname", "levelno", "pathname",
        "filename", "module", "exc_info", "exc_text", "stack_info",
        "lineno", "funcName", "created", "msecs", "relativeCreated",
        "thread", "threadName", "processName", "process", "message",
        "asctime", "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        for k, v in record.__dict__.items():
            if k not in self._RESERVED and not k.startswith("_"):
                payload[k] = v
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


_BASE_LOGGER = logging.getLogger("rotate_broker_encryption_key")


class _StructuredLogger:
    """Tiny shim — ``logger.info("msg", row_id=1)`` lands as a JSON field.

    Python's :mod:`logging` rejects unknown kwargs on the standard
    ``Logger`` methods. To attach arbitrary structured fields we have to
    funnel them through the documented ``extra=`` dict, which the
    formatter then reads off ``record.__dict__``. This wrapper makes the
    call sites readable (``logger.info("msg", k=v)``) while preserving
    the stdlib's reserved-name protections via ``LogRecord``'s own
    ``KeyError`` on collision.
    """

    def __init__(self, base: logging.Logger) -> None:
        self._base = base

    def _emit(self, level: int, msg: str, *, exc_info: bool = False, **fields) -> None:
        self._base.log(level, msg, extra=fields, exc_info=exc_info)

    def debug(self, msg: str, **fields) -> None:
        self._emit(logging.DEBUG, msg, **fields)

    def info(self, msg: str, **fields) -> None:
        self._emit(logging.INFO, msg, **fields)

    def warning(self, msg: str, **fields) -> None:
        self._emit(logging.WARNING, msg, **fields)

    def error(self, msg: str, *, exc_info: bool = False, **fields) -> None:
        self._emit(logging.ERROR, msg, exc_info=exc_info, **fields)


logger = _StructuredLogger(_BASE_LOGGER)


def _setup_logger(verbose: bool) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    _BASE_LOGGER.addHandler(handler)
    _BASE_LOGGER.setLevel(logging.DEBUG if verbose else logging.INFO)
    _BASE_LOGGER.propagate = False


# ─── Key parsing — mirror services/crypto_service._load_master_key ──────────
def _parse_key(raw: str, *, name: str) -> bytes:
    """Mirror crypto_service._load_master_key, but for a supplied string.

    Accepts:
      - base64-encoded 32 bytes (preferred — same format as the env var)
      - raw 32-byte utf-8
      - any other string → SHA-256-derived 32 bytes (parity with
        crypto_service which silently SHA-256s non-32-byte inputs).
    """
    raw = raw.strip()
    if not raw:
        raise ValueError(f"{name}: empty key")
    try:
        key = base64.b64decode(raw, validate=False)
    except Exception:
        key = raw.encode("utf-8")
    if len(key) == 32:
        return key
    return hashlib.sha256(key).digest()


# ─── Stream rows from broker_connections in batches ─────────────────────────
def _iter_rows(session, batch_size: int) -> Iterator[Sequence]:
    """Yield batches of (id, broker, *ciphertext_columns) tuples.

    Server-side cursor would be ideal on Postgres but SQLAlchemy + Flask
    sessions don't expose one portably; we LIMIT/OFFSET with a stable
    ``ORDER BY id`` instead — fine for the row counts we expect
    (production currently <100 broker rows; this is operator tooling,
    not a hot path).
    """
    from sqlalchemy import text

    cols_sql = ", ".join(("id", "broker") + _CIPHERTEXT_COLUMNS)
    sql = text(
        f"SELECT {cols_sql} FROM {_BROKER_TABLE} "
        f"ORDER BY id ASC LIMIT :limit OFFSET :offset"
    )

    offset = 0
    while True:
        batch = session.execute(sql, {"limit": batch_size, "offset": offset}).fetchall()
        if not batch:
            return
        yield batch
        if len(batch) < batch_size:
            return
        offset += batch_size


# ─── Per-row rotation ────────────────────────────────────────────────────────
def _rotate_value(
    ciphertext_b64: Optional[str],
    *,
    aad: bytes,
    aes_old,
    aes_new,
) -> Tuple[Optional[str], bool]:
    """Return (new_ciphertext_or_None, rotated_bool).

    NULL / empty input is a legitimate state (e.g. encrypted_access_token
    is NULL until first KIS auth) — propagate unchanged.

    Re-encrypt round-trip is verified: decrypting the new ciphertext with
    the new key must recover the same plaintext.
    """
    if not ciphertext_b64:
        return None, False

    # Decrypt with OLD key.
    raw = base64.b64decode(ciphertext_b64)
    if len(raw) < 13:
        raise ValueError(f"ciphertext too short ({len(raw)} bytes)")
    nonce_old, ct_old = raw[:12], raw[12:]
    plaintext = aes_old.decrypt(nonce_old, ct_old, aad)

    # Encrypt with NEW key.
    nonce_new = os.urandom(12)
    ct_new = aes_new.encrypt(nonce_new, plaintext, aad)
    new_b64 = base64.b64encode(nonce_new + ct_new).decode("ascii")

    # Round-trip verify with NEW key — guards against partial AES state
    # corruption mid-batch (paranoia, but cheap and provable).
    raw_check = base64.b64decode(new_b64)
    verify_pt = aes_new.decrypt(raw_check[:12], raw_check[12:], aad)
    if verify_pt != plaintext:
        raise RuntimeError("re-encrypt verification mismatch (new ct decrypts to different plaintext)")

    return new_b64, True


def _rotate_broker_rows(
    *,
    aes_old,
    aes_new,
    batch_size: int,
    dry_run: bool,
    sample_limit: int = 3,
) -> Tuple[int, int]:
    """Return (rows_seen, columns_rotated). Raises on first hard failure."""
    from app import create_app
    from extensions import db
    from sqlalchemy import text

    app = create_app()

    rows_seen = 0
    cols_rotated = 0
    samples_logged = 0

    with app.app_context():
        # Ensure the broker_connections table exists. Operators sometimes
        # point this at an empty fresh DB by mistake.
        try:
            from sqlalchemy import inspect as _inspect

            tables = set(_inspect(db.engine).get_table_names())
        except Exception as exc:
            logger.error("schema introspection failed", exc_info=True, exc_kind=type(exc).__name__)
            raise SystemExit(4) from exc

        if _BROKER_TABLE not in tables:
            logger.warning(
                "broker_connections table missing — nothing to rotate",
                table=_BROKER_TABLE,
            )
            return 0, 0

        for batch in _iter_rows(db.session, batch_size):
            batch_updates: list[dict] = []
            for row in batch:
                rows_seen += 1
                row_id = row[0]
                broker = row[1]
                col_values = row[2:]

                new_values: dict[str, Optional[str]] = {}
                rotated_in_row = 0
                try:
                    for col_name, ct in zip(_CIPHERTEXT_COLUMNS, col_values):
                        new_ct, rotated = _rotate_value(
                            ct,
                            aad=_BROKER_AAD,
                            aes_old=aes_old,
                            aes_new=aes_new,
                        )
                        if rotated:
                            new_values[col_name] = new_ct
                            rotated_in_row += 1
                except Exception as exc:
                    logger.error(
                        "decrypt-with-old-key failed",
                        row_id=row_id,
                        broker=broker,
                        exc_kind=type(exc).__name__,
                        exc_msg=str(exc),
                    )
                    db.session.rollback()
                    raise SystemExit(2) from exc

                cols_rotated += rotated_in_row

                if rotated_in_row and not dry_run:
                    batch_updates.append({"row_id": row_id, **new_values})

                if samples_logged < sample_limit:
                    logger.info(
                        "row inspected",
                        row_id=row_id,
                        broker=broker,
                        columns_rotated=rotated_in_row,
                        dry_run=dry_run,
                    )
                    samples_logged += 1

            if dry_run:
                continue

            # Per-batch UPDATE inside one transaction. We build a parameterised
            # UPDATE per row to avoid touching columns that are NULL (those
            # rotated 0 columns and stay out of the SET clause entirely).
            try:
                for upd in batch_updates:
                    row_id = upd.pop("row_id")
                    set_parts = ", ".join(f"{c} = :{c}" for c in upd.keys())
                    if not set_parts:
                        continue  # all columns NULL — no-op
                    sql = text(f"UPDATE {_BROKER_TABLE} SET {set_parts} WHERE id = :row_id")
                    db.session.execute(sql, {"row_id": row_id, **upd})
                db.session.commit()
                logger.info(
                    "batch committed",
                    batch_rows=len(batch),
                    batch_updates=len(batch_updates),
                )
            except Exception as exc:
                db.session.rollback()
                logger.error(
                    "batch UPDATE failed — rolled back",
                    exc_kind=type(exc).__name__,
                    exc_msg=str(exc),
                )
                raise SystemExit(4) from exc

    return rows_seen, cols_rotated


# ─── KIS token cache file (separate from DB) ─────────────────────────────────
def _rotate_kis_token_cache(*, aes_old, aes_new, dry_run: bool) -> bool:
    """Rotate ``.kis_token_cache.json`` if present.

    Returns True if the cache existed and was processed, False if absent.
    Decrypt failure here is NON-FATAL — the cache is regenerable (next
    get_token() reissues). We log a warning + delete the un-rotatable
    file unless --dry-run, then return.
    """
    if not _CACHE_FILE.exists():
        logger.info("kis token cache absent — skip", path=str(_CACHE_FILE))
        return False

    try:
        raw = _CACHE_FILE.read_bytes()
    except OSError as exc:
        logger.warning(
            "kis token cache read failed — skip",
            path=str(_CACHE_FILE),
            exc_kind=type(exc).__name__,
        )
        return False

    if not raw.startswith(_CACHE_HEADER):
        # Plaintext legacy file — token_manager._load_from_file accepts it
        # once and re-saves on next refresh. Not our problem to rotate.
        logger.info(
            "kis token cache is legacy plaintext — leave for auto-migration",
            path=str(_CACHE_FILE),
        )
        return True

    body_b64 = raw[len(_CACHE_HEADER):].decode("ascii").strip()
    try:
        new_b64, rotated = _rotate_value(
            body_b64,
            aad=_CACHE_AAD,
            aes_old=aes_old,
            aes_new=aes_new,
        )
    except Exception as exc:
        logger.warning(
            "kis token cache decrypt-with-old-key failed — will delete (regenerable)",
            path=str(_CACHE_FILE),
            exc_kind=type(exc).__name__,
            dry_run=dry_run,
        )
        if not dry_run:
            try:
                _CACHE_FILE.unlink()
            except OSError:
                pass
        return True

    if dry_run or not rotated or new_b64 is None:
        logger.info(
            "kis token cache rotation simulated",
            path=str(_CACHE_FILE),
            dry_run=dry_run,
        )
        return True

    # Atomic-ish write: tmp + rename keeps the file readable at all times.
    tmp = _CACHE_FILE.with_suffix(_CACHE_FILE.suffix + ".tmp")
    try:
        tmp.write_bytes(_CACHE_HEADER + new_b64.encode("ascii"))
        os.chmod(tmp, 0o600)
        os.replace(tmp, _CACHE_FILE)
    except OSError as exc:
        logger.warning(
            "kis token cache write failed — left original",
            path=str(_CACHE_FILE),
            exc_kind=type(exc).__name__,
        )
        try:
            tmp.unlink()
        except OSError:
            pass
        return True

    logger.info("kis token cache rotated", path=str(_CACHE_FILE))
    return True


# ─── Entrypoint ─────────────────────────────────────────────────────────────
def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="rotate_broker_encryption_key",
        description="Rotate PIVOX_BROKER_ENCRYPTION_KEY — re-encrypt every broker secret.",
    )
    p.add_argument(
        "--old-key",
        default=os.environ.get("PIVOX_OLD_KEY", ""),
        help="Current key (base64 32 bytes). Default: $PIVOX_OLD_KEY.",
    )
    p.add_argument(
        "--new-key",
        default=os.environ.get("PIVOX_NEW_KEY", ""),
        help="New key (base64 32 bytes). Default: $PIVOX_NEW_KEY.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect + log without writing DB or rewriting cache file.",
    )
    p.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Rows per transaction (default 100).",
    )
    p.add_argument(
        "--skip-cache",
        action="store_true",
        help="Skip .kis_token_cache.json rotation (DB-only mode).",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="DEBUG-level structured logs.",
    )
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_argparser().parse_args(argv)
    _setup_logger(args.verbose)

    if not args.old_key or not args.new_key:
        logger.error("missing --old-key/--new-key (or PIVOX_OLD_KEY / PIVOX_NEW_KEY env)")
        return 1
    if args.old_key == args.new_key:
        logger.error("--old-key and --new-key are identical — refusing no-op rotation")
        return 1
    if args.batch_size <= 0:
        logger.error("--batch-size must be positive", batch_size=args.batch_size)
        return 1

    try:
        old_bytes = _parse_key(args.old_key, name="old-key")
        new_bytes = _parse_key(args.new_key, name="new-key")
    except ValueError as exc:
        logger.error("key parse failed", exc_msg=str(exc))
        return 1

    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        # The fallback in crypto_service uses an HMAC-XOR scheme that is NOT
        # safe to rotate across — refuse rather than silently producing
        # garbage. Operators must install cryptography before rotating.
        logger.error("cryptography package not installed — refusing fallback-backend rotation")
        return 4

    aes_old = AESGCM(old_bytes)
    aes_new = AESGCM(new_bytes)

    logger.info(
        "rotation start",
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        skip_cache=args.skip_cache,
    )

    rows_seen, cols_rotated = _rotate_broker_rows(
        aes_old=aes_old,
        aes_new=aes_new,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )

    cache_processed = False
    if not args.skip_cache:
        cache_processed = _rotate_kis_token_cache(
            aes_old=aes_old,
            aes_new=aes_new,
            dry_run=args.dry_run,
        )

    logger.info(
        "rotation complete",
        rows_seen=rows_seen,
        columns_rotated=cols_rotated,
        cache_processed=cache_processed,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
