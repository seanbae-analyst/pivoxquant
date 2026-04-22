"""Tests for services.broker.user_kis_service and services.crypto_service.

Week 1 coverage: crypto roundtrip, auth success/failure, balance parsing,
DB sync upsert logic. Network I/O is fully mocked via `unittest.mock.patch`
against `requests.post` / `requests.get` inside the service module.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services import crypto_service


# ═════════════════════════════════════════════════════════════════════════
# crypto_service — roundtrip + tamper detection
# ═════════════════════════════════════════════════════════════════════════
def test_crypto_roundtrip():
    pt = "PS123456789ABCDEF-secret"
    ct = crypto_service.encrypt(pt)
    assert ct != pt
    assert crypto_service.decrypt(ct) == pt


def test_crypto_aad_mismatch_rejected():
    ct = crypto_service.encrypt("hello", aad=b"broker")
    with pytest.raises(Exception):
        crypto_service.decrypt(ct, aad=b"other-context")


def test_crypto_tampered_ciphertext_rejected():
    ct = crypto_service.encrypt("hello")
    # Flip a byte somewhere in the middle.
    import base64
    raw = bytearray(base64.b64decode(ct))
    raw[len(raw) // 2] ^= 0x01
    tampered = base64.b64encode(bytes(raw)).decode()
    with pytest.raises(Exception):
        crypto_service.decrypt(tampered)


def test_crypto_empty_ciphertext_raises():
    with pytest.raises(ValueError):
        crypto_service.decrypt("")


# ═════════════════════════════════════════════════════════════════════════
# UserKISService — authenticate / balance / sync_to_db
# ═════════════════════════════════════════════════════════════════════════
@pytest.fixture
def kis_user(app, make_user):
    """Create a user with an active KIS BrokerConnection containing encrypted creds."""
    from services.broker.user_kis_service import upsert_kis_connection

    user = make_user(email="kisuser@test.com")
    with app.app_context():
        conn = upsert_kis_connection(
            user_id=user["id"],
            app_key="PS-APP-KEY-FAKE-1234567890",
            app_secret="SECRET-FAKE-ABCDEFGH-0987654321",
            account_no="XXXXXXXX",
            account_prod="01",
            display_name="테스트 계좌",
        )
        return {"user_id": user["id"], "conn_id": conn.id}


def _mock_token_response(status=200, payload=None, text=""):
    resp = MagicMock()
    resp.ok = status == 200
    resp.status_code = status
    resp.text = text
    resp.json.return_value = payload or {
        "access_token": "FAKE-TOKEN-XYZ",
        "expires_in": 86400,
    }
    return resp


def _mock_balance_response(positions=None, cash=500_000.0, total=1_000_000.0):
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
            },
        ],
        "output2": [{"dnca_tot_amt": str(cash), "tot_evlu_amt": str(total)}],
    }
    return resp


def test_authenticate_success(app, kis_user):
    from services.broker.user_kis_service import UserKISService

    with app.app_context(), patch(
        "services.broker.user_kis_service.requests.post",
        return_value=_mock_token_response(),
    ) as mock_post:
        svc = UserKISService(kis_user["user_id"])
        result = svc.authenticate(force=True)
        assert result["ok"] is True
        assert result["token_cached"] is False
        mock_post.assert_called_once()
        # Token should now be cached — next authenticate should hit cache, not network.
        mock_post.reset_mock()
        result2 = svc.authenticate()
        assert result2["ok"] is True
        assert result2["token_cached"] is True
        mock_post.assert_not_called()


def test_authenticate_rate_limited(app, kis_user):
    from services.broker.user_kis_service import UserKISService

    resp = MagicMock()
    resp.ok = False
    resp.status_code = 403
    resp.text = '{"error_code":"EGW00133","error_description":"1분 1회"}'
    with app.app_context(), patch(
        "services.broker.user_kis_service.requests.post", return_value=resp
    ):
        svc = UserKISService(kis_user["user_id"])
        result = svc.authenticate(force=True)
        assert result["ok"] is False
        assert result["code"] == "RATE_LIMITED"


def test_authenticate_invalid_credentials(app, kis_user):
    from services.broker.user_kis_service import UserKISService

    resp = MagicMock()
    resp.ok = False
    resp.status_code = 401
    resp.text = '{"error":"invalid credentials"}'
    with app.app_context(), patch(
        "services.broker.user_kis_service.requests.post", return_value=resp
    ):
        svc = UserKISService(kis_user["user_id"])
        result = svc.authenticate(force=True)
        assert result["ok"] is False
        assert result["code"] == "INVALID_CREDENTIALS"


def test_authenticate_network_error(app, kis_user):
    import requests as _rq
    from services.broker.user_kis_service import UserKISService

    with app.app_context(), patch(
        "services.broker.user_kis_service.requests.post",
        side_effect=_rq.ConnectionError("dns"),
    ):
        svc = UserKISService(kis_user["user_id"])
        result = svc.authenticate(force=True)
        assert result["ok"] is False
        assert result["code"] == "BROKER_DOWN"


def test_get_balance_and_positions(app, kis_user):
    from services.broker.user_kis_service import UserKISService

    with app.app_context(), patch(
        "services.broker.user_kis_service.requests.post",
        return_value=_mock_token_response(),
    ), patch(
        "services.broker.user_kis_service.requests.get",
        return_value=_mock_balance_response(),
    ):
        svc = UserKISService(kis_user["user_id"])
        bal = svc.get_balance()
        assert bal["ok"] is True
        assert bal["available_cash"] == 500_000.0
        assert bal["total_value"] == 1_000_000.0
        assert len(bal["positions"]) == 1
        assert bal["positions"][0]["ticker"] == "005930"
        assert bal["positions"][0]["name"] == "삼성전자"
        assert bal["positions"][0]["shares"] == 10

        # get_positions is a thin convenience wrapper
        positions = svc.get_positions()
        assert len(positions) == 1
        assert positions[0]["currency"] == "KRW"


def test_sync_to_db_inserts_and_updates(app, kis_user, add_position):
    from models.position import Position
    from services.broker.user_kis_service import UserKISService

    with app.app_context():
        # Pre-existing position that should be updated.
        add_position(kis_user["user_id"], ticker="005930.KS", shares=5, avg_cost=70000)

    with app.app_context(), patch(
        "services.broker.user_kis_service.requests.post",
        return_value=_mock_token_response(),
    ), patch(
        "services.broker.user_kis_service.requests.get",
        return_value=_mock_balance_response(
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
        ),
    ):
        svc = UserKISService(kis_user["user_id"])
        result = svc.sync_to_db()
        assert result["ok"] is True
        assert "000660.KS" in result["added"]
        assert "005930.KS" in result["updated"]

        # Verify DB state
        with app.app_context():
            rows = {p.ticker: p for p in Position.query.filter_by(
                user_id=kis_user["user_id"]
            ).all()}
            assert rows["005930.KS"].shares == 10
            assert rows["005930.KS"].avg_cost == 72000
            assert rows["000660.KS"].shares == 3
            assert rows["000660.KS"].avg_cost == 210000


def test_sync_to_db_zeros_disappeared_positions(app, kis_user, add_position):
    from models.position import Position
    from services.broker.user_kis_service import UserKISService

    with app.app_context():
        # Previously held position that no longer appears in broker data.
        add_position(kis_user["user_id"], ticker="035720.KS", shares=4, avg_cost=50000)

    with app.app_context(), patch(
        "services.broker.user_kis_service.requests.post",
        return_value=_mock_token_response(),
    ), patch(
        "services.broker.user_kis_service.requests.get",
        return_value=_mock_balance_response(positions=[]),  # empty broker side
    ):
        svc = UserKISService(kis_user["user_id"])
        result = svc.sync_to_db()
        assert result["ok"] is True

        with app.app_context():
            kakao = Position.query.filter_by(
                user_id=kis_user["user_id"], ticker="035720.KS"
            ).first()
            assert kakao is not None
            assert kakao.shares == 0


def test_service_raises_when_no_connection(app, make_user):
    from services.broker.user_kis_service import UserKISError, UserKISService

    user = make_user(email="noconn@test.com")
    with app.app_context(), pytest.raises(UserKISError) as excinfo:
        UserKISService(user["id"])
    assert excinfo.value.code == "NO_CONNECTION"


# ═════════════════════════════════════════════════════════════════════════
# Blueprint registration
# ═════════════════════════════════════════════════════════════════════════
def test_broker_oauth_blueprint_registered(app):
    rules = {r.rule for r in app.url_map.iter_rules()}
    assert "/api/broker/kis/connect" in rules
    assert "/api/broker/kis/sync" in rules
    assert "/api/broker/kis/disconnect" in rules
    assert "/api/broker/kis/status" in rules


def test_kis_connect_rejects_invalid_payload(client, auth_user):
    resp = client.post("/api/broker/kis/connect", json={})
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["code"] == "INVALID_APP_KEY"


def test_kis_status_when_not_connected(client, auth_user):
    resp = client.get("/api/broker/kis/status")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["connected"] is False


def test_kis_disconnect_when_not_connected(client, auth_user):
    resp = client.delete("/api/broker/kis/disconnect")
    assert resp.status_code == 404
    body = resp.get_json()
    assert body["code"] == "NO_CONNECTION"
