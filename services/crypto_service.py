"""
PivoxQuant — Symmetric encryption helper for broker credentials.

Primary backend: AES-256-GCM via `cryptography.hazmat.primitives.ciphers.aead.AESGCM`.
Fallback (dev only, cryptography not installed): Fernet-style base64 obfuscation
with HMAC-SHA256 authentication using the MASTER_KEY. The fallback is **NOT**
approved for production — it logs a loud warning on every encrypt call.

Key source: `PIVOX_BROKER_ENCRYPTION_KEY` env var (base64-encoded 32 bytes).
If unset, a random key is generated at import time for dev/test isolation
(ciphertext will not survive process restarts — also logs a warning).

Public API:
    encrypt(plaintext: str, aad: bytes = b"broker") -> str   # returns base64
    decrypt(ciphertext_b64: str, aad: bytes = b"broker") -> str

AAD (Additional Authenticated Data) binds ciphertext to a context and prevents
cross-context replay. Default context is b"broker".

Week 1 — 2026-04-18.

────────────────────────────────────────────────────────────────────────────
2026-05-18 Wave G-2 P1 Bug #1 (partial admit) — KEY ROTATION LIMITATION
────────────────────────────────────────────────────────────────────────────
`BrokerConnection.encryption_key_version` exists as a SmallInteger column on
the broker_connections table but is currently **schema theater**: every row
is hardcoded to `1` at write time (see services/broker/user_kis_service.py
upsert_kis_connection + services/broker/user_alpaca_service.py
upsert_alpaca_connection). This module loads a SINGLE master key from
`PIVOX_BROKER_ENCRYPTION_KEY` — there is no key ring, no `decrypt_versioned()`
selector, and no per-version env var fanout (e.g.
`PIVOX_BROKER_ENCRYPTION_KEY_V1`, `_V2`, ...).

Operational consequence: rotating `PIVOX_BROKER_ENCRYPTION_KEY` makes every
existing encrypted column on broker_connections (encrypted_app_key,
encrypted_app_secret, encrypted_account_no, encrypted_access_token)
**permanently unrecoverable** on the next decrypt call. Users get a
DECRYPT_FAILED 500 and must re-enter their KIS credentials.

External-action carry-over: operators MUST run a re-encrypt migration script
(decrypt with old key → encrypt with new key → persist + bump
encryption_key_version) BEFORE rotating the env var in production.

Real fix (separate wave): introduce a key-ring loader (dict[int, bytes]
keyed by version), `decrypt_versioned(ct, version, aad)`, and have callers
pass `conn.encryption_key_version` through to decrypt.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import re
import secrets

from sqlalchemy.types import Text, TypeDecorator

logger = logging.getLogger(__name__)


# ── Key bootstrap ─────────────────────────────────────────────────────────
class MissingEncryptionKeyError(RuntimeError):
    """Raised when PIVOX_BROKER_ENCRYPTION_KEY is required but absent.

    Fail-fast in production: a missing key means ALL encrypted broker
    credentials (KIS app_key/app_secret/account_no) will become
    unrecoverable after the next process restart, silently logging users
    out of their broker connections. This MUST block startup in prod.
    """


def _is_production() -> bool:
    """Detect a production environment.

    Heuristics (any one true => prod):
      - FLASK_ENV=production
      - PIVOX_ENV=production / prod
      - RAILWAY_ENVIRONMENT_NAME=production (Railway-specific)
      - DEPLOY_ENV / APP_ENV set to production/prod
    Tests set FLASK_ENV=testing (see conftest.py) so they bypass this.
    """
    env_vars = (
        os.environ.get("FLASK_ENV"),
        os.environ.get("PIVOX_ENV"),
        os.environ.get("RAILWAY_ENVIRONMENT_NAME"),
        os.environ.get("DEPLOY_ENV"),
        os.environ.get("APP_ENV"),
    )
    for v in env_vars:
        if v and v.strip().lower() in ("production", "prod"):
            return True
    return False


def _load_master_key() -> bytes:
    """Load or generate the 32-byte master key.

    Prefers `PIVOX_BROKER_ENCRYPTION_KEY` (base64, 32-byte decoded). Falls back
    to `BROKER_ENCRYPTION_KEY`. In **production** a missing key raises
    :class:`MissingEncryptionKeyError` (fail-fast). In dev/test only, an
    ephemeral random key is generated with a loud warning.
    """
    for var in ("PIVOX_BROKER_ENCRYPTION_KEY", "BROKER_ENCRYPTION_KEY"):
        raw = os.environ.get(var, "").strip()
        if not raw:
            continue
        try:
            key = base64.b64decode(raw)
        except Exception:
            # Allow raw utf-8 32-byte string as well.
            key = raw.encode("utf-8")
        if len(key) == 32:
            return key
        # If the supplied value isn't exactly 32 bytes, derive a 32-byte key
        # via SHA-256. Acceptable for a shared secret string.
        return hashlib.sha256(key).digest()

    # No key configured.
    if _is_production():
        # Fail-fast: refuse to boot with an ephemeral key in prod. Losing this
        # key between restarts corrupts every BrokerConnection row.
        raise MissingEncryptionKeyError(
            "PIVOX_BROKER_ENCRYPTION_KEY is not set in production. "
            "Refusing to boot with an ephemeral key — broker credentials "
            "would become unrecoverable on the next restart. "
            "Set PIVOX_BROKER_ENCRYPTION_KEY (32 bytes, base64) and redeploy."
        )
    # Dev/test: ephemeral key with loud warning.
    logger.warning(
        "crypto_service: PIVOX_BROKER_ENCRYPTION_KEY not set — using an "
        "ephemeral random key (DEV/TEST ONLY). Encrypted broker credentials "
        "will NOT survive process restart. Set PIVOX_BROKER_ENCRYPTION_KEY "
        "in production (fail-fast enforced)."
    )
    return secrets.token_bytes(32)


_MASTER_KEY: bytes = _load_master_key()


# ── Backend selection ─────────────────────────────────────────────────────
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore

    _BACKEND = "aesgcm"
    _aes = AESGCM(_MASTER_KEY)
except Exception:  # pragma: no cover — cryptography optional in dev
    _BACKEND = "fallback"
    _aes = None
    logger.warning(
        "crypto_service: `cryptography` library not available — using HMAC "
        "fallback. Install `cryptography>=42.0.0` before production."
    )


# ── User-text key ring (rotation-safe) ─────────────────────────────────────
# The broker ``encrypt``/``decrypt`` path uses the single master key. User
# free-text columns (``EncryptedText``) instead resolve their key by VERSION
# from this ring, so the user-text key can be rotated WITHOUT making existing
# rows unrecoverable — the exact failure mode this module's header warns about.
# Version 1 is ALWAYS the master key: this keeps every pre-existing
# ``pqenc:1:`` row (and the no-migration legacy-plaintext fallback) readable.
# Add ``PIVOX_USER_TEXT_KEY_V2`` (base64, 32 bytes) to introduce v2 — new writes
# use it while v1 rows still decrypt; a re-encrypt sweep then rolls rows forward
# (scripts/reencrypt_user_text.py).
def _load_user_text_key_ring() -> dict:
    ring = {1: _MASTER_KEY}
    for var, raw in os.environ.items():
        m = re.fullmatch(r"PIVOX_USER_TEXT_KEY_V(\d+)", var)
        if not m:
            continue
        version = int(m.group(1))
        if version < 2:
            # v1 is reserved for the master key — never let a stray env var
            # orphan existing v1 ciphertext.
            continue
        val = (raw or "").strip()
        if not val:
            continue
        try:
            key = base64.b64decode(val)
        except Exception:
            key = val.encode("utf-8")
        if len(key) != 32:
            key = hashlib.sha256(key).digest()
        ring[version] = key
    return ring


_USER_TEXT_KEY_RING: dict = _load_user_text_key_ring()
_CURRENT_TEXT_VERSION: int = max(_USER_TEXT_KEY_RING)
_AESGCM_RING: dict = {}


def _aesgcm_for(version: int):
    """Return a cached AESGCM bound to the ring key for ``version``."""
    inst = _AESGCM_RING.get(version)
    if inst is None:
        key = _USER_TEXT_KEY_RING.get(version)
        if key is None:
            raise ValueError(
                f"crypto_service: no user-text key for version {version}"
            )
        inst = AESGCM(key)
        _AESGCM_RING[version] = inst
    return inst


# ── Public API ────────────────────────────────────────────────────────────
def encrypt(plaintext: str, aad: bytes = b"broker") -> str:
    """Encrypt and return a base64 string. Nonce is prepended (12 bytes)."""
    if plaintext is None:
        raise ValueError("plaintext cannot be None")
    data = plaintext.encode("utf-8")

    if _BACKEND == "aesgcm":
        nonce = os.urandom(12)
        ct = _aes.encrypt(nonce, data, aad)
        return base64.b64encode(nonce + ct).decode("ascii")

    # Fallback: XOR-stream derived from HKDF-like SHA256(key || nonce) + HMAC tag.
    return _fallback_encrypt(data, aad)


def decrypt(ciphertext_b64: str, aad: bytes = b"broker") -> str:
    """Decrypt a base64 ciphertext produced by `encrypt`."""
    if not ciphertext_b64:
        raise ValueError("ciphertext is empty")
    try:
        raw = base64.b64decode(ciphertext_b64)
    except Exception as exc:
        raise ValueError(f"Invalid base64 ciphertext: {exc}") from exc

    if _BACKEND == "aesgcm":
        if len(raw) < 13:
            raise ValueError("Ciphertext too short")
        nonce, ct = raw[:12], raw[12:]
        pt = _aes.decrypt(nonce, ct, aad)
        return pt.decode("utf-8")

    return _fallback_decrypt(raw, aad)


def is_configured() -> bool:
    """True if a real encryption key is configured (not ephemeral)."""
    return bool(
        os.environ.get("PIVOX_BROKER_ENCRYPTION_KEY")
        or os.environ.get("BROKER_ENCRYPTION_KEY")
    )


def backend_name() -> str:
    """Return which backend is in use ('aesgcm' or 'fallback')."""
    return _BACKEND


def is_encrypted_value(value: str | None) -> bool:
    """True iff ``value`` carries the EncryptedText version marker — i.e. it is
    our ciphertext rather than a legacy plaintext row. Matches any key version
    (``pqenc:1:``, ``pqenc:2:`` …) via the shared base prefix."""
    return bool(value) and value.startswith(_ENC_PREFIX_BASE)


# ── Transparent encrypted column (SQLAlchemy) ─────────────────────────────
# Every ciphertext we persist starts with ``pqenc:{version}:`` — the version
# selects the key from the user-text key ring so the column can (a) tell its
# own ciphertext apart from *legacy plaintext* rows written before encryption
# was switched on (the rollout needs no data migration) and (b) survive a key
# rotation (``pqenc:2:`` rows coexist with ``pqenc:1:``).
_ENC_PREFIX_BASE = "pqenc:"
_ENC_VERSIONED_RE = re.compile(r"^pqenc:(\d+):")
# Retained literal for the v1 prefix (back-compat with any external reference).
_ENC_PREFIX = "pqenc:1:"

# AAD context for user free-text. Distinct from b"broker" (credentials) so a
# ciphertext from one domain can never be replayed into the other.
_USER_TEXT_AAD = b"pivox_user_text"


def encrypt_user_text(plaintext, version: int | None = None) -> str:
    """Encrypt a user free-text value for an :class:`EncryptedText` column.

    Returns ``pqenc:{version}:{base64(nonce||ciphertext)}``. Uses the current
    (highest) key-ring version unless ``version`` is pinned — pinning is used
    only by the re-encrypt utility and tests.
    """
    v = _CURRENT_TEXT_VERSION if version is None else int(version)
    data = str(plaintext).encode("utf-8")
    if _BACKEND == "aesgcm":
        nonce = os.urandom(12)
        ct = _aesgcm_for(v).encrypt(nonce, data, _USER_TEXT_AAD)
        body = base64.b64encode(nonce + ct).decode("ascii")
    else:
        key = _USER_TEXT_KEY_RING.get(v)
        if key is None:
            raise ValueError(f"crypto_service: no key for user-text version {v}")
        body = _fallback_encrypt(data, _USER_TEXT_AAD, key=key)
    return f"{_ENC_PREFIX_BASE}{v}:{body}"


def decrypt_user_text(stored: str) -> str:
    """Decrypt a value produced by :func:`encrypt_user_text` (any version)."""
    m = _ENC_VERSIONED_RE.match(stored or "")
    if not m:
        raise ValueError("crypto_service: not a versioned user-text ciphertext")
    v = int(m.group(1))
    body = stored[m.end():]
    if _BACKEND == "aesgcm":
        raw = base64.b64decode(body)
        if len(raw) < 13:
            raise ValueError("Ciphertext too short")
        nonce, ct = raw[:12], raw[12:]
        return _aesgcm_for(v).decrypt(nonce, ct, _USER_TEXT_AAD).decode("utf-8")
    key = _USER_TEXT_KEY_RING.get(v)
    if key is None:
        raise ValueError(f"crypto_service: key version {v} not in ring")
    return _fallback_decrypt(base64.b64decode(body), _USER_TEXT_AAD, key=key)


def reencrypt_user_text(stored):
    """Roll one stored value forward to the current key version.

    Returns the re-encrypted ciphertext, or ``None`` when nothing needs doing
    (empty, legacy plaintext — those re-encrypt on the next ORM write — or
    already at the current version). Used by ``scripts/reencrypt_user_text.py``
    for an eager rotation sweep.
    """
    if not stored or not str(stored).startswith(_ENC_PREFIX_BASE):
        return None
    m = _ENC_VERSIONED_RE.match(stored)
    if not m or int(m.group(1)) == _CURRENT_TEXT_VERSION:
        return None
    return encrypt_user_text(decrypt_user_text(stored))


def current_text_key_version() -> int:
    """Highest key-ring version — the one new writes are encrypted under."""
    return _CURRENT_TEXT_VERSION


def user_text_key_versions() -> list:
    """Sorted list of every key version currently loadable for decryption."""
    return sorted(_USER_TEXT_KEY_RING)


def _set_user_text_key_ring_for_test(ring) -> None:
    """TEST-ONLY: swap the in-memory key ring and reset the AESGCM cache."""
    global _USER_TEXT_KEY_RING, _CURRENT_TEXT_VERSION
    _USER_TEXT_KEY_RING = dict(ring)
    _CURRENT_TEXT_VERSION = max(_USER_TEXT_KEY_RING)
    _AESGCM_RING.clear()


class EncryptedText(TypeDecorator):
    """Transparent application-level encryption for sensitive free-text columns.

    Persisted on the database as ``TEXT`` (so switching an existing ``Text``
    column to this type needs **no schema migration** — the stored bytes are
    just ciphertext), but the ORM keeps reading and writing *plaintext*. Every
    existing call site (``row.rationale = "..."`` / ``row.rationale``) is
    unchanged; encryption happens at the bind/result boundary.

    Tier — encrypt-at-rest with a **server-held** key
    (``PIVOX_BROKER_ENCRYPTION_KEY``):
      - Covers: a DB dump, a leaked backup, or a read-access contractor can no
        longer read the user's words. This is the realistic breach for a small
        startup.
      - Does NOT cover: this is **not** end-to-end. The app can still decrypt to
        render the mirror to its owner. A true "we *cannot* read it" guarantee
        needs a user-held key — a separate product decision, because it would
        also stop the server-side pattern/mirror from reading the text.

    Backward compatible: a legacy plaintext row (no version marker) is returned
    as-is on read and re-encrypted the next time it is written.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):  # noqa: D401 - SA hook
        if value is None:
            return None
        return encrypt_user_text(str(value))

    def process_result_value(self, value, dialect):  # noqa: D401 - SA hook
        if value is None:
            return None
        if not value.startswith(_ENC_PREFIX_BASE):
            # Legacy plaintext (written before this column was encrypted).
            return value
        try:
            return decrypt_user_text(value)
        except Exception:  # pragma: no cover - key mismatch / tamper only
            # Never 500 the journal over one unreadable row; log loud, blank it.
            logger.error(
                "EncryptedText: decrypt failed for a user_text column — "
                "returning empty. Check key rotation (PIVOX_USER_TEXT_KEY_V*) "
                "or the master key."
            )
            return ""


# ── Fallback (dev/test only) ──────────────────────────────────────────────
def _fallback_encrypt(data: bytes, aad: bytes, key: bytes | None = None) -> str:
    """Authenticated XOR stream. NOT cryptographically equivalent to AES-GCM
    but preserves confidentiality + integrity for dev. Format:

        nonce(12) || xor_stream(data) || hmac_sha256_tag(16)

    Emits base64. ``key`` defaults to the master key (broker path); the
    user-text ring passes the per-version key. Do NOT rely on this in prod.
    """
    k = key if key is not None else _MASTER_KEY
    nonce = os.urandom(12)
    stream = _kdf_stream(k, nonce, len(data))
    ct = bytes(a ^ b for a, b in zip(data, stream))
    tag = hmac.new(k, nonce + aad + ct, hashlib.sha256).digest()[:16]
    return base64.b64encode(nonce + ct + tag).decode("ascii")


def _fallback_decrypt(raw: bytes, aad: bytes, key: bytes | None = None) -> str:
    k = key if key is not None else _MASTER_KEY
    if len(raw) < 12 + 16:
        raise ValueError("Ciphertext too short")
    nonce = raw[:12]
    tag = raw[-16:]
    ct = raw[12:-16]
    expected = hmac.new(k, nonce + aad + ct, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(tag, expected):
        raise ValueError("HMAC verification failed — ciphertext tampered or wrong key")
    stream = _kdf_stream(k, nonce, len(ct))
    pt = bytes(a ^ b for a, b in zip(ct, stream))
    return pt.decode("utf-8")


def _kdf_stream(key: bytes, nonce: bytes, length: int) -> bytes:
    """Generate a keystream of `length` bytes from (key, nonce) via SHA256 CTR."""
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])
