"""Proof tests — the rest of the user's free-text is encrypted **at rest**.

Extends ``test_encrypted_reflection.py`` (which covers PreTradeReflection) to
every column moved to ``EncryptedText`` in the 2026-06-02 data-storage-trust
build:

    positions.thesis / positions.thesis_reason
    watchlist.note
    position_dd_checks.note
    weekly_pulse.worry / weekly_pulse.learn
    behavioral_scores.notes
    inquiries.body / inquiries.admin_reply
    ai_twin_weekly_reports.rationale_summary

For each we demonstrate (not merely assert in a policy page):
    1. what is written to the DB column is version-marked ciphertext, and the
       user's actual words do NOT appear in the stored bytes;
    2. the ORM still returns plaintext to the owning request;
    3. multi-byte free-text longer than the old VARCHAR(500) cap round-trips
       (the reason those columns were widened to TEXT).

Tier note: encrypt-at-rest with a *server-held* key — defeats a DB leak, not a
malicious operator. See services.crypto_service.EncryptedText.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import text

from extensions import db
from models import (
    Position,
    Watchlist,
    PositionDDCheck,
    WeeklyPulse,
    BehavioralScore,
    Inquiry,
    AITwinWeeklyReport,
)

# Distinctive phrases that must NOT appear in the stored bytes if encryption
# works. Korean so they are unambiguous fragments to search the raw column for.
SECRET = "사실 텔레그램 리딩방에서 추천받아 FOMO 로 들어간다. 무섭다."
SECRET_FRAGMENTS = ("리딩방", "FOMO", "무섭다")


def _raw(table: str, column: str, row_id: int):
    """Read a column via textual SQL — bypasses the EncryptedText decoder, so
    we see exactly the bytes on disk."""
    row = db.session.execute(
        text(f"SELECT {column} FROM {table} WHERE id = :id"),
        {"id": row_id},
    ).first()
    return row[0] if row else None


def _assert_encrypted(table: str, column: str, row_id: int):
    raw = _raw(table, column, row_id)
    assert raw is not None, f"{table}.{column} is NULL"
    assert raw.startswith("pqenc:"), f"{table}.{column} not ciphertext: {raw[:24]!r}"
    for frag in SECRET_FRAGMENTS:
        assert frag not in raw, f"plaintext fragment {frag!r} leaked into {table}.{column}"


def test_position_thesis_encrypted(app, make_user):
    user = make_user(email="enc-pos@test.com")
    with app.app_context():
        p = Position(
            user_id=user["id"], ticker="AAPL", shares=5, avg_cost=190.0,
            thesis=SECRET, thesis_reason=SECRET,
        )
        db.session.add(p)
        db.session.commit()
        pid = p.id
        db.session.expire_all()

        _assert_encrypted("positions", "thesis", pid)
        _assert_encrypted("positions", "thesis_reason", pid)
        row = db.session.get(Position, pid)
        assert row.thesis == SECRET
        assert row.thesis_reason == SECRET


def test_watchlist_note_encrypted(app, make_user):
    user = make_user(email="enc-wl@test.com")
    with app.app_context():
        w = Watchlist(user_id=user["id"], ticker="MSFT", note=SECRET)
        db.session.add(w)
        db.session.commit()
        wid = w.id
        db.session.expire_all()

        _assert_encrypted("watchlist", "note", wid)
        assert db.session.get(Watchlist, wid).note == SECRET


def test_dd_check_note_encrypted(app, make_user):
    user = make_user(email="enc-dd@test.com")
    with app.app_context():
        p = Position(user_id=user["id"], ticker="NVDA", shares=1, avg_cost=900.0)
        db.session.add(p)
        db.session.commit()
        dd = PositionDDCheck(user_id=user["id"], position_id=p.id, note=SECRET)
        db.session.add(dd)
        db.session.commit()
        ddid = dd.id
        db.session.expire_all()

        _assert_encrypted("position_dd_checks", "note", ddid)
        assert db.session.get(PositionDDCheck, ddid).note == SECRET


def test_weekly_pulse_encrypted(app, make_user):
    user = make_user(email="enc-wp@test.com")
    with app.app_context():
        wp = WeeklyPulse(
            user_id=user["id"], mood=2, confidence=3, worry=SECRET, learn=SECRET,
        )
        db.session.add(wp)
        db.session.commit()
        wpid = wp.id
        db.session.expire_all()

        _assert_encrypted("weekly_pulse", "worry", wpid)
        _assert_encrypted("weekly_pulse", "learn", wpid)
        row = db.session.get(WeeklyPulse, wpid)
        assert row.worry == SECRET
        assert row.learn == SECRET
        assert row.to_dict()["worry"] == SECRET


def test_behavioral_notes_encrypted(app, make_user):
    user = make_user(email="enc-bs@test.com")
    with app.app_context():
        bs = BehavioralScore(
            user_id=user["id"], week_ending=date(2026, 1, 4),
            overall_score=72, sub_scores="{}", notes=SECRET,
        )
        db.session.add(bs)
        db.session.commit()
        bsid = bs.id
        db.session.expire_all()

        _assert_encrypted("behavioral_scores", "notes", bsid)
        assert db.session.get(BehavioralScore, bsid).notes == SECRET


def test_inquiry_body_encrypted(app, make_user):
    user = make_user(email="enc-iq@test.com")
    with app.app_context():
        iq = Inquiry(
            user_id=user["id"], category="other", subject="문의",
            body=SECRET, admin_reply=SECRET,
        )
        db.session.add(iq)
        db.session.commit()
        iqid = iq.id
        db.session.expire_all()

        _assert_encrypted("inquiries", "body", iqid)
        _assert_encrypted("inquiries", "admin_reply", iqid)
        row = db.session.get(Inquiry, iqid)
        assert row.body == SECRET
        assert row.admin_reply == SECRET
        # subject stays plaintext (short title, operator-searchable) — by design.
        assert _raw("inquiries", "subject", iqid) == "문의"


def test_twin_weekly_summary_encrypted(app, make_user):
    user = make_user(email="enc-twin@test.com")
    with app.app_context():
        r = AITwinWeeklyReport(
            user_id=user["id"], week_ending=date(2026, 1, 11),
            rationale_summary=SECRET,
        )
        db.session.add(r)
        db.session.commit()
        rid = r.id
        db.session.expire_all()

        _assert_encrypted("ai_twin_weekly_reports", "rationale_summary", rid)
        assert db.session.get(AITwinWeeklyReport, rid).rationale_summary == SECRET


def test_long_multibyte_text_roundtrips(app, make_user):
    """A free-text value far longer than the old VARCHAR(500) cap round-trips —
    the reason those columns were widened to TEXT. 700 Korean chars ≈ 2.1 KB of
    UTF-8, whose ciphertext is well over 500 chars."""
    user = make_user(email="enc-long@test.com")
    long_text = "과잉거래로 매년 돈을 잃는 나의 패턴을 기록한다. " * 30  # ~700+ chars
    assert len(long_text) > 500
    with app.app_context():
        wp = WeeklyPulse(
            user_id=user["id"], mood=1, confidence=1, worry=long_text, learn="",
        )
        db.session.add(wp)
        db.session.commit()
        wpid = wp.id
        db.session.expire_all()

        stored = _raw("weekly_pulse", "worry", wpid)
        assert stored.startswith("pqenc:")
        assert len(stored) > 500
        assert db.session.get(WeeklyPulse, wpid).worry == long_text


def test_legacy_plaintext_note_still_reads(app, make_user):
    """A row written before encryption (no version marker) reads back verbatim —
    so enabling encryption on these columns needs no backfill migration."""
    user = make_user(email="enc-legacy@test.com")
    with app.app_context():
        w = Watchlist(user_id=user["id"], ticker="TSLA", note="placeholder")
        db.session.add(w)
        db.session.commit()
        wid = w.id
        legacy = "옛날에 평문으로 저장된 관찰 메모"
        db.session.execute(
            text("UPDATE watchlist SET note = :v WHERE id = :id"),
            {"v": legacy, "id": wid},
        )
        db.session.commit()
        db.session.expire_all()
        assert db.session.get(Watchlist, wid).note == legacy
