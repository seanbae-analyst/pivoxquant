"""Tests for Feature 6 — Pre-Trade Friction.

Covers the service-layer invariants (rationale floor, cooldown
duration, auto-extend triggers, ownership check) and the route-layer
contract (CSRF, status codes, observational disclaimer).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from extensions import db
from models import (
    PreTradeReflection,
    DEFAULT_COOLDOWN_SECONDS,
    EXTENDED_COOLDOWN_SECONDS,
    MIN_RATIONALE_CHARS,
)
from services.pre_trade.friction import (
    cancel,
    check_status,
    list_reflections,
    proceed,
    start_cooldown,
)


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

LONG_RATIONALE = (
    "포지션 사이즈가 작아도 손절 룰을 어기지 않기 위해 미리 reasoning 을 적어둔다. "
    "충분한 길이의 자기 reflection 메모로 사용한다."
)


def _make_user(make_user, email="pt@test.com"):
    return make_user(email=email)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ─────────────────────────────────────────────────────────────────────
# Service layer
# ─────────────────────────────────────────────────────────────────────

def test_start_creates_reflection(app, make_user):
    user = _make_user(make_user)
    with app.app_context():
        out = start_cooldown(
            user_id=user["id"],
            ticker="AAPL",
            side="BUY",
            shares=10,
            rationale=LONG_RATIONALE,
        )
        assert out["intended_ticker"] == "AAPL"
        assert out["intended_side"] == "BUY"
        # 2026-05-22: cooldown removed (CEO "2분 없애") → reflection is
        # immediately ready (seconds_remaining 0, proceed permitted).
        assert out["status"] == "ready"
        assert out["seconds_remaining"] == 0
        # Row persisted.
        row = db.session.get(PreTradeReflection, out["id"])
        assert row is not None
        assert int(row.user_id) == int(user["id"])


def test_rationale_too_short_rejects(app, make_user):
    user = _make_user(make_user, email="pt-short@test.com")
    with app.app_context():
        with pytest.raises(ValueError, match="rationale"):
            start_cooldown(
                user_id=user["id"],
                ticker="AAPL",
                side="BUY",
                shares=1,
                rationale="too short",
            )


def test_cooldown_default_is_zero(app, make_user):
    """2026-05-22: cooldown removed → default duration is 0s (immediately ready)."""
    user = _make_user(make_user, email="pt-2min@test.com")
    with app.app_context(), patch(
        "services.pre_trade.friction._should_extend_cooldown",
        return_value=None,
    ):
        out = start_cooldown(
            user_id=user["id"],
            ticker="AAPL",
            side="BUY",
            shares=1,
            rationale=LONG_RATIONALE,
        )
        assert DEFAULT_COOLDOWN_SECONDS == 0
        assert out["seconds_remaining"] == 0
        assert out["status"] == "ready"
        assert out["auto_extended_reason"] is None


def test_fomc_extension_to_5min(app, make_user):
    """FOMC trigger extends to 5 minutes and stamps the reason."""
    user = _make_user(make_user, email="pt-fomc@test.com")
    with app.app_context(), patch(
        "services.pre_trade.friction._fomc_window_active", return_value=True
    ), patch(
        "services.pre_trade.friction._read_vix", return_value=None
    ), patch(
        "services.pre_trade.friction._ticker_moved_more_than", return_value=False
    ):
        out = start_cooldown(
            user_id=user["id"],
            ticker="AAPL",
            side="BUY",
            shares=1,
            rationale=LONG_RATIONALE,
        )
        # Reason is still stamped for the journal, but the duration is 0
        # (cooldown removed 2026-05-22) so the user is not made to wait.
        assert out["auto_extended_reason"] == "fomc_30min"
        assert EXTENDED_COOLDOWN_SECONDS == 0
        assert out["seconds_remaining"] == 0


def test_high_vix_extension(app, make_user):
    """VIX > 30 extends to 5 minutes."""
    user = _make_user(make_user, email="pt-vix@test.com")
    with app.app_context(), patch(
        "services.pre_trade.friction._fomc_window_active", return_value=False
    ), patch(
        "services.pre_trade.friction._ticker_moved_more_than", return_value=False
    ):
        out = start_cooldown(
            user_id=user["id"],
            ticker="AAPL",
            side="BUY",
            shares=1,
            rationale=LONG_RATIONALE,
            market_volatility=35.0,
        )
        assert out["auto_extended_reason"] == "high_vix"
        assert out["seconds_remaining"] == 0


def test_proceed_immediately_succeeds(app, make_user):
    """2026-05-22: cooldown removed → proceed is permitted right after start
    (no enforced wait). Previously this raised "cooldown has not elapsed".
    """
    user = _make_user(make_user, email="pt-prep@test.com")
    with app.app_context():
        out = start_cooldown(
            user_id=user["id"],
            ticker="AAPL",
            side="BUY",
            shares=1,
            rationale=LONG_RATIONALE,
        )
        assert out["seconds_remaining"] == 0
        result = proceed(out["id"], user["id"])
        assert result["status"] == "proceeded"
        assert result["proceeded_at"] is not None


def test_proceed_after_cooldown_succeeds(app, make_user):
    user = _make_user(make_user, email="pt-after@test.com")
    with app.app_context():
        out = start_cooldown(
            user_id=user["id"],
            ticker="AAPL",
            side="BUY",
            shares=1,
            rationale=LONG_RATIONALE,
        )
        # Fast-forward by rewriting cooldown_ends_at backwards.
        row = db.session.get(PreTradeReflection, out["id"])
        row.cooldown_ends_at = _utc_now() - timedelta(seconds=1)
        db.session.commit()

        result = proceed(out["id"], user["id"])
        assert result["status"] == "proceeded"
        assert result["proceeded_at"] is not None


def test_cancel_works(app, make_user):
    user = _make_user(make_user, email="pt-cancel@test.com")
    with app.app_context():
        out = start_cooldown(
            user_id=user["id"],
            ticker="AAPL",
            side="BUY",
            shares=1,
            rationale=LONG_RATIONALE,
        )
        result = cancel(out["id"], user["id"])
        assert result["status"] == "cancelled"
        assert result["cancelled_at"] is not None


def test_other_user_cannot_proceed(app, make_user):
    """Owner-isolation: a foreign user_id sees a LookupError, not the row."""
    owner = _make_user(make_user, email="owner@test.com")
    intruder = _make_user(make_user, email="intruder@test.com")
    with app.app_context():
        out = start_cooldown(
            user_id=owner["id"],
            ticker="AAPL",
            side="BUY",
            shares=1,
            rationale=LONG_RATIONALE,
        )
        # Make cooldown elapsed so the failure is purely owner-mismatch.
        row = db.session.get(PreTradeReflection, out["id"])
        row.cooldown_ends_at = _utc_now() - timedelta(seconds=1)
        db.session.commit()
        with pytest.raises(LookupError):
            proceed(out["id"], intruder["id"])
        with pytest.raises(LookupError):
            check_status(out["id"], intruder["id"])


# ─────────────────────────────────────────────────────────────────────
# List / Journal feed
# ─────────────────────────────────────────────────────────────────────

def test_list_newest_first_and_user_isolation(app, make_user):
    """Journal feed: newest-first ordering + zero cross-user leakage."""
    owner = _make_user(make_user, email="list-owner@test.com")
    other = _make_user(make_user, email="list-other@test.com")
    with app.app_context():
        # Owner creates two reflections; rewrite created_at so ordering
        # is deterministic regardless of insert clock resolution.
        first = start_cooldown(
            user_id=owner["id"], ticker="AAPL", side="BUY", shares=1,
            rationale=LONG_RATIONALE,
        )
        second = start_cooldown(
            user_id=owner["id"], ticker="MSFT", side="SELL", shares=2,
            rationale=LONG_RATIONALE,
        )
        base = _utc_now()
        db.session.get(PreTradeReflection, first["id"]).created_at = base - timedelta(minutes=5)
        db.session.get(PreTradeReflection, second["id"]).created_at = base
        db.session.commit()

        # A foreign user's reflection that must NEVER appear.
        start_cooldown(
            user_id=other["id"], ticker="TSLA", side="BUY", shares=3,
            rationale=LONG_RATIONALE,
        )

        rows = list_reflections(owner["id"])
        # Only the owner's two rows.
        assert len(rows) == 2
        assert all(r["intended_ticker"] in ("AAPL", "MSFT") for r in rows)
        assert "TSLA" not in [r["intended_ticker"] for r in rows]
        # Newest (MSFT, created_at=base) first.
        assert rows[0]["intended_ticker"] == "MSFT"
        assert rows[1]["intended_ticker"] == "AAPL"
        # Every owned row belongs to the owner (status field present).
        assert all(r["status"] in ("pending", "ready", "proceeded", "cancelled") for r in rows)


def test_list_limit_clamped(app, make_user):
    """?limit is clamped to MAX_LIST_LIMIT and malformed values fall back."""
    from services.pre_trade.friction import MAX_LIST_LIMIT

    user = _make_user(make_user, email="list-limit@test.com")
    with app.app_context():
        for i in range(3):
            start_cooldown(
                user_id=user["id"], ticker="AAPL", side="BUY", shares=1,
                rationale=LONG_RATIONALE,
            )
        # Over-large request is clamped (no error) and bounded.
        rows = list_reflections(user["id"], limit=99999)
        assert len(rows) == 3  # only 3 exist; clamp <= MAX_LIST_LIMIT
        assert MAX_LIST_LIMIT == 200
        # Malformed limit falls back to default, still returns rows.
        rows2 = list_reflections(user["id"], limit="not-a-number")
        assert len(rows2) == 3


def test_route_list_returns_feed(client, auth_user):
    """GET /api/pre-trade/list returns the envelope with a reflections array."""
    client.post("/api/pre-trade/start", json={
        "ticker": "AAPL", "side": "BUY", "shares": 1, "rationale": LONG_RATIONALE,
    })
    resp = client.get("/api/pre-trade/list")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert "disclaimer" in body
    assert isinstance(body["reflections"], list)
    assert len(body["reflections"]) >= 1
    assert body["reflections"][0]["intended_ticker"] == "AAPL"
    assert "status" in body["reflections"][0]


def test_route_list_excludes_other_users(client, app, make_user, auth_user):
    """The logged-in user's feed never contains a foreign user's row."""
    other = _make_user(make_user, email="feed-intruder@test.com")
    with app.app_context():
        start_cooldown(
            user_id=other["id"], ticker="NVDA", side="BUY", shares=1,
            rationale=LONG_RATIONALE,
        )
    resp = client.get("/api/pre-trade/list")
    assert resp.status_code == 200
    tickers = [r["intended_ticker"] for r in resp.get_json()["reflections"]]
    assert "NVDA" not in tickers


# ─────────────────────────────────────────────────────────────────────
# Route layer
# ─────────────────────────────────────────────────────────────────────

def test_route_start_returns_disclaimer(client, auth_user):
    resp = client.post("/api/pre-trade/start", json={
        "ticker": "AAPL",
        "side": "BUY",
        "shares": 10,
        "rationale": LONG_RATIONALE,
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert "disclaimer" in body
    assert "권유가 아닙니다" in body["disclaimer"]
    # 2026-05-22: cooldown removed → reflection is immediately ready.
    assert body["reflection"]["status"] == "ready"


def test_route_csrf_required(raw_client, make_user):
    """POST without the CSRF header is rejected by init_security."""
    u = make_user(email="csrf@pretrade.test", password="x")
    # Log in via raw client (no CSRF auto-attach).
    login = raw_client.post("/api/auth/login", json={
        "email": u["email"], "password": u["password"]
    })
    assert login.status_code == 200, f"login failed: {login.data!r}"
    resp = raw_client.post("/api/pre-trade/start", json={
        "ticker": "AAPL",
        "side": "BUY",
        "shares": 1,
        "rationale": LONG_RATIONALE,
    })
    # Security middleware returns 403 on missing/mismatched CSRF.
    assert resp.status_code in (400, 401, 403), (
        "Expected CSRF rejection; got %s" % resp.status_code
    )


def test_route_proceed_blocks_other_user(client, app, make_user, auth_user):
    """Even with valid auth, a foreign id resolves to 404 not the row."""
    # auth_user is logged in; create the reflection under a *different* user.
    other = _make_user(make_user, email="other@test.com")
    with app.app_context():
        out = start_cooldown(
            user_id=other["id"],
            ticker="AAPL",
            side="BUY",
            shares=1,
            rationale=LONG_RATIONALE,
        )
    resp = client.post(f"/api/pre-trade/{out['id']}/proceed")
    assert resp.status_code == 404


def test_route_error_message_truncated_to_200(client, app, make_user, auth_user):
    """OPS#9: api_error ``en`` from a service ValueError is capped at 200 chars.

    The route emits ``str(exc)[:200]`` so an unexpectedly long exception
    message can never balloon the error envelope. We force a >200-char
    ValueError out of the service layer and assert the route truncates it.
    """
    # Create a reflection owned by the logged-in user.
    with app.app_context():
        row = start_cooldown(
            user_id=auth_user["id"],
            ticker="AAPL",
            side="BUY",
            shares=1,
            rationale=LONG_RATIONALE,
        )
    long_msg = "X" * 500
    with patch(
        "routes.pre_trade.proceed_reflection",
        side_effect=ValueError(long_msg),
    ):
        resp = client.post(f"/api/pre-trade/{row['id']}/proceed")
    assert resp.status_code == 409
    body = resp.get_json()
    # en value lands in the "error" key (services.error_responses.api_error).
    assert len(body["error"]) == 200, (
        "error message must be truncated to 200 chars, got %d" % len(body["error"])
    )
    assert body["error"] == "X" * 200


def test_rationale_min_chars_constant_holds():
    """Pin the rationale floor — any change must come with explicit migration.

    2026-05-22: lowered 50 → 10 per CEO ("50자 너무 많아 10자"). Frontend
    pre-trade-friction-core.tsx MIN_RATIONALE_CHARS must match.
    """
    assert MIN_RATIONALE_CHARS == 10


# ─────────────────────────────────────────────────────────────────────
# Ticker normalization (2026-05-21 fix)
# ─────────────────────────────────────────────────────────────────────
#
# ``start_cooldown`` now runs ``normalize_ticker()`` before persisting so a
# bare KR code lands as the registry-canonical form (e.g. "035760.KQ")
# instead of a naked number the Journal would render without a company name.

def test_start_normalizes_bare_kr_code(app, make_user):
    """A bare "035760" is stored as its normalized "035760.KQ" form."""
    from services.ticker_normalizer import normalize_ticker

    expected = normalize_ticker("035760")
    # Guard: the fixture input must actually be transformable, else the test
    # would pass vacuously.
    assert expected != "035760", "normalize_ticker should canonicalize the bare code"
    assert expected.endswith(".KQ") or expected.endswith(".KS")

    user = _make_user(make_user, email="pt-normalize@test.com")
    with app.app_context():
        out = start_cooldown(
            user_id=user["id"],
            ticker="035760",
            side="BUY",
            shares=1,
            rationale=LONG_RATIONALE,
        )
        assert out["intended_ticker"] == expected
        row = db.session.get(PreTradeReflection, out["id"])
        assert row.intended_ticker == expected
        # Pin: the naked code must not survive into storage.
        assert row.intended_ticker != "035760"


def test_start_us_ticker_uppercased_unchanged(app, make_user):
    """A US ticker normalizes to upper-case and is otherwise unchanged."""
    user = _make_user(make_user, email="pt-us-norm@test.com")
    with app.app_context():
        out = start_cooldown(
            user_id=user["id"],
            ticker="aapl",
            side="BUY",
            shares=1,
            rationale=LONG_RATIONALE,
        )
        assert out["intended_ticker"] == "AAPL"


# ─────────────────────────────────────────────────────────────────────
# Numeric input hardening (2026-06-09) — a crafted inf / NaN / huge value
# must surface as a clean ValueError (→ 400), never reach the DB where
# Postgres NUMERIC would raise DataError (→ uncaught 500) or persist a NaN.
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan"), 1e12])
def test_start_rejects_non_finite_or_huge_shares(app, make_user, bad):
    user = _make_user(make_user, email=f"pt-shares-{bad}@test.com")
    with app.app_context():
        with pytest.raises(ValueError, match="shares"):
            start_cooldown(
                user_id=user["id"],
                ticker="AAPL",
                side="BUY",
                shares=bad,
                rationale=LONG_RATIONALE,
            )


def test_start_still_accepts_normal_and_zero_shares(app, make_user):
    """The hardening must not reject legitimate values (0 stays allowed)."""
    user = _make_user(make_user, email="pt-shares-ok@test.com")
    with app.app_context():
        for s in (0, 1, 1000.5, 1e9):
            out = start_cooldown(
                user_id=user["id"],
                ticker="AAPL",
                side="BUY",
                shares=s,
                rationale=LONG_RATIONALE,
            )
            assert out["id"]


@pytest.mark.parametrize("bad_vol", [float("inf"), float("nan"), 1e9, -5.0])
def test_start_drops_bad_volatility_instead_of_failing(app, make_user, bad_vol):
    """market_volatility is optional telemetry: a bad snapshot is dropped to
    None, not a 500 — the reflection still writes."""
    user = _make_user(make_user, email=f"pt-vol-{bad_vol}@test.com")
    with app.app_context(), patch(
        "services.pre_trade.friction._should_extend_cooldown", return_value=None
    ):
        out = start_cooldown(
            user_id=user["id"],
            ticker="AAPL",
            side="BUY",
            shares=1,
            rationale=LONG_RATIONALE,
            market_volatility=bad_vol,
        )
        row = db.session.get(PreTradeReflection, out["id"])
        assert row is not None
        assert row.market_volatility_at_request is None


def test_start_keeps_valid_volatility(app, make_user):
    """A sane VIX snapshot is preserved."""
    user = _make_user(make_user, email="pt-vol-ok@test.com")
    with app.app_context(), patch(
        "services.pre_trade.friction._should_extend_cooldown", return_value=None
    ):
        out = start_cooldown(
            user_id=user["id"],
            ticker="AAPL",
            side="BUY",
            shares=1,
            rationale=LONG_RATIONALE,
            market_volatility=22.5,
        )
        row = db.session.get(PreTradeReflection, out["id"])
        assert float(row.market_volatility_at_request) == 22.5


# ─────────────────────────────────────────────────────────────────────
# Observed-context snapshot (record-as-spine Phase 2, 2026-06-10) —
# "그때 무엇을 보고 있었나" is captured best-effort at /start. A collection
# failure must never block the reflection write, and only the legal
# observation fields (signal label / score / sector / vix / 1h move) may
# be copied — never rec_* / take_profit / stop_loss (§17).
# ─────────────────────────────────────────────────────────────────────

def test_start_captures_observed_context_from_signal_cache(app, make_user):
    import json as _json
    from models import SignalCache

    user = _make_user(make_user, email="pt-ctx@test.com")
    with app.app_context(), patch(
        "services.pre_trade.friction._should_extend_cooldown", return_value=None
    ):
        db.session.add(SignalCache(
            ticker="AAPL",
            data_json=_json.dumps({
                "signal": "POSITIVE", "score": 71.5, "sector": "Technology",
                # Directive fields that must NOT be copied (§17):
                "rec_shares": 12, "take_profit": 250.0, "stop_loss": 180.0,
            }),
        ))
        db.session.commit()

        out = start_cooldown(
            user_id=user["id"],
            ticker="AAPL",
            side="BUY",
            shares=1,
            rationale=LONG_RATIONALE,
            market_volatility=18.2,
        )
        ctx = out["observed_context"]
        assert ctx is not None
        assert ctx["signal"] == "POSITIVE"
        assert ctx["score"] == 71.5
        assert ctx["sector"] == "Technology"
        assert ctx["vix"] == 18.2
        assert "captured_at" in ctx
        # §17 — no directive field may leak into the record.
        for banned in ("rec_shares", "take_profit", "stop_loss"):
            assert banned not in ctx


def test_start_survives_observed_context_failure(app, make_user):
    """Broken lookups inside the collection must not block the write.

    Pins the contract that ``_collect_observed_context`` wraps EVERY
    dependency: a corrupt SignalCache blob (json.loads raises) and a broken
    vix reader yield a null context — never an exception into /start."""
    import json as _json
    from models import SignalCache

    user = _make_user(make_user, email="pt-ctx-fail@test.com")
    with app.app_context(), patch(
        "services.pre_trade.friction._should_extend_cooldown", return_value=None
    ), patch(
        "services.pre_trade.friction._read_vix", side_effect=RuntimeError("boom"),
    ):
        db.session.add(SignalCache(ticker="BROKEN", data_json="{not json"))
        db.session.commit()

        out = start_cooldown(
            user_id=user["id"], ticker="BROKEN", side="BUY",
            shares=1, rationale=LONG_RATIONALE,
        )
        assert out["id"]
        assert out["observed_context"] is None


def test_start_without_cache_yields_null_context_but_writes(app, make_user):
    user = _make_user(make_user, email="pt-ctx-none@test.com")
    with app.app_context(), patch(
        "services.pre_trade.friction._should_extend_cooldown", return_value=None
    ):
        out = start_cooldown(
            user_id=user["id"],
            ticker="ZZZNOCACHE",
            side="BUY",
            shares=1,
            rationale=LONG_RATIONALE,
        )
        assert out["id"]
        # No cache row, no vix passed, no realtime service in tests → null.
        assert out["observed_context"] is None
