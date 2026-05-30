"""tests/test_concentration_mirror.py — PivoxQuant Concentration Mirror
(집중도 거울)

Covers the cost-basis concentration mirror:

    services.behavior.concentration_mirror.compute_concentration_mirror(user_id)
    GET /api/behavior/concentration-mirror

Invariants validated here
-------------------------
- Weight = single largest ``shares * avg_cost`` / total ``shares *
  avg_cost`` (cost basis, NEVER market value). No external price call.
- Edge cases: no positions / one position (100.0) / many positions /
  avg_cost==0 excluded / shares==0 excluded / total==0 zero-div guard /
  negative/None shares|cost excluded.
- largest holding surfaces display NAME (feedback_ticker_display) — a KR
  position resolves to hangul, never a naked ``.KS`` code.
- NO score / grade / ratio / index field ever appears in the output.
- API: auth required, disclaimer present, observational language only.
"""
from __future__ import annotations

import pytest

from models import Position
from services.behavior.concentration_mirror import compute_concentration_mirror


# ═════════════════════════════════════════════════════════════════════
# Forbidden-key guard (점수화 함정 회피 — DECISIONS.md)
# ═════════════════════════════════════════════════════════════════════

_FORBIDDEN_SCORE_KEYS = {"ratio", "score", "grade", "index"}


def _assert_no_scoring(result: dict) -> None:
    """The mirror must never surface a score/grade/ratio/index anywhere."""
    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                assert k not in _FORBIDDEN_SCORE_KEYS, f"forbidden key {k!r}"
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(result)


# ═════════════════════════════════════════════════════════════════════
# Helpers — insert Position rows directly (bypasses route)
# ═════════════════════════════════════════════════════════════════════

def _insert_positions(app, user_id, specs):
    """specs: list of dicts with ticker/shares/avg_cost."""
    from extensions import db
    with app.app_context():
        for s in specs:
            db.session.add(Position(
                user_id=user_id,
                ticker=s["ticker"],
                shares=s["shares"],
                avg_cost=s["avg_cost"],
            ))
        db.session.commit()


@pytest.fixture
def user_id(make_user, app):
    """A persisted user id (no login needed for the pure function tests)."""
    u = make_user()
    return u["id"]


# ═════════════════════════════════════════════════════════════════════
# Pure function — compute_concentration_mirror(user_id)
# ═════════════════════════════════════════════════════════════════════

class TestComputeFunction:
    def test_no_positions_insufficient(self, app, user_id):
        with app.app_context():
            result = compute_concentration_mirror(user_id)
        assert result["sufficient_data"] is False
        assert result["ticker_count"] == 0
        assert result["max_weight_pct"] is None
        assert result["largest_ticker"] is None
        assert result["cost_basis_note"] == "평균매입가 기준 (시장가 아님)"
        _assert_no_scoring(result)

    def test_single_position_is_hundred_pct(self, app, user_id):
        _insert_positions(app, user_id, [
            {"ticker": "AAPL", "shares": 10.0, "avg_cost": 150.0},
        ])
        with app.app_context():
            result = compute_concentration_mirror(user_id)
        assert result["sufficient_data"] is True
        assert result["ticker_count"] == 1
        # one holding IS the whole portfolio — a fact, not a judgement
        assert result["max_weight_pct"] == 100.0
        assert result["largest_ticker"] == "AAPL"
        _assert_no_scoring(result)

    def test_many_positions_weight_math(self, app, user_id):
        # values: 6000 / 2000 / 1000 → total 9000; largest 6000/9000=66.67%
        _insert_positions(app, user_id, [
            {"ticker": "AAA", "shares": 60.0, "avg_cost": 100.0},   # 6000
            {"ticker": "BBB", "shares": 20.0, "avg_cost": 100.0},   # 2000
            {"ticker": "CCC", "shares": 10.0, "avg_cost": 100.0},   # 1000
        ])
        with app.app_context():
            result = compute_concentration_mirror(user_id)
        assert result["sufficient_data"] is True
        assert result["ticker_count"] == 3
        assert result["max_weight_pct"] == pytest.approx(66.7, abs=0.05)
        assert result["largest_ticker"] == "AAA"
        _assert_no_scoring(result)

    def test_avg_cost_zero_excluded(self, app, user_id):
        # ZERO has 0 avg_cost → excluded; only REAL counts → 100%
        _insert_positions(app, user_id, [
            {"ticker": "REAL", "shares": 10.0, "avg_cost": 50.0},
            {"ticker": "ZERO", "shares": 10.0, "avg_cost": 0.0},
        ])
        with app.app_context():
            result = compute_concentration_mirror(user_id)
        assert result["ticker_count"] == 1
        assert result["max_weight_pct"] == 100.0
        assert result["largest_ticker"] == "REAL"
        _assert_no_scoring(result)

    def test_shares_zero_excluded(self, app, user_id):
        _insert_positions(app, user_id, [
            {"ticker": "HELD", "shares": 5.0, "avg_cost": 200.0},
            {"ticker": "SOLD", "shares": 0.0, "avg_cost": 200.0},
        ])
        with app.app_context():
            result = compute_concentration_mirror(user_id)
        assert result["ticker_count"] == 1
        assert result["max_weight_pct"] == 100.0
        assert result["largest_ticker"] == "HELD"

    def test_negative_shares_and_cost_excluded(self, app, user_id):
        _insert_positions(app, user_id, [
            {"ticker": "GOOD", "shares": 4.0, "avg_cost": 25.0},
            {"ticker": "NEGSH", "shares": -3.0, "avg_cost": 25.0},
            {"ticker": "NEGCO", "shares": 3.0, "avg_cost": -25.0},
        ])
        with app.app_context():
            result = compute_concentration_mirror(user_id)
        assert result["ticker_count"] == 1
        assert result["largest_ticker"] == "GOOD"

    def test_all_zero_cost_basis_zero_div_guard(self, app, user_id):
        # every position contributes zero → total == 0 → insufficient,
        # NOT a ZeroDivisionError.
        _insert_positions(app, user_id, [
            {"ticker": "Z1", "shares": 0.0, "avg_cost": 100.0},
            {"ticker": "Z2", "shares": 10.0, "avg_cost": 0.0},
        ])
        with app.app_context():
            result = compute_concentration_mirror(user_id)
        assert result["sufficient_data"] is False
        assert result["ticker_count"] == 0
        assert result["max_weight_pct"] is None
        assert result["largest_ticker"] is None

    def test_kr_ticker_resolves_to_name(self, app, user_id, monkeypatch):
        # Largest holding is a KR ticker → display NAME, not naked .KS code.
        import services.behavior.concentration_mirror as mod
        monkeypatch.setattr(
            mod, "kr_display_name",
            lambda t: "삼성전자" if t == "005930.KS" else t,
        )
        _insert_positions(app, user_id, [
            {"ticker": "005930.KS", "shares": 100.0, "avg_cost": 80000.0},
            {"ticker": "AAPL", "shares": 1.0, "avg_cost": 100.0},
        ])
        with app.app_context():
            result = compute_concentration_mirror(user_id)
        assert result["largest_ticker"] == "삼성전자"
        assert ".KS" not in result["largest_ticker"]
        _assert_no_scoring(result)


# ═════════════════════════════════════════════════════════════════════
# API surface — GET /api/behavior/concentration-mirror
# ═════════════════════════════════════════════════════════════════════

class TestApi:
    def _insert(self, app, user_id, specs):
        _insert_positions(app, user_id, specs)

    def test_requires_auth(self, client):
        resp = client.get("/api/behavior/concentration-mirror")
        assert resp.status_code in (401, 403)

    def test_new_user_insufficient(self, client, auth_user):
        resp = client.get("/api/behavior/concentration-mirror")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["ok"] is True
        assert body["sufficient_data"] is False
        assert body["max_weight_pct"] is None
        assert body["largest_ticker"] is None
        assert "disclaimer" in body
        # no scoring keys leak through the envelope
        assert not (_FORBIDDEN_SCORE_KEYS & set(body))

    def test_populated_response(self, client, auth_user, app):
        self._insert(app, auth_user["id"], [
            {"ticker": "AAA", "shares": 60.0, "avg_cost": 100.0},  # 6000
            {"ticker": "BBB", "shares": 40.0, "avg_cost": 100.0},  # 4000
        ])
        resp = client.get("/api/behavior/concentration-mirror")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["sufficient_data"] is True
        assert body["ticker_count"] == 2
        assert body["max_weight_pct"] == pytest.approx(60.0, abs=0.05)
        assert body["largest_ticker"] == "AAA"
        assert body["cost_basis_note"] == "평균매입가 기준 (시장가 아님)"
        _assert_no_scoring(body)

    def test_disclaimer_is_observational(self, client, auth_user):
        resp = client.get("/api/behavior/concentration-mirror")
        body = resp.get_json()
        disclaimer = body["disclaimer"]
        # observational / non-judgemental — never a recommendation
        assert "권유가" in disclaimer or "권유" in disclaimer
        for banned in ("추천", "조언", "과집중", "분산 필요", "위험"):
            assert banned not in disclaimer
