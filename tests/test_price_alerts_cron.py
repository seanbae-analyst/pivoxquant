"""Bug D — 52-week high/low + sector concentration bell-alert cron wiring.

배경
====
``services/alert.py`` 의 ``check_52w_highs_lows()`` + ``check_concentration_alerts()``
는 존재했으나 어느 스케줄러에도 등록되지 않아, 사용자가 설정한 52주 고/저 in-app
벨 알림이 자동 발화된 적이 없었다(어드민 수동 ``POST /api/alerts/admin/check`` 외 0회).

본 테스트는:
  1. ``app.py:_init_scheduler`` 가 ``price_alerts_daily`` job 을 등록하고, 그 trigger
     가 ``timezone='Asia/Seoul'`` + max_instances=1 + coalesce=True 임을 검증
     (UTC 9시간 시프트 / 멱등성 회귀 방지).
  2. ``check_52w_highs_lows`` 가 KR(.KS/.KQ) 티커를 skip 하는 wave1 가드를 유지함
     (FMP KRX 커버리지 불량 → 오발화/예산낭비 회피)을 검증.
  3. US 티커는 52주 고점 터치 시 실제 벨 알림을 생성함을 검증(기능 동작).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


# ─── 1. 스케줄러 등록 (price_alerts_daily) ─────────────────────────────────


def test_price_alerts_job_registered_with_seoul_cron():
    """``_init_scheduler`` 는 ``price_alerts_daily`` 를 평일 KST cron 으로 등록.

    ``RUN_SCHEDULER=0`` 운영 환경에서는 ``_init_scheduler`` 가 호출되지 않으므로
    여기서는 직접 호출하되, 백그라운드 스레드/advisory-lock 부작용은 차단한다.
    """
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    import app as app_module

    captured = {}

    real_init = BackgroundScheduler.__init__

    def _capture_init(self, *a, **kw):
        real_init(self, *a, **kw)
        captured["sched"] = self

    # Patch out side effects: don't actually start the scheduler thread, and
    # force the advisory-lock acquire to True so the (no-op) start is reached.
    # ``register_cron_jobs`` is imported lazily inside _init_scheduler and is
    # already wrapped in try/except there — no need to stub it; we just stub
    # the start() thread + advisory lock so no background work runs.
    with patch.object(BackgroundScheduler, "__init__", _capture_init), \
         patch.object(BackgroundScheduler, "start", lambda self, *a, **k: None), \
         patch.object(app_module, "_try_acquire_scheduler_lock", return_value=True):
        app_module._init_scheduler(app_module.app)

    sched = captured["sched"]
    jobs = {j.id: j for j in sched.get_jobs()}
    assert "price_alerts_daily" in jobs, (
        f"price_alerts_daily not registered — Bug D regression. "
        f"jobs={sorted(jobs)}"
    )

    job = jobs["price_alerts_daily"]
    assert isinstance(job.trigger, CronTrigger)
    assert str(job.trigger.timezone) == "Asia/Seoul", (
        f"price_alerts_daily tz={job.trigger.timezone!r}; must be Asia/Seoul "
        "(Railway UTC default would shift it 9h)"
    )
    # 멱등성 가드 (missed-run 스택 방지).
    assert job.max_instances == 1
    assert job.coalesce is True


# ─── 2. check_52w_highs_lows — KR skip 보존 ────────────────────────────────


def test_check_52w_skips_kr_tickers(app, make_user, add_position):
    """.KS / .KQ 티커는 FMP-guard 로 skip — ``_lookup_52w_range`` 호출조차 안 됨."""
    user = make_user()
    add_position(user["id"], ticker="005930.KS", shares=10, avg_cost=70000)
    add_position(user["id"], ticker="035720.KQ", shares=5, avg_cost=50000)

    from services import alert as alert_mod
    from unittest.mock import MagicMock

    # check_52w_highs_lows does `from services.container import fetcher`, so we
    # patch the singleton on the container module.
    fake_fetcher = MagicMock()
    fake_fetcher.get_prices_batch.return_value = {
        "005930.KS": {"price": 70000.0},
        "035720.KQ": {"price": 50000.0},
    }

    # Even if every KR position were "at its high", the KR guard must prevent
    # any range lookup or alert. We stub the range to always trip — if the
    # guard were broken, we'd see alerts_created > 0.
    with app.app_context():
        with patch.object(
            alert_mod, "_lookup_52w_range", return_value=(100.0, 50.0)
        ) as mock_range, \
             patch("services.container.fetcher", fake_fetcher):
            metrics = alert_mod.check_52w_highs_lows()

    # KR tickers skipped → no range lookups, no alerts.
    assert mock_range.call_count == 0, (
        "KR (.KS/.KQ) tickers must be skipped before _lookup_52w_range — "
        f"got {mock_range.call_count} lookups"
    )
    assert metrics["alerts_created"] == 0


# ─── 3. check_52w_highs_lows — US 티커 실제 발화 ───────────────────────────


def test_check_52w_creates_alert_for_us_high(app, make_user, add_position):
    """US 티커가 52주 고점에 닿으면 벨 알림이 실제로 생성된다(기능 동작)."""
    user = make_user()
    add_position(user["id"], ticker="AAPL", shares=10, avg_cost=100)

    from services import alert as alert_mod
    from models import Alert
    from unittest.mock import MagicMock

    fake_fetcher = MagicMock()
    # price >= hi*0.999 → 52w-high alert.
    fake_fetcher.get_prices_batch.return_value = {"AAPL": {"price": 200.0}}

    with app.app_context():
        with patch.object(
            alert_mod, "_lookup_52w_range", return_value=(200.0, 100.0)
        ), patch("services.container.fetcher", fake_fetcher):
            metrics = alert_mod.check_52w_highs_lows()

        assert metrics["alerts_created"] == 1, metrics
        rows = Alert.query.filter_by(user_id=user["id"], ticker="AAPL").all()
        kinds = [r.kind for r in rows]
        assert "price_52w_high" in kinds, f"kinds={kinds}"
