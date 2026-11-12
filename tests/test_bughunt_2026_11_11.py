"""Regressions from the 2026-11-11 simulation bug hunt (3 areas, in-process)."""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from extensions import db
from models import PreTradeReflection, TradeHistory


@pytest.fixture
def no_cache():
    with patch("routes.portfolio.cache_service.cache_ticker"):
        yield


# ── scalar / wrong-typed JSON bodies were 500s ───────────────────────

@pytest.mark.parametrize("url", ["/api/portfolio/positions", "/api/portfolio/trades",
                                 "/api/support/inquiries", "/api/auth/delete-cancel"])
@pytest.mark.parametrize("body", [5, "x", [1]])
def test_scalar_body_is_4xx(client, auth_user, url, body):
    assert client.post(url, json=body).status_code < 500


def test_login_with_non_string_fields_is_4xx(client):
    assert client.post("/api/auth/login", json=[1]).status_code < 500
    assert client.post("/api/auth/login", json={"email": 123, "password": 1}).status_code < 500


def test_position_symbol_int_is_400(client, auth_user, no_cache):
    assert client.post("/api/portfolio/positions",
                       json={"symbol": 123, "quantity": 1, "price": 1}).status_code == 400


# ── POST /positions symbol validation ────────────────────────────────

@pytest.mark.parametrize("bad", ["<script>", "AAPL; DROP", "삼성전자", "$AAPL"])
def test_position_rejects_junk_ticker(client, auth_user, no_cache, bad):
    r = client.post("/api/portfolio/positions", json={"symbol": bad, "quantity": 1, "price": 10})
    assert r.status_code == 400 and r.get_json()["code"] == "INVALID_TICKER"


# ── a tiny sell kept the remainder ───────────────────────────────────

def test_tiny_sell_does_not_close_the_position(client, auth_user, no_cache):
    client.post("/api/portfolio/positions", json={"symbol": "MSFT", "quantity": 0.0002, "price": 100})
    rows = client.get("/api/portfolio/positions").get_json()
    rows = rows if isinstance(rows, list) else rows.get("positions") or rows.get("data")
    pid = next(x["id"] for x in rows if x["ticker"] == "MSFT")
    r = client.post("/api/portfolio/trades",
                    json={"position_id": pid, "action": "sell", "quantity": 0.0001, "price": 100})
    assert r.status_code == 200 and not r.get_json().get("closed")


# ── trade currency from the ticker suffix, not a cache blob ──────────

def test_trade_currency_ignores_poisoned_cache(client, auth_user, no_cache, app):
    client.post("/api/portfolio/positions", json={"symbol": "AAPL", "quantity": 5, "price": 100})
    rows = client.get("/api/portfolio/positions").get_json()
    rows = rows if isinstance(rows, list) else rows.get("positions") or rows.get("data")
    pid = next(x["id"] for x in rows if x["ticker"] == "AAPL")
    with patch("routes.portfolio.cache_service.safe_cache_blob",
               return_value={"currency": "KRW", "is_korean": True}):
        r = client.post("/api/portfolio/trades",
                        json={"position_id": pid, "action": "sell", "quantity": 1, "price": 120})
    assert r.status_code == 200
    with app.app_context():
        sell = TradeHistory.query.filter_by(user_id=auth_user["id"], action="SELL").one()
        assert sell.currency == "USD"


# ── the holding seed carries purchase_date (FIFO lot order) ──────────

def test_backdated_adds_after_seed_read_as_below_average(client, auth_user, no_cache):
    now = datetime.utcnow()
    client.post("/api/portfolio/positions", json={
        "symbol": "AAPL", "quantity": 10, "price": 100,
        "purchase_date": (now - timedelta(days=90)).strftime("%Y-%m-%d")})
    rows = client.get("/api/portfolio/positions").get_json()
    rows = rows if isinstance(rows, list) else rows.get("positions") or rows.get("data")
    pid = next(x["id"] for x in rows if x["ticker"] == "AAPL")
    for i in range(5):
        client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "buy", "quantity": 1, "price": 95,
            "date": (now - timedelta(days=40 - 5 * i)).strftime("%Y-%m-%d")})
    j = client.get("/api/behavior/averaging-down-mirror").get_json()
    assert j["follow_on_count"] == 5 and j["below_avg_count"] == 5


# ── research notes ───────────────────────────────────────────────────

@pytest.mark.parametrize("q", ["since=0001-01-01", "until=9999-12-31"])
def test_research_list_extreme_dates_are_400(client, auth_user, q):
    assert client.get(f"/api/research-notes/list?{q}").status_code == 400


def test_same_stock_ks_kq_is_one_research_lookup(app, make_user):
    from services.research_notes.service import _same_stock
    with app.app_context():
        assert set(_same_stock("035760.KS")) >= {"035760", "035760.KS", "035760.KQ"}


# ── stock_record agrees with friction_outcome on a date-only buy ─────

def test_stock_record_date_only_buy_same_kst_day_is_bought_after(app, make_user):
    from services.stock_record import stock_record
    uid = make_user(email="sr-dateonly@test.com")["id"]
    pause_at = datetime(2026, 11, 5, 5, 0)  # 14:00 KST
    with app.app_context():
        db.session.add(PreTradeReflection(
            user_id=uid, intended_ticker="AAPL", intended_side="BUY", rationale="실적·숫자",
            cooldown_started_at=pause_at, cooldown_ends_at=pause_at, cancelled_at=pause_at))
        db.session.add(TradeHistory(
            user_id=uid, ticker="AAPL", name="", action="BUY", shares=1, price_per_share=100,
            total_value=100, currency="USD", traded_at=datetime(2026, 11, 5)))  # date-only
        db.session.commit()
        out = stock_record(uid, "AAPL", now=datetime(2026, 11, 10))
    assert out["counts"]["not_taken"] == 0


# ── drift compares only axes both snapshots measured ─────────────────

def test_drift_ignores_unmeasured_axes():
    from services.profile.persona_classifier_v2 import FEATURE_KEYS
    from services.profile.persona_history import compute_drift
    first = {"persona": "growth", "features": {k: 0.5 for k in FEATURE_KEYS},
             "present_mask": {k: False for k in FEATURE_KEYS}}
    last = {"persona": "growth", "features": {k: 0.0 for k in FEATURE_KEYS},
            "present_mask": {k: True for k in FEATURE_KEYS}}
    out = compute_drift([first, last])
    assert out["feature_distance"] == 0.0 and out["descriptor"] == "유지 관찰"


# ── an unresolved code with no name is not a duplicate of another ────

def test_unresolved_codes_are_not_duplicates(client, auth_user):
    tok = client.post("/api/portfolio/imports/tokens",
                      json={"name": "macro", "consent": True}).get_json()["token"]
    row = {"action": "buy", "shares": 10, "price": 5000, "traded_at": "2026-11-10 10:00"}
    r = client.post("/api/portfolio/imports/webhook",
                    json={"rows": [{"ticker": "0007C0", **row}, {"ticker": "00104K", **row}]},
                    headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 201, r.get_json()
    assert [p["status"] for p in r.get_json()["pending"]] == ["pending", "pending"]


# ── /api/inbox answers JSON 401, not a login redirect ────────────────

def test_inbox_unauthenticated_is_json_401(app):
    r = app.test_client().get("/api/inbox")
    assert r.status_code == 401 and r.is_json


# ═════ round 2 ("다 고쳐") ═══════════════════════════════════════════

RATIONALE = "실적 발표 전에 숫자를 확인하고 분할로 들어가려는 계획이다"


def _positions(client):
    rows = client.get("/api/portfolio/positions").get_json()
    return rows if isinstance(rows, list) else rows.get("positions") or rows.get("data")


# ── import matching respects the pause side (frozen: imports/ledger.py) ──

def test_sell_fill_never_matches_a_pause(client, auth_user):
    client.post("/api/pre-trade/start", json={"ticker": "005930.KS", "side": "BUY", "rationale": RATIONALE})
    r = client.post("/api/portfolio/imports/", json={
        "text": "삼성전자 10주 매도 체결 71,200원", "source": "screenshot_text", "consent": True})
    assert r.status_code == 201, r.get_json()
    assert r.get_json()["pending"][0]["pre_trade_reflection_id"] is None


def test_buy_fill_does_not_match_an_exit_pause(client, auth_user):
    client.post("/api/pre-trade/start", json={"ticker": "035720.KS", "side": "SELL", "rationale": RATIONALE})
    r = client.post("/api/portfolio/imports/", json={
        "text": "카카오 5주 매수 체결 50,000원", "source": "screenshot_text", "consent": True})
    assert r.status_code == 201, r.get_json()
    assert r.get_json()["pending"][0]["pre_trade_reflection_id"] is None


# ── /pre-trade/start input types (frozen: pre_trade/friction.py) ─────

@pytest.mark.parametrize("ticker", [123, ["AAPL"], {"a": 1}])
def test_pre_trade_rejects_non_string_ticker(client, auth_user, ticker):
    r = client.post("/api/pre-trade/start", json={"ticker": ticker, "side": "BUY", "rationale": RATIONALE})
    assert r.status_code == 400


@pytest.mark.parametrize("side", ["HOLD", 1, "sideways"])
def test_pre_trade_rejects_unknown_side(client, auth_user, side):
    r = client.post("/api/pre-trade/start", json={"ticker": "AAPL", "side": side, "rationale": RATIONALE})
    assert r.status_code == 400


def test_pre_trade_maps_korean_side(app, client, auth_user):
    r = client.post("/api/pre-trade/start", json={"ticker": "AAPL", "side": "매도", "rationale": RATIONALE})
    assert r.status_code in (200, 201), r.get_json()
    with app.app_context():
        assert PreTradeReflection.query.filter_by(user_id=auth_user["id"]).one().intended_side == "SELL"


# ── reflection_id 1.5 is refused, not truncated (frozen: pre_trade/link.py) ──

def test_reflection_id_float_is_refused(client, auth_user):
    from services.pre_trade.link import ReflectionLinkError, resolve_reflection_link
    with pytest.raises(ReflectionLinkError):
        resolve_reflection_link(auth_user["id"], 1.5, ticker="AAPL", action="buy")


# ── one stock is one position ────────────────────────────────────────

@pytest.mark.parametrize("a,b", [("035760.KQ", "035760.KS"), ("BRK.B", "brk-b")])
def test_second_spelling_merges_into_one_position(client, auth_user, no_cache, a, b):
    client.post("/api/portfolio/positions", json={"symbol": a, "quantity": 2, "price": 100})
    client.post("/api/portfolio/positions", json={"symbol": b, "quantity": 4, "price": 100})
    rows = _positions(client)
    assert len(rows) == 1 and float(rows[0]["shares"]) == 6


def test_ticker_key_class_shares():
    from services.pre_trade.friction_outcome import ticker_key
    assert ticker_key("BRK.B") == ticker_key("BRK-B")
    assert ticker_key("BRK.A") != ticker_key("BRK.B")
    assert ticker_key("005930.KQ") == ticker_key("005930.KS") == "005930"


def test_fifo_sell_on_other_spelling_closes_the_lot():
    from types import SimpleNamespace as N
    from services.profile.fifo_util import fifo_match_closed_trades
    t0 = datetime(2026, 1, 1)
    trades = [
        N(id=1, ticker="035760.KS", action="BUY", shares=1, price_per_share=100, traded_at=t0, pnl=0, source=None),
        N(id=2, ticker="035760.KQ", action="SELL", shares=1, price_per_share=120, traded_at=t0 + timedelta(days=5), pnl=20, source=None),
    ]
    pairs = fifo_match_closed_trades(trades)
    assert len(pairs) == 1


# ── error strings are not rewritten by the legal scrub ───────────────

def test_error_message_keeps_must(client, auth_user):
    r = client.get("/api/behavior/holding-mirror?period=ALL")
    assert r.status_code == 400
    assert "is recorded as" not in r.get_json()["error"]


# ── onboarding: skip keeps V3 answers whole; partial PUT merges ─────

def _v3_answers(**over):
    from services.profile.questionnaire import LEGAL_BLOCK, QUESTIONNAIRE_V3
    ans = {q["id"]: q["options"][0]["value"] for q in QUESTIONNAIRE_V3 if q["id"] != "legal_confirmations"}
    ans.update(over)
    ans["legal_confirmations"] = [o["value"] for o in LEGAL_BLOCK["options"]]
    return ans


def test_skip_after_v3_keeps_profile_type(client, auth_user, add_position):
    add_position(auth_user["id"], ticker="ONBOARD", shares=0.0)  # holdings gate
    assert client.post("/api/profile/onboarding", json={"answers": _v3_answers()}).status_code == 200
    before = client.get("/api/profile").get_json()
    client.post("/api/profile/onboarding", json={})
    after = client.get("/api/profile").get_json()
    pick = lambda j: (j.get("profile") or j).get("profile_type")  # noqa: E731
    assert pick(after) == pick(before)


def test_partial_put_keeps_other_answers(app, client, auth_user, add_position):
    from models import InvestmentProfile
    from services.profile.questionnaire import LEGAL_BLOCK, V3_QUESTION_IDS
    add_position(auth_user["id"], ticker="ONBOARD", shares=0.0)  # holdings gate
    assert client.post("/api/profile/onboarding", json={"answers": _v3_answers()}).status_code == 200
    one = sorted(V3_QUESTION_IDS)[0]
    r = client.put("/api/profile", json={"answers": {
        one: _v3_answers()[one],
        "legal_confirmations": [o["value"] for o in LEGAL_BLOCK["options"]]}})
    assert r.status_code == 200, r.get_json()
    with app.app_context():
        stored = InvestmentProfile.query.filter_by(user_id=auth_user["id"]).one().onboarding_answers()
    assert set(stored) == set(V3_QUESTION_IDS)


# ── smaller ones ─────────────────────────────────────────────────────

def test_normalize_ticker_strips_nul():
    from services.ticker_normalizer import normalize_ticker
    assert normalize_ticker("AAPL\x00") == "AAPL"


def test_alert_serializer_drops_rec_keys():
    from types import SimpleNamespace as N
    from services.serializers import serialize_alert
    a = N(id=1, kind="concentration", ticker="AAPL", title="t", message="m", signal=None, score=0,
          rec_shares=None, rec_investment=None, created_at=None, is_read=False, read_at=None,
          alert_type="concentration", body="m", name=None, stock_name=None, data_json=None)
    out = serialize_alert(a)
    assert not {"rec_shares", "rec_investment", "signal", "score"} & set(out)
