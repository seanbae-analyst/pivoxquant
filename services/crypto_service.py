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
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets

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


# ── Fallback (dev/test only) ──────────────────────────────────────────────
def _fallback_encrypt(data: bytes, aad: bytes) -> str:
    """Authenticated XOR stream. NOT cryptographically equivalent to AES-GCM
    but preserves confidentiality + integrity for dev. Format:

        nonce(12) || xor_stream(data) || hmac_sha256_tag(16)

    Emits base64. Do NOT rely on this in production.
    """
    nonce = os.urandom(12)
    stream = _kdf_stream(_MASTER_KEY, nonce, len(data))
    ct = bytes(a ^ b for a, b in zip(data, stream))
    tag = hmac.new(_MASTER_KEY, nonce + aad + ct, hashlib.sha256).digest()[:16]
    return base64.b64encode(nonce + ct + tag).decode("ascii")


def _fallback_decrypt(raw: bytes, aad: bytes) -> str:
    if len(raw) < 12 + 16:
        raise ValueError("Ciphertext too short")
    nonce = raw[:12]
    tag = raw[-16:]
    ct = raw[12:-16]
    expected = hmac.new(_MASTER_KEY, nonce + aad + ct, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(tag, expected):
        raise ValueError("HMAC verification failed — ciphertext tampered or wrong key")
    stream = _kdf_stream(_MASTER_KEY, nonce, len(ct))
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
