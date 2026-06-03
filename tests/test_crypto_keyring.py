"""Key-ring rotation tests for the user-text encryption layer.

The original ``EncryptedText`` shipped with a hardcoded ``pqenc:1:`` marker and a
single master key — the module header itself warned that rotating that key makes
every encrypted column permanently unrecoverable. This suite proves the
rotation-safe ring:

    * version 1 is always the master key (existing rows keep working);
    * adding a v2 key makes new writes ``pqenc:2:`` while v1 rows still decrypt;
    * a re-encrypt sweep rolls old-version rows forward.

The ring is module-global, so each test snapshots and restores it — otherwise a
rotation here would leak into ``test_encrypted_reflection`` (which asserts the
default ``pqenc:1:``).
"""
from __future__ import annotations

import os

import pytest

import services.crypto_service as cs


@pytest.fixture(autouse=True)
def _restore_ring():
    """Snapshot + restore the global key ring around every test."""
    saved_ring = dict(cs._USER_TEXT_KEY_RING)
    saved_current = cs._CURRENT_TEXT_VERSION
    saved_aes = dict(cs._AESGCM_RING)
    try:
        yield
    finally:
        cs._set_user_text_key_ring_for_test(saved_ring)
        cs._CURRENT_TEXT_VERSION = saved_current
        cs._AESGCM_RING.clear()
        cs._AESGCM_RING.update(saved_aes)


def test_default_ring_is_v1_master():
    assert cs.user_text_key_versions() == [1]
    assert cs.current_text_key_version() == 1


def test_v1_roundtrip_korean_and_emoji():
    ct = cs.encrypt_user_text("무서워서 팔았다 😬")
    assert ct.startswith("pqenc:1:")
    assert cs.decrypt_user_text(ct) == "무서워서 팔았다 😬"
    assert cs.is_encrypted_value(ct) is True
    assert cs.is_encrypted_value("plain text") is False


def test_rotation_v1_rows_still_decrypt_and_new_writes_use_v2():
    v1_ct = cs.encrypt_user_text("예전 글")
    assert v1_ct.startswith("pqenc:1:")

    k1 = cs._USER_TEXT_KEY_RING[1]
    cs._set_user_text_key_ring_for_test({1: k1, 2: os.urandom(32)})

    assert cs.current_text_key_version() == 2
    # old v1 row still readable after rotation (the whole point)
    assert cs.decrypt_user_text(v1_ct) == "예전 글"
    # new writes carry v2
    new_ct = cs.encrypt_user_text("새 글")
    assert new_ct.startswith("pqenc:2:")
    assert cs.decrypt_user_text(new_ct) == "새 글"


def test_reencrypt_sweep_rolls_v1_forward():
    v1_ct = cs.encrypt_user_text("롤포워드 대상")
    k1 = cs._USER_TEXT_KEY_RING[1]
    cs._set_user_text_key_ring_for_test({1: k1, 2: os.urandom(32)})

    rolled = cs.reencrypt_user_text(v1_ct)
    assert rolled is not None
    assert rolled.startswith("pqenc:2:")
    assert cs.decrypt_user_text(rolled) == "롤포워드 대상"

    # No-ops: already current, legacy plaintext, empty.
    assert cs.reencrypt_user_text(rolled) is None
    assert cs.reencrypt_user_text("legacy plaintext row") is None
    assert cs.reencrypt_user_text("") is None
    assert cs.reencrypt_user_text(None) is None


def test_encrypted_text_column_decodes_v1_row_after_rotation():
    """The TypeDecorator must read a pre-rotation v1 row once v2 is current —
    the realistic state right after an operator adds a new key."""
    et = cs.EncryptedText()
    stored_v1 = et.process_bind_param("로테이션 전 저장", None)
    assert stored_v1.startswith("pqenc:1:")

    k1 = cs._USER_TEXT_KEY_RING[1]
    cs._set_user_text_key_ring_for_test({1: k1, 2: os.urandom(32)})

    # read v1 row under the rotated ring
    assert et.process_result_value(stored_v1, None) == "로테이션 전 저장"
    # new writes now v2
    assert et.process_bind_param("로테이션 후", None).startswith("pqenc:2:")


def test_loader_ignores_v1_env_override():
    """A stray ``PIVOX_USER_TEXT_KEY_V1`` must never override the master key —
    that would orphan every existing v1 row."""
    os.environ["PIVOX_USER_TEXT_KEY_V1"] = "Zm9vYmFyZm9vYmFyZm9vYmFyZm9vYmFyMzI="
    try:
        ring = cs._load_user_text_key_ring()
        assert ring[1] == cs._MASTER_KEY  # master wins, env V1 ignored
    finally:
        del os.environ["PIVOX_USER_TEXT_KEY_V1"]


def test_missing_key_version_fails_loud_not_blank():
    """A row written at v2, then read after the v2 key is dropped on a redeploy
    (env-drift), must FAIL LOUD — never silently blank. A blanked value would be
    re-encrypted on the next ORM write and permanently overwrite the original
    ciphertext, turning a recoverable env mistake into permanent data loss."""
    et = cs.EncryptedText()
    k1 = cs._USER_TEXT_KEY_RING[1]
    cs._set_user_text_key_ring_for_test({1: k1, 2: os.urandom(32)})
    stored_v2 = et.process_bind_param("키 사라지기 전 저장", None)
    assert stored_v2.startswith("pqenc:2:")

    # Operator drops PIVOX_USER_TEXT_KEY_V2 → ring loses v2 (master only).
    cs._set_user_text_key_ring_for_test({1: k1})

    with pytest.raises(cs.MissingKeyVersionError):
        et.process_result_value(stored_v2, None)


def test_corrupt_ciphertext_blanks_not_raises():
    """A genuinely corrupted/tampered row (key present, auth tag mismatch) blanks
    just that one row rather than 500-ing the whole feed — the opposite policy
    from a missing key version."""
    et = cs.EncryptedText()
    stored = et.process_bind_param("정상 저장", None)
    prefix = "pqenc:1:"
    assert stored.startswith(prefix)
    body = stored[len(prefix):]
    mid = len(body) // 2
    flipped = "A" if body[mid] != "A" else "B"  # swap one base64 char → tag fails
    corrupt = prefix + body[:mid] + flipped + body[mid + 1:]
    assert et.process_result_value(corrupt, None) == ""
