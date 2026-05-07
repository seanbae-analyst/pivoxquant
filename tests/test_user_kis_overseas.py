"""Tests for KIS overseas (US stock) balance sync.

Scope:
  - `_inquire_overseas_balance()` — single-exchange overseas balance parsing
  - `_inquire_all_overseas_balances()` — NASD + NYSE + AMEX merge
  - `get_balance()` — domestic + overseas integration
  - `sync_to_db()` — mixed KR + US position upsert + ticker suffix rules
  - Graceful fallback on overseas API failures
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ═════════════════════════════════════════════════════════════════════════
# Shared fixtures (mirror test_user_kis_service.py)
# ═════════════════════════════════════════════════════════════════════════
@pytest.fixture
def kis_user(app, make_user):
    from services.broker.user_kis_service import upsert_kis_connection

    user = make_user(email="kis_overseas@test.com")
    with app.app_context():
        conn = upsert_kis_connection(
            user_id=user["id"],
            app_key="PS-APP-KEY-FAKE-OVERSEAS-123",
            app_secret="SECRET-FAKE-OVERSEAS-0987654321",
            account_no="12345678",
            account_prod="01",
            display_name="해외 테스트 계좌",
        )
        return {"user_id": user["id"], "conn_id": conn.id}


def _mock_token_response():
    resp = MagicMock()
    resp.ok = True
    resp.status_code = 200
    resp.text = ""
    resp.json.return_value = {"access_token": "FAKE-TOKEN-XYZ", "expires_in": 86400}
    return resp


def _mock_domestic_balance(positions=None, cash=500_000.0, total=1_000_000.0):
    resp = MagicMock()
    resp.ok = True
    resp.status_code = 200
    resp.json.return_value = {
        "rt_cd": "0",
        "msg1": "OK",
        "output1": positions
        or [
            {
                "pdno": "005930",
                "prdt_name": "삼성전자",
                "hldg_qty": "10",
                "pchs_avg_pric": "72000",
                "prpr": "75000",
                "evlu_pfls_amt": "30000",
                "evlu_pfls_rt": "4.17",
            }
        ],
        "output2": [{"dnca_tot_amt": str(cash), "tot_evlu_amt": str(total)}],
    }
    return resp


def _mock_overseas_balance(positions=None, summary=None):
    resp = MagicMock()
    resp.ok = True
    resp.status_code = 200
    resp.json.return_value = {
        "rt_cd": "0",
        "msg1": "OK",
        "output1": positions or [],
        "output2": summary or {"frcr_pchs_amt1": "0", "tot_evlu_pfls_amt": "0"},
    }
    return resp


def _overseas_item(ticker, name, qty, avg, price, excg="NASD"):
    evlu = round(float(qty) * float(price), 2)
    pchs = round(float(qty) * float(avg), 2)
    pnl = round(evlu - pchs, 2)
    pnl_rt = round((pnl / pchs) * 100, 2) if pchs else 0.0
    return {
        "ovrs_pdno": ticker,
        "ovrs_item_name": name,
        "ovrs_excg_cd": excg,
        "tr_crcy_cd": "USD",
        "ovrs_cblc_qty": str(qty),
        "ord_psbl_qty": str(qty),
        "pchs_avg_pric": str(avg),
        "now_pric2": str(price),
        "frcr_pchs_amt1": str(pchs),
        "evlu_amt": str(evlu),
        "evlu_pfls_amt": str(pnl),
        "evlu_pfls_rt": str(pnl_rt),
    }


def _make_exchange_router(responses_by_exchange, domestic_response):
    """Route requests.get to the correct mock based on URL + OVRS_EXCG_CD."""

    def _side_effect(url, headers=None, params=None, timeout=None):
        if "overseas-stock" in url:
            exch = (params or {}).get("OVRS_EXCG_CD", "")
            return responses_by_exchange.get(exch, _mock_overseas_balance([]))
        return domestic_response

    return _side_effect


# ═════════════════════════════════════════════════════════════════════════
# _inquire_overseas_balance — single exchange
# ═════════════════════════════════════════════════════════════════════════
def test_overseas_single_exchange_parses_positions(app, kis_user):
    from services.broker.user_kis_service import UserKISService

    overseas_resp = _mock_overseas_balance(
        positions=[
            _overseas_item("AAPL", "APPLE INC", 10, 150.50, 170.25, "NASD"),
            _overseas_item("MSFT", "MICROSOFT CORP", 5, 300.00, 350.00, "NASD"),
        ],
        summary={"frcr_pchs_amt1": "3005.00", "tot_evlu_pfls_amt": "447.50"},
    )

    with app.app_context(), patch(
        "services.broker.user_kis_service.requests.post",
        return_value=_mock_token_response(),
    ), patch(
        "services.broker.user_kis_service.requests.get",
        return_value=overseas_resp,
    ):
        svc = UserKISService(kis_user["user_id"])
        result = svc._inquire_overseas_balance("NASD")

    assert result["ok"] is True
    assert len(result["positions"]) == 2
    aapl = next(p for p in result["positions"] if p["ticker"] == "AAPL")
    assert aapl["shares"] == 10
    assert aapl["avg_cost"] == 150.50
    assert aapl["currency"] == "USD"
    assert aapl["market"] == "US"
    assert aapl["exchange"] == "NASD"
    assert result["summary"]["frcr_pchs_amt1"] == 3005.00


def test_overseas_single_exchange_empty(app, kis_user):
    """해외 계좌에 포지션이 없을 때 빈 리스트 (ok=True)."""
    from services.broker.user_kis_service import UserKISService

    with app.app_context(), patch(
        "services.broker.user_kis_service.requests.post",
        return_value=_mock_token_response(),
    ), patch(
        "services.broker.user_kis_service.requests.get",
        return_value=_mock_overseas_balance(positions=[]),
    ):
        svc = UserKISService(kis_user["user_id"])
        result = svc._inquire_overseas_balance("NYSE")

    assert result["ok"] is True
    assert result["positions"] == []


def test_overseas_single_exchange_http_error(app, kis_user):
    from services.broker.user_kis_service import UserKISService

    resp = MagicMock()
    resp.ok = False
    resp.status_code = 401
    resp.text = "unauthorized"
    with app.app_context(), patch(
        "services.broker.user_kis_service.requests.post",
        return_value=_mock_token_response(),
    ), patch(
        "services.broker.user_kis_service.requests.get",
        return_value=resp,
    ):
        svc = UserKISService(kis_user["user_id"])
        result = svc._inquire_overseas_balance("NASD")
    assert result["ok"] is False
    assert result["code"] == "BROKER_DOWN"


def test_overseas_skips_zero_qty_rows(app, kis_user):
    from services.broker.user_kis_service import UserKISService

    overseas_resp = _mock_overseas_balance(
        positions=[
            _overseas_item("AAPL", "APPLE INC", 10, 150, 170, "NASD"),
            # qty=0 should be skipped
            {
                **_overseas_item("TSLA", "TESLA INC", 0, 200, 250, "NASD"),
                "ovrs_cblc_qty": "0",
            },
        ]
    )
    with app.app_context(), patch(
        "services.broker.user_kis_service.requests.post",
        return_value=_mock_token_response(),
    ), patch(
        "services.broker.user_kis_service.requests.get",
        return_value=overseas_resp,
    ):
        svc = UserKISService(kis_user["user_id"])
        result = svc._inquire_overseas_balance("NASD")
    assert result["ok"] is True
    tickers = {p["ticker"] for p in result["positions"]}
    assert tickers == {"AAPL"}


# ═════════════════════════════════════════════════════════════════════════
# _inquire_all_overseas_balances — merge across 3 exchanges
# ═════════════════════════════════════════════════════════════════════════
def test_overseas_all_merges_nasd_nyse_amex(app, kis_user):
    """NASDAQ 3종목 + NYSE 2종목 + AMEX 1종목 → 6개 병합."""
    from services.broker.user_kis_service import UserKISService

    responses = {
        "NASD": _mock_overseas_balance(
            positions=[
                _overseas_item("AAPL", "APPLE INC", 10, 150, 170, "NASD"),
                _overseas_item("MSFT", "MICROSOFT", 5, 300, 350, "NASD"),
                _overseas_item("GOOGL", "ALPHABET", 2, 2500, 2800, "NASD"),
            ],
            summary={"frcr_pchs_amt1": "8005.00", "tot_evlu_pfls_amt": "847.50"},
        ),
        "NYSE": _mock_overseas_balance(
            positions=[
                _overseas_item("JPM", "JPMORGAN CHASE", 4, 140, 155, "NYSE"),
                _overseas_item("BRK.B", "BERKSHIRE", 1, 350, 400, "NYSE"),
            ],
            summary={"frcr_pchs_amt1": "910.00", "tot_evlu_pfls_amt": "110.00"},
        ),
        "AMEX": _mock_overseas_balance(
            positions=[
                _overseas_item("SPY", "SPDR S&P 500", 8, 450, 480, "AMEX"),
            ],
            summary={"frcr_pchs_amt1": "3600.00", "tot_evlu_pfls_amt": "240.00"},
        ),
    }

    with app.app_context(), patch(
        "services.broker.user_kis_service.requests.post",
        return_value=_mock_token_response(),
    ), patch(
        "services.broker.user_kis_service.requests.get",
        side_effect=_make_exchange_router(responses, _mock_domestic_balance()),
    ):
        svc = UserKISService(kis_user["user_id"])
        result = svc._inquire_all_overseas_balances()

    assert result["ok"] is True
    tickers = {p["ticker"] for p in result["positions"]}
    assert tickers == {"AAPL", "MSFT", "GOOGL", "JPM", "BRK.B", "SPY"}
    # 8005 + 910 + 3600 = 12515
    assert abs(result["total_purchase_usd"] - 12515.0) < 0.01


def test_overseas_all_skips_empty_exchange(app, kis_user):
    """NASDAQ 3 + NYSE 2 + AMEX 0 → 5개 반환, AMEX 없음은 에러 아님."""
    from services.broker.user_kis_service import UserKISService

    responses = {
        "NASD": _mock_overseas_balance(
            positions=[
                _overseas_item("AAPL", "APPLE INC", 10, 150, 170, "NASD"),
                _overseas_item("MSFT", "MICROSOFT", 5, 300, 350, "NASD"),
                _overseas_item("NVDA", "NVIDIA", 3, 400, 500, "NASD"),
            ]
        ),
        "NYSE": _mock_overseas_balance(
            positions=[
                _overseas_item("JPM", "JPMORGAN", 4, 140, 155, "NYSE"),
                _overseas_item("BAC", "BANK OF AMERICA", 20, 35, 40, "NYSE"),
            ]
        ),
        "AMEX": _mock_overseas_balance(positions=[]),
    }
    with app.app_context(), patch(
        "services.broker.user_kis_service.requests.post",
        return_value=_mock_token_response(),
    ), patch(
        "services.broker.user_kis_service.requests.get",
        side_effect=_make_exchange_router(responses, _mock_domestic_balance()),
    ):
        svc = UserKISService(kis_user["user_id"])
        result = svc._inquire_all_overseas_balances()
    assert result["ok"] is True
    tickers = {p["ticker"] for p in result["positions"]}
    assert tickers == {"AAPL", "MSFT", "NVDA", "JPM", "BAC"}
    assert len(result["positions"]) == 5


def test_overseas_all_handles_partial_exchange_failure(app, kis_user):
    """NYSE 401 에러여도 NASD/AMEX 성공이면 부분 결과 반환."""
    from services.broker.user_kis_service import UserKISService

    err_resp = MagicMock()
    err_resp.ok = False
    err_resp.status_code = 401
    err_resp.text = "unauthorized"

    responses = {
        "NASD": _mock_overseas_balance(
            positions=[_overseas_item("AAPL", "APPLE", 10, 150, 170, "NASD")]
        ),
        "NYSE": err_resp,
        "AMEX": _mock_overseas_balance(positions=[]),
    }
    with app.app_context(), patch(
        "services.broker.user_kis_service.requests.post",
        return_value=_mock_token_response(),
    ), patch(
        "services.broker.user_kis_service.requests.get",
        side_effect=_make_exchange_router(responses, _mock_domestic_balance()),
    ):
        svc = UserKISService(kis_user["user_id"])
        result = svc._inquire_all_overseas_balances()
    assert result["ok"] is True  # NASD + AMEX succeeded
    tickers = {p["ticker"] for p in result["positions"]}
    assert tickers == {"AAPL"}


def test_overseas_all_all_three_fail(app, kis_user):
    """세 거래소 모두 실패 → ok=False."""
    from services.broker.user_kis_service import UserKISService

    err_resp = MagicMock()
    err_resp.ok = False
    err_resp.status_code = 500
    err_resp.text = "server error"

    responses = {"NASD": err_resp, "NYSE": err_resp, "AMEX": err_resp}
    with app.app_context(), patch(
        "services.broker.user_kis_service.requests.post",
        return_value=_mock_token_response(),
    ), patch(
        "services.broker.user_kis_service.requests.get",
        side_effect=_make_exchange_router(responses, _mock_domestic_balance()),
    ):
        svc = UserKISService(kis_user["user_id"])
        result = svc._inquire_all_overseas_balances()
    assert result["ok"] is False
    assert result["code"] == "BROKER_DOWN"


# ═════════════════════════════════════════════════════════════════════════
# get_balance — domestic + overseas integration
# ═════════════════════════════════════════════════════════════════════════
def test_get_balance_combines_domestic_and_overseas(app, kis_user):
    from services.broker.user_kis_service import UserKISService

    responses = {
        "NASD": _mock_overseas_balance(
            positions=[_overseas_item("AAPL", "APPLE", 10, 150, 170, "NASD")]
        ),
        "NYSE": _mock_overseas_balance(
            positions=[_overseas_item("JPM", "JPMORGAN", 4, 140, 155, "NYSE")]
        ),
        "AMEX": _mock_overseas_balance(positions=[]),
    }

    with app.app_context(), patch(
        "services.broker.user_kis_service.requests.post",
        return_value=_mock_token_response(),
    ), patch(
        "services.broker.user_kis_service.requests.get",
        side_effect=_make_exchange_router(responses, _mock_domestic_balance()),
    ), patch("services.fx_service.get_rate", return_value=1400.0):
        svc = UserKISService(kis_user["user_id"])
        bal = svc.get_balance()

    assert bal["ok"] is True
    # 1 domestic + 2 overseas
    assert len(bal["positions"]) == 3
    tickers = {p["ticker"] for p in bal["positions"]}
    assert tickers == {"005930", "AAPL", "JPM"}
    # domestic KRW + overseas USD * fx_rate
    # overseas: 10*170 + 4*155 = 1700 + 620 = 2320 USD
    # 2320 * 1400 = 3,248,000 KRW
    expected = 1_000_000.0 + 2320.0 * 1400.0
    assert abs(bal["total_value"] - expected) < 1.0
    assert bal["fx_rate"] == 1400.0
    assert abs(bal["overseas_total_usd"] - 2320.0) < 0.01


def test_get_balance_domestic_failure_propagates(app, kis_user):
    """국내 조회 실패 → 전체 실패 (해외는 호출되지 않음)."""
    from services.broker.user_kis_service import UserKISService

    err_resp = MagicMock()
    err_resp.ok = False
    err_resp.status_code = 500
    err_resp.text = "down"

    with app.app_context(), patch(
        "services.broker.user_kis_service.requests.post",
        return_value=_mock_token_response(),
    ), patch(
        "services.broker.user_kis_service.requests.get",
        return_value=err_resp,
    ):
        svc = UserKISService(kis_user["user_id"])
        bal = svc.get_balance()
    assert bal["ok"] is False
    assert bal["code"] == "BROKER_DOWN"


# ═════════════════════════════════════════════════════════════════════════
# sync_to_db — mixed KR + US upsert
# ═════════════════════════════════════════════════════════════════════════
def test_sync_to_db_inserts_us_positions_without_suffix(app, kis_user):
    from models.position import Position
    from services.broker.user_kis_service import UserKISService

    responses = {
        "NASD": _mock_overseas_balance(
            positions=[
                _overseas_item("AAPL", "APPLE", 10, 150, 170, "NASD"),
                _overseas_item("MSFT", "MICROSOFT", 5, 300, 350, "NASD"),
            ]
        ),
        "NYSE": _mock_overseas_balance(
            positions=[_overseas_item("JPM", "JPMORGAN", 4, 140, 155, "NYSE")]
        ),
        "AMEX": _mock_overseas_balance(
            positions=[_overseas_item("SPY", "SPDR", 8, 450, 480, "AMEX")]
        ),
    }

    with app.app_context(), patch(
        "services.broker.user_kis_service.requests.post",
        return_value=_mock_token_response(),
    ), patch(
        "services.broker.user_kis_service.requests.get",
        side_effect=_make_exchange_router(responses, _mock_domestic_balance()),
    ), patch("services.fx_service.get_rate", return_value=1400.0):
        svc = UserKISService(kis_user["user_id"])
        result = svc.sync_to_db()

    assert result["ok"] is True
    # KR uses .KS suffix, US has no suffix
    assert "005930.KS" in result["added"]
    assert "AAPL" in result["added"]
    assert "MSFT" in result["added"]
    assert "JPM" in result["added"]
    assert "SPY" in result["added"]

    with app.app_context():
        rows = {
            p.ticker: p
            for p in Position.query.filter_by(user_id=kis_user["user_id"]).all()
        }
        assert rows["AAPL"].shares == 10
        assert rows["AAPL"].avg_cost == 150.0
        # 신규 해외 포지션은 현재 환율이 buy_fx_rate에 저장
        assert rows["AAPL"].buy_fx_rate == 1400.0
        # KR 포지션은 buy_fx_rate=0 유지
        assert rows["005930.KS"].buy_fx_rate == 0.0


def test_sync_to_db_updates_existing_us_position(app, kis_user, add_position):
    from models.position import Position
    from services.broker.user_kis_service import UserKISService

    with app.app_context():
        # pre-existing AAPL with buy_fx_rate already set
        add_position(
            kis_user["user_id"], ticker="AAPL", shares=5, avg_cost=140.0, buy_fx=1300.0
        )

    responses = {
        "NASD": _mock_overseas_balance(
            positions=[_overseas_item("AAPL", "APPLE", 12, 145, 170, "NASD")]
        ),
        "NYSE": _mock_overseas_balance(positions=[]),
        "AMEX": _mock_overseas_balance(positions=[]),
    }
    with app.app_context(), patch(
        "services.broker.user_kis_service.requests.post",
        return_value=_mock_token_response(),
    ), patch(
        "services.broker.user_kis_service.requests.get",
        side_effect=_make_exchange_router(responses, _mock_domestic_balance()),
    ), patch("services.fx_service.get_rate", return_value=1400.0):
        svc = UserKISService(kis_user["user_id"])
        result = svc.sync_to_db()

    assert result["ok"] is True
    assert "AAPL" in result["updated"]

    with app.app_context():
        aapl = Position.query.filter_by(
            user_id=kis_user["user_id"], ticker="AAPL"
        ).first()
        assert aapl.shares == 12
        assert aapl.avg_cost == 145.0
        # 기존 buy_fx_rate(1300) 유지 — 이미 설정돼있으면 덮어쓰지 않음
        assert aapl.buy_fx_rate == 1300.0


def test_sync_to_db_zeros_disappeared_us_positions(app, kis_user, add_position):
    from models.position import Position
    from services.broker.user_kis_service import UserKISService

    with app.app_context():
        # 이전에 갖고 있던 TSLA가 broker에서 사라짐
        add_position(
            kis_user["user_id"], ticker="TSLA", shares=3, avg_cost=200.0, buy_fx=1350.0
        )

    responses = {
        "NASD": _mock_overseas_balance(
            positions=[_overseas_item("AAPL", "APPLE", 10, 150, 170, "NASD")]
        ),
        "NYSE": _mock_overseas_balance(positions=[]),
        "AMEX": _mock_overseas_balance(positions=[]),
    }
    with app.app_context(), patch(
        "services.broker.user_kis_service.requests.post",
        return_value=_mock_token_response(),
    ), patch(
        "services.broker.user_kis_service.requests.get",
        side_effect=_make_exchange_router(responses, _mock_domestic_balance()),
    ), patch("services.fx_service.get_rate", return_value=1400.0):
        svc = UserKISService(kis_user["user_id"])
        result = svc.sync_to_db()

    assert result["ok"] is True
    with app.app_context():
        tsla = Position.query.filter_by(
            user_id=kis_user["user_id"], ticker="TSLA"
        ).first()
        assert tsla is not None
        assert tsla.shares == 0  # zeroed because overseas fetch succeeded


def test_sync_to_db_preserves_us_positions_on_overseas_failure(
    app, kis_user, add_position
):
    """해외 API 전체 실패 → 기존 US 포지션은 보존 (data loss 방지)."""
    from models.position import Position
    from services.broker.user_kis_service import UserKISService

    with app.app_context():
        add_position(
            kis_user["user_id"], ticker="NVDA", shares=2, avg_cost=400.0, buy_fx=1350.0
        )

    err_resp = MagicMock()
    err_resp.ok = False
    err_resp.status_code = 500
    err_resp.text = "down"

    responses = {"NASD": err_resp, "NYSE": err_resp, "AMEX": err_resp}
    with app.app_context(), patch(
        "services.broker.user_kis_service.requests.post",
        return_value=_mock_token_response(),
    ), patch(
        "services.broker.user_kis_service.requests.get",
        side_effect=_make_exchange_router(responses, _mock_domestic_balance()),
    ):
        svc = UserKISService(kis_user["user_id"])
        result = svc.sync_to_db()

    assert result["ok"] is True
    assert result["overseas_partial_failure"] is True
    with app.app_context():
        nvda = Position.query.filter_by(
            user_id=kis_user["user_id"], ticker="NVDA"
        ).first()
        assert nvda is not None
        # overseas fetch failed → 기존 포지션 보존
        assert nvda.shares == 2


def test_sync_to_db_mixed_kr_and_us(app, kis_user):
    """KR `.KS` + US no-suffix 티커가 섞여서 저장됨."""
    from models.position import Position
    from services.broker.user_kis_service import UserKISService

    domestic = _mock_domestic_balance(
        positions=[
            {
                "pdno": "005930",
                "prdt_name": "삼성전자",
                "hldg_qty": "10",
                "pchs_avg_pric": "72000",
                "prpr": "75000",
                "evlu_pfls_amt": "30000",
                "evlu_pfls_rt": "4.17",
            },
            {
                "pdno": "000660",
                "prdt_name": "SK하이닉스",
                "hldg_qty": "3",
                "pchs_avg_pric": "210000",
                "prpr": "220000",
                "evlu_pfls_amt": "30000",
                "evlu_pfls_rt": "4.76",
            },
        ]
    )
    responses = {
        "NASD": _mock_overseas_balance(
            positions=[_overseas_item("AAPL", "APPLE", 10, 150, 170, "NASD")]
        ),
        "NYSE": _mock_overseas_balance(positions=[]),
        "AMEX": _mock_overseas_balance(positions=[]),
    }
    with app.app_context(), patch(
        "services.broker.user_kis_service.requests.post",
        return_value=_mock_token_response(),
    ), patch(
        "services.broker.user_kis_service.requests.get",
        side_effect=_make_exchange_router(responses, domestic),
    ), patch("services.fx_service.get_rate", return_value=1400.0):
        svc = UserKISService(kis_user["user_id"])
        result = svc.sync_to_db()

    assert result["ok"] is True
    with app.app_context():
        tickers = {
            p.ticker
            for p in Position.query.filter_by(user_id=kis_user["user_id"]).all()
        }
        assert "005930.KS" in tickers
        assert "000660.KS" in tickers
        assert "AAPL" in tickers
        # US 티커는 `.KS` suffix 없이 저장
        assert "AAPL.KS" not in tickers
