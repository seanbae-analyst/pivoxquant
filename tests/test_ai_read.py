"""tests/test_ai_read.py — POST /api/portfolio/imports/ai-read (services/ai_read.py).

docs/product/AI_READ_EXPERIMENT_2026-10-07.md. The model is never called
here: a fake client returns canned answers, and these tests pin what the
SERVER does with them — the gate, the consent, the second masking pass, and
the checks that keep a model's number out of a filled cell unless the
printed text proves it.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from services import ai_read

URL = "/api/portfolio/imports/ai-read"


class FakeClient:
    def __init__(self, answer=None, stop_reason="end_turn"):
        self.answer = answer or {"screens": []}
        self.stop_reason = stop_reason
        self.calls: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(stop_reason=self.stop_reason,
                               content=[SimpleNamespace(type="text", text=json.dumps(self.answer))])


@pytest.fixture
def ai_on(app, monkeypatch):
    previous = app.config.get("AI_READ_ENABLED")
    app.config["AI_READ_ENABLED"] = True
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    yield app
    app.config["AI_READ_ENABLED"] = previous


@pytest.fixture
def fake(monkeypatch):
    holder = {"client": FakeClient()}
    monkeypatch.setattr(ai_read, "_client", lambda: holder["client"])
    return holder


def _holding(**kw):
    row = {
        "stock": "셀트리온", "stock_status": "read",
        "shares": 20, "shares_status": "read",
        "avg_cost": 136000, "avg_cost_status": "read",
        "currency": "KRW",
        "evidence": {"cost": 2720000, "value": None, "pl": None, "current": None},
        "truncated": False,
    }
    row.update(kw)
    return row


def _screen(rows, screen_type="holdings", index=0):
    return {"index": index, "screen_type": screen_type, "reason": "", "rows": rows}


SCREEN = "셀트리온\n보유수량 20주 평균가 136,000원\n매입금액 2,720,000원"


def _post(client, screens=(SCREEN,), kind="holdings", consent=True):
    return client.post(URL, json={"kind": kind, "screens": list(screens), "consent": consent})


# ── gate / contract ──────────────────────────────────────────────────

class TestGate:
    def test_off_by_default_503(self, client, auth_user):
        r = _post(client)
        assert r.status_code == 503 and r.get_json()["code"] == "AI_READ_DISABLED"

    def test_flag_without_credential_503(self, client, auth_user, app, monkeypatch):
        app.config["AI_READ_ENABLED"] = True
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
        try:
            assert _post(client).status_code == 503
        finally:
            app.config["AI_READ_ENABLED"] = False

    def test_unauthenticated_401(self, client, ai_on, fake):
        assert _post(client).status_code == 401

    def test_consent_required(self, client, auth_user, ai_on, fake):
        r = _post(client, consent=False)
        assert r.status_code == 400 and r.get_json()["code"] == "AI_READ_CONSENT_REQUIRED"
        assert fake["client"].calls == []

    @pytest.mark.parametrize("body", [
        {"kind": "notes", "screens": ["x"]},
        {"kind": "holdings", "screens": []},
        {"kind": "holdings", "screens": "x"},
        {"kind": "holdings", "screens": [1]},
        {"kind": "holdings", "screens": ["x"] * (ai_read.MAX_SCREENS + 1)},
    ])
    def test_invalid_400(self, client, auth_user, ai_on, fake, body):
        r = client.post(URL, json={**body, "consent": True})
        assert r.status_code == 400 and r.get_json()["code"] == "AI_READ_INVALID"

    def test_nothing_is_stored(self, client, auth_user, ai_on, fake, app):
        from models.import_batch import ImportBatch, PendingTrade
        fake["client"] = FakeClient({"screens": [_screen([_holding()])]})
        assert _post(client).status_code == 200
        with app.app_context():
            assert PendingTrade.query.count() == 0 and ImportBatch.query.count() == 0

    def test_too_long_is_refused_not_cut(self, client, auth_user, ai_on, fake):
        r = _post(client, screens=["가" * (ai_read.MAX_TEXT_CHARS + 1)])
        assert r.status_code == 422 and r.get_json()["code"] == "AI_READ_TOO_LONG"
        assert fake["client"].calls == []

    def test_refusal_422(self, client, auth_user, ai_on, fake):
        fake["client"] = FakeClient(stop_reason="refusal")
        r = _post(client)
        assert r.status_code == 422 and r.get_json()["code"] == "AI_READ_DECLINED"

    def test_rate_limited_per_user(self, client, auth_user, ai_on, fake, enable_rate_limit):
        codes = [_post(client).status_code for _ in range(6)]
        assert codes[:5] == [200] * 5 and codes[5] == 429


# ── what is sent ─────────────────────────────────────────────────────

class TestRequest:
    def test_account_and_customer_lines_are_dropped_again(self, client, auth_user, ai_on, fake):
        text = "124-4567-8900-XX[종합_주식] 김미래\n이서연님의 계좌\n예수금 6,403,600\n" + SCREEN
        _post(client, screens=[text])
        sent = fake["client"].calls[0]["messages"][0]["content"]
        for gone in ("김미래", "이서연", "4567", "6,403,600"):
            assert gone not in sent
        assert "셀트리온" in sent and "136,000" in sent

    def test_request_shape(self, client, auth_user, ai_on, fake):
        _post(client)
        kw = fake["client"].calls[0]
        assert kw["model"] == "claude-opus-5-5"
        assert kw["output_config"]["format"]["type"] == "json_schema"
        assert kw["extra_body"] == {"fallbacks": "default"} and kw["betas"] == ["server-side-fallback-2026-07-01"]
        assert "권유" in kw["system"]  # the extraction-only rule is in the prompt


# ── server-side checks on the answer ─────────────────────────────────

def _rows(client, fake, rows, screen_type="holdings", text=SCREEN, kind="holdings"):
    fake["client"] = FakeClient({"screens": [_screen(rows, screen_type)]})
    r = _post(client, screens=[text], kind=kind)
    assert r.status_code == 200, r.get_json()
    return r.get_json()["screens"][0]["rows"]


class TestHoldingChecks:
    def test_proven_row_is_filled(self, client, auth_user, ai_on, fake):
        [row] = _rows(client, fake, [_holding()])
        assert row["shares"] == {"value": 20} and row["avg_cost"] == {"value": 136000}
        assert row["name"] == {"value": "셀트리온"} and "cross_checked" in row["flags"]

    def test_number_not_on_screen_is_only_a_hint(self, client, auth_user, ai_on, fake):
        # 21 is not printed — a model's number never fills a cell on its own
        [row] = _rows(client, fake, [_holding(shares=21, evidence={"cost": None, "value": None, "pl": None, "current": None})])
        assert row["shares"] == {"value": None, "hint": "21"}

    def test_printed_relation_that_fails_empties_both(self, client, auth_user, ai_on, fake):
        text = "셀트리온 보유수량 20주 평균가 15,000원 매입금액 2,720,000원"
        [row] = _rows(client, fake, [_holding(avg_cost=15000)], text=text)
        assert row["shares"]["value"] is None and row["avg_cost"]["value"] is None
        assert "amount_mismatch" in row["flags"]

    def test_no_relation_on_screen_means_confirm(self, client, auth_user, ai_on, fake):
        text = "셀트리온 136주 평단 344,890원"
        row = _holding(shares=136, avg_cost=344890, evidence={"cost": None, "value": None, "pl": None, "current": None})
        [out] = _rows(client, fake, [row], text=text)
        assert out["shares"] == {"value": None, "hint": "136"} and out["avg_cost"] == {"value": None, "hint": "344890"}

    def test_value_minus_pl_proves_derived_avg(self, client, auth_user, ai_on, fake):
        text = "세아제강 23,805,000원\n180주 -6,883,200원 (-22.43%)"
        row = _holding(stock="세아제강", shares=180, avg_cost=170490, avg_cost_status="derived",
                       evidence={"cost": None, "value": 23805000, "pl": -6883200, "current": None})
        [out] = _rows(client, fake, [row], text=text)
        assert out["avg_cost"] == {"value": 170490} and "cross_checked" in out["flags"]

    def test_current_and_pl_prove_the_pair(self, client, auth_user, ai_on, fake):
        text = "TSLA 8 $212.50 $221.35 +70.80"
        row = _holding(stock="TSLA", shares=8, avg_cost=212.5, currency="USD",
                       evidence={"cost": None, "value": None, "pl": 70.8, "current": 221.35})
        [out] = _rows(client, fake, [row], text=text)
        assert out["shares"] == {"value": 8} and out["avg_cost"] == {"value": 212.5}
        assert out["code"] == {"value": "TSLA"} and out["name"] == {"value": None}

    def test_latin_name_on_won_row_is_a_name(self, client, auth_user, ai_on, fake):
        text = "GS 92,058,840원 279주 매입금액 103,213,260원 평단 369,940원"
        row = _holding(stock="GS", shares=279, avg_cost=369940,
                       evidence={"cost": 103213260, "value": None, "pl": None, "current": None})
        [out] = _rows(client, fake, [row], text=text)
        assert out["name"] == {"value": "GS"} and out["code"] == {"value": None}

    def test_guessed_stock_is_a_hint(self, client, auth_user, ai_on, fake):
        [row] = _rows(client, fake, [_holding(stock="LG전자", stock_status="guessed")])
        assert row["name"] == {"value": None, "hint": "LG전자"}

    def test_truncated_row_gets_no_numbers(self, client, auth_user, ai_on, fake):
        [row] = _rows(client, fake, [_holding(truncated=True)])
        assert row["truncated"] and row["shares"]["value"] is None and row["avg_cost"]["value"] is None

    def test_rows_on_a_non_holdings_screen_are_dropped(self, client, auth_user, ai_on, fake):
        assert _rows(client, fake, [_holding()], screen_type="watchlist") == []


class TestFillChecks:
    TEXT = "삼성전자 매수 10주 체결가 71,200원 체결금액 712,000원 2026-09-01 10:15"

    def _fill(self, **kw):
        row = {"stock": "삼성전자", "stock_status": "read", "side": "buy",
               "shares": 10, "shares_status": "read", "price": 71200, "price_status": "read",
               "date": "2026-09-01", "date_hint": None, "time": "10:15", "currency": "KRW",
               "evidence": {"amount": 712000}}
        row.update(kw)
        return row

    def test_proven_fill(self, client, auth_user, ai_on, fake):
        [row] = _rows(client, fake, [self._fill()], screen_type="fills", text=self.TEXT, kind="fills")
        assert row["shares"] == {"value": 10} and row["price"] == {"value": 71200}
        assert row["action"] == {"value": "buy"} and row["date"] == {"value": "2026-09-01"}

    def test_mismatch_empties(self, client, auth_user, ai_on, fake):
        [row] = _rows(client, fake, [self._fill(price=72100)], screen_type="fills",
                      text=self.TEXT + " 72,100", kind="fills")
        assert row["shares"]["value"] is None and "amount_mismatch" in row["flags"]

    def test_bad_date_is_a_hint(self, client, auth_user, ai_on, fake):
        [row] = _rows(client, fake, [self._fill(date="09.01", date_hint="09.01")], screen_type="fills",
                      text=self.TEXT, kind="fills")
        assert row["date"] == {"value": None, "hint": "09.01"}


# ── masking parity with frontend/src/lib/fill-ocr/mask.ts ────────────

@pytest.mark.parametrize("line,why", [
    ("124-4567-8900-XX[종합_주식] 김미래 v", "account"),
    ("(7) 12345678-010 김하나 v", "account"),
    ("[ 종 합 ( 평 생 혜택 비 대 면 )] 김 증권 =", "account"),
    ("£57 =} 1234-5678-90", "account"),
    ("1O2-34-5678l9", "account"),
    ("010-1234-5678", "account"),
    ("계좌 45160882-24 이서연", "identity"),
    ("이 서 연 님 의 계좌", "identity"),
    ("주 문 가 능 금액 2,940,000 원", "unneeded"),
    ("셀트리온 20 136,000 136,000", None),
    ("2026-10-01 09:31 체결가 71,000원", None),
    ("20261001 매수 10주", None),
    ("매 도 가능 현재가 손 익 률", None),
])
def test_drop_reason_matches_the_device(line, why):
    assert ai_read.drop_reason(line) == why
