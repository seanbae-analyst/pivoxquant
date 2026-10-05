"""GET /api/reports/mirror — 앱 안 리포트 보기 (2026-10-05).

PDF 라우트와 같은 데이터(build_mirror_report)와 같은 문구(mirror_labels)를
JSON 으로 낸다. 본인 것만, 빈 기록은 404 가 아니라 has_content=False.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from services.reports.mirror_pdf import mirror_labels

_BANNED_RE = re.compile(
    r"\b(buy|sell|hold|recommend|recommendation|advice|advise)\b|추천|조언",
    re.IGNORECASE,
)


def _add_trade(app, user_id, *, ticker="AAPL", action="BUY", days_ago=3, price=100.0):
    from extensions import db
    from models import TradeHistory

    with app.app_context():
        db.session.add(TradeHistory(
            user_id=user_id, ticker=ticker, name=ticker, action=action,
            shares=1.0, price_per_share=price, total_value=price, currency="USD",
            traded_at=datetime.utcnow() - timedelta(days=days_ago),
        ))
        db.session.commit()


def test_requires_login(client):
    resp = client.get("/api/reports/mirror")
    assert resp.status_code == 401
    assert resp.get_json()["code"] == "SESSION_EXPIRED"


def test_empty_record_is_200_with_has_content_false(client, auth_user):
    resp = client.get("/api/reports/mirror")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["report"]["has_content"] is False
    assert body["report"]["period_days"] == 30


def test_report_carries_own_records_and_labels(app, client, auth_user):
    _add_trade(app, auth_user["id"], days_ago=5)
    _add_trade(app, auth_user["id"], action="SELL", days_ago=2, price=110.0)
    body = client.get("/api/reports/mirror?locale=ko").get_json()

    report = body["report"]
    assert report["has_content"] is True
    assert report["turnover"]["trade_count"] == 2
    assert "pauses" in report
    assert "user_id" not in report
    assert body["labels"]["title"] == mirror_labels("ko")["title"]


def test_never_reads_another_users_records(app, client, auth_user, make_user):
    other = make_user(email="other-json@test.com")
    _add_trade(app, other["id"], days_ago=3)
    resp = client.get(f"/api/reports/mirror?user_id={other['id']}")
    assert resp.get_json()["report"]["has_content"] is False


def test_locale_switch_and_fallback(client, auth_user):
    en = client.get("/api/reports/mirror?locale=en").get_json()
    assert en["locale"] == "en"
    assert en["labels"]["title"] == mirror_labels("en")["title"]
    odd = client.get("/api/reports/mirror?locale=fr").get_json()
    assert odd["locale"] == "ko"


def test_not_publicly_cacheable(client, auth_user):
    resp = client.get("/api/reports/mirror")
    assert "no-store" in resp.headers.get("Cache-Control", "")


def test_labels_carry_no_directive_vocabulary():
    for locale in ("ko", "en"):
        labels = mirror_labels(locale)
        text = " ".join(
            " ".join(v) if isinstance(v, list) else str(v) for v in labels.values()
        )
        assert not _BANNED_RE.search(text), locale
