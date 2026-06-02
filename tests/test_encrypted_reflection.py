"""Proof tests — user free-text (rationale / devil_advocate_seen) is
encrypted **at rest**.

The product asks users to pour in their real reason for a trade. The trust we
owe back is that those words are not sitting in plaintext in the database, where
a leaked dump / backup / read-access contractor could read them. These tests
demonstrate the guarantee rather than assert it in a policy page:

    1. what is written to the DB column is ciphertext (version-marked), and the
       user's actual words do NOT appear in the stored bytes;
    2. the ORM still returns plaintext to the owning request (the mirror works);
    3. legacy plaintext rows (written before encryption) still read back fine —
       so the rollout needs no data migration.

Tier note: this is encrypt-at-rest with a *server-held* key. It defeats a DB
leak, not a malicious operator — true "we cannot read it" needs a user-held key
(separate product decision; would also stop the server-side mirror). See
services.crypto_service.EncryptedText.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from extensions import db
from models import PreTradeReflection
from services.pre_trade.friction import start_cooldown, storage_proof


# A distinctive phrase we can search for in the raw DB bytes. If encryption
# works, this Korean string must NOT appear in what is stored on disk.
SECRET_RATIONALE = (
    "사실 어제 텔레그램 리딩방에서 추천받아서 FOMO 로 들어가는 거다. "
    "무섭지만 안 사면 뒤쳐질 것 같아서 결국 매수 버튼을 누른다."
)
SECRET_DEVIL = "이미 30% 오른 종목을 지금 따라 사는 게 합리적인가?"


def _raw_column(reflection_id: int, column: str) -> str | None:
    """Read the column with textual SQL so the EncryptedText TypeDecorator is
    bypassed — i.e. exactly the bytes that live on disk."""
    row = db.session.execute(
        text(f"SELECT {column} FROM pre_trade_reflections WHERE id = :id"),
        {"id": reflection_id},
    ).first()
    return row[0] if row else None


def test_rationale_is_ciphertext_on_disk(app, make_user):
    """The stored bytes are version-marked ciphertext, and the user's words
    are nowhere in them."""
    user = make_user(email="enc1@test.com")
    with app.app_context():
        out = start_cooldown(
            user_id=user["id"],
            ticker="AAPL",
            side="BUY",
            shares=5,
            rationale=SECRET_RATIONALE,
            devil_advocate=SECRET_DEVIL,
        )
        rid = out["id"]

        raw_rationale = _raw_column(rid, "rationale")
        raw_devil = _raw_column(rid, "devil_advocate_seen")

        # 1. Stored value is our ciphertext, not plaintext.
        assert raw_rationale is not None
        assert raw_rationale.startswith("pqenc:1:")
        assert raw_devil.startswith("pqenc:1:")

        # 2. The actual words do NOT appear in the stored bytes (the proof a
        #    DB leak reads nothing). Check a few distinctive fragments.
        for fragment in ("리딩방", "FOMO", "매수 버튼", "텔레그램"):
            assert fragment not in raw_rationale
        assert "합리적인가" not in raw_devil


def test_orm_returns_plaintext(app, make_user):
    """The owning request still gets plaintext back — the mirror keeps working.

    Forces a real DB round-trip (expire_all) so the value comes through the
    TypeDecorator, not the identity-map copy held since insert."""
    user = make_user(email="enc2@test.com")
    with app.app_context():
        out = start_cooldown(
            user_id=user["id"],
            ticker="MSFT",
            side="BUY",
            shares=3,
            rationale=SECRET_RATIONALE,
            devil_advocate=SECRET_DEVIL,
        )
        rid = out["id"]

        db.session.expire_all()
        row = db.session.get(PreTradeReflection, rid)
        assert row.rationale == SECRET_RATIONALE
        assert row.devil_advocate_seen == SECRET_DEVIL
        # to_dict (what the API serialises to the owner) is plaintext too.
        assert row.to_dict()["rationale"] == SECRET_RATIONALE


def test_nullable_devil_advocate_roundtrips_none(app, make_user):
    """A null free-text column stays null through encrypt/decrypt."""
    user = make_user(email="enc3@test.com")
    with app.app_context():
        out = start_cooldown(
            user_id=user["id"],
            ticker="TSLA",
            side="SELL",
            shares=2,
            rationale=SECRET_RATIONALE,
            devil_advocate=None,
        )
        db.session.expire_all()
        row = db.session.get(PreTradeReflection, out["id"])
        assert row.devil_advocate_seen is None
        assert _raw_column(out["id"], "devil_advocate_seen") is None


def test_legacy_plaintext_row_still_reads(app, make_user):
    """A row written before encryption (no version marker) reads back as-is —
    so enabling encryption needs no backfill migration."""
    user = make_user(email="enc4@test.com")
    with app.app_context():
        out = start_cooldown(
            user_id=user["id"],
            ticker="NVDA",
            side="BUY",
            shares=1,
            rationale=SECRET_RATIONALE,
        )
        rid = out["id"]

        # Simulate a legacy plaintext row by overwriting the column directly.
        legacy = "옛날에 평문으로 저장된 매매 이유 메모"
        db.session.execute(
            text(
                "UPDATE pre_trade_reflections SET rationale = :v WHERE id = :id"
            ),
            {"v": legacy, "id": rid},
        )
        db.session.commit()
        db.session.expire_all()

        row = db.session.get(PreTradeReflection, rid)
        # No marker → returned verbatim, no decrypt attempt, no crash.
        assert row.rationale == legacy


# ─────────────────────────────────────────────────────────────────────
# storage_proof — the "show, don't tell" trust artifact
# ─────────────────────────────────────────────────────────────────────

def test_storage_proof_shows_both_forms(app, make_user):
    """The user can witness, on their own row, plaintext vs the stored
    ciphertext — and the stored form really is the encrypted one."""
    user = make_user(email="proof1@test.com")
    with app.app_context():
        out = start_cooldown(
            user_id=user["id"],
            ticker="AAPL",
            side="BUY",
            shares=5,
            rationale=SECRET_RATIONALE,
        )
        proof = storage_proof(out["id"], user["id"])

        assert proof["encrypted"] is True
        assert proof["rationale_plaintext"] == SECRET_RATIONALE
        assert proof["rationale_stored"].startswith("pqenc:1:")
        # The stored form must not contain the user's actual words.
        assert "리딩방" not in proof["rationale_stored"]
        # Honest copy — must NOT overclaim "we can't read it" at this tier.
        assert "종단간" in proof["note_kr"]


def test_storage_proof_enforces_ownership(app, make_user):
    """Another user cannot pull the proof for a row they don't own."""
    owner = make_user(email="proof_owner@test.com")
    intruder = make_user(email="proof_intruder@test.com")
    with app.app_context():
        out = start_cooldown(
            user_id=owner["id"],
            ticker="AAPL",
            side="BUY",
            shares=5,
            rationale=SECRET_RATIONALE,
        )
        with pytest.raises(LookupError):
            storage_proof(out["id"], intruder["id"])
