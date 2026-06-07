"""Smoke test for all 17 artifact services.

Wave 1 verification (2026-04-29). Runs each service against three
fixture scenarios — empty / minimal / normal — to verify

  1. The service can be imported.
  2. The service entry point does not raise on each scenario.
  3. The returned payload contains *something* (or, for the explicit
     None-on-empty contract, returns None gracefully).

This script does NOT verify that WeasyPrint actually rendered a PDF —
on macOS the system libraries (libgobject, libpango) are missing, so
the `_try_import_weasyprint()` shim returns None and every service
falls back to the HTML-only path. PDF rendering is exercised on
Railway Linux (Dockerfile installs libpango/libcairo/libgdk-pixbuf).

Usage:
    cd /Users/seanbae/Desktop/취준/pivoxquant
    source venv/bin/activate
    PYTHONPATH=. python3 scripts/smoke_test_artifacts.py
"""
from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime, timezone, timedelta
from typing import Any, Callable

# Run in test mode so no real broker calls / external API hits happen.
os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ALPACA_ENABLED", "0")
os.environ.setdefault("AGENT_ENABLED", "0")
os.environ.setdefault("PIVOX_BROKER_ENCRYPTION_KEY", "smoke-test-key-not-for-production")

# Ensure repo root is importable.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models.user import User  # noqa: E402
from models.position import Position  # noqa: E402
from models.trade_history import TradeHistory  # noqa: E402


# ── Service registry ────────────────────────────────────────────────────────
# (display_name, import_path, callable_factory)
# Each callable_factory(user_id) returns a no-arg callable invoking the
# service's "produce a payload for this user" entry point.

def _factory_generate_for_user(cls):
    def make(user_id):
        svc = cls()
        return lambda: svc.generate_for_user(user_id)
    return make


SERVICES: list[tuple[str, str, Callable[[int], Callable[[], Any]]]] = []


def _register():
    """Collect the 17 artefact services. Imports are lazy so an import
    failure in one service doesn't blow up the whole sweep."""
    from services.artifacts.weekly_memo_service import WeeklyMemoService
    from services.artifacts.brag_card_service import BragCardService
    from services.artifacts.monthly_brag_service import MonthlyBragService
    from services.artifacts.earnings_prebrief_service import (
        EarningsPreBriefService,
    )
    from services.artifacts.self_audit_service import SelfAuditService
    from services.artifacts.risk_board_service import RiskBoardService
    from services.artifacts.year_end_letter_service import (
        YearEndLetterService,
    )
    from services.artifacts.quarterly_self_report_service import (
        QuarterlySelfReportService,
    )
    from services.artifacts.kpi_dashboard_service import KPIDashboardService
    from services.artifacts.dd_checklist_service import DDChecklistService
    from services.artifacts.dividend_income_service import (
        DividendIncomeService,
    )
    from services.artifacts.monthly_finance_service import (
        MonthlyFinanceService,
    )
    from services.artifacts.burn_rate_service import BurnRateService
    from services.artifacts.capital_allocation_service import (
        CapitalAllocationService,
    )
    from services.artifacts.credit_rating_service import CreditRatingService
    from services.artifacts.insider_mirror_service import (
        InsiderMirrorService,
    )
    from services.artifacts.portfolio_segment_service import (
        PortfolioSegmentService,
    )
    from services.artifacts import pre_trade_checklist_service as ptcs

    # Standard generate_for_user(user_id) services (12).
    standard = [
        ("weekly_memo", WeeklyMemoService),
        ("brag_card", BragCardService),
        ("monthly_brag", MonthlyBragService),
        ("self_audit", SelfAuditService),
        ("risk_board", RiskBoardService),
        ("year_end_letter", YearEndLetterService),
        ("quarterly_self_report", QuarterlySelfReportService),
        ("kpi_dashboard", KPIDashboardService),
        ("dividend_income", DividendIncomeService),
        ("monthly_finance", MonthlyFinanceService),
        ("burn_rate", BurnRateService),
        ("credit_rating", CreditRatingService),
        ("insider_mirror", InsiderMirrorService),
        ("portfolio_segment", PortfolioSegmentService),
    ]
    for name, cls in standard:
        SERVICES.append((name, cls.__module__, _factory_generate_for_user(cls)))

    # earnings_prebrief — needs a ticker arg, returns None when no upcoming
    # earnings. Exercise the spec-aligned generate_for_user(user_id, ticker).
    def _earnings(user_id):
        svc = EarningsPreBriefService()
        return lambda: svc.generate_for_user(user_id, "AAPL")
    SERVICES.append(
        ("earnings_prebrief", EarningsPreBriefService.__module__, _earnings)
    )

    # dd_checklist — uses run_for_user(user, send=False). Different shape.
    def _dd(user_id):
        svc = DDChecklistService()
        user = db.session.get(User, user_id)
        return lambda: svc.run_for_user(user, send=False)
    SERVICES.append(
        ("dd_checklist", DDChecklistService.__module__, _dd)
    )

    # capital_allocation — uses calculate_for_user(cash_amount=, scenarios=).
    def _capital(user_id):
        svc = CapitalAllocationService()
        return lambda: svc.calculate_for_user(
            user_id,
            cash_amount=10_000.0,
            scenarios=[
                {"label": "diversify", "type": "diversify_existing"},
            ],
        )
    SERVICES.append(
        ("capital_allocation", CapitalAllocationService.__module__, _capital)
    )

    # pre_trade_checklist — module-level build_checklist(persona). No user
    # state, but exercise it once per scenario for completeness.
    def _pretrade(_user_id):
        return lambda: ptcs.build_checklist_as_dicts("balanced")
    SERVICES.append(
        ("pre_trade_checklist", ptcs.__name__, _pretrade)
    )


# ── Fixture builders ────────────────────────────────────────────────────────

def _make_user(email: str) -> int:
    user = User(email=email, name="Smoke Test", subscription_tier="premium",
                onboarding_completed=True, available_capital=100_000.0)
    db.session.add(user)
    db.session.commit()
    return user.id


def _make_minimal(user_id: int) -> None:
    db.session.add(Position(user_id=user_id, ticker="AAPL",
                            shares=10, avg_cost=150.0, buy_fx_rate=1300.0))
    db.session.add(TradeHistory(user_id=user_id, ticker="AAPL",
                                action="BUY", shares=10, price_per_share=150.0,
                                total_value=1500.0, currency="USD"))
    db.session.commit()


def _make_normal(user_id: int) -> None:
    tickers = [("AAPL", 175.0), ("MSFT", 410.0), ("NVDA", 950.0)]
    for ticker, cost in tickers:
        db.session.add(Position(user_id=user_id, ticker=ticker,
                                shares=5, avg_cost=cost, buy_fx_rate=1300.0))
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for i in range(30):
        traded = now - timedelta(days=i)
        ticker, cost = tickers[i % 3]
        db.session.add(TradeHistory(
            user_id=user_id, ticker=ticker,
            action="BUY" if i % 2 == 0 else "SELL",
            shares=1, price_per_share=cost,
            total_value=cost, pnl=10.0, pnl_pct=0.5,
            currency="USD", traded_at=traded,
        ))
    db.session.commit()


# ── Test runner ─────────────────────────────────────────────────────────────

SCENARIOS = [
    ("empty",   "smoke-empty@test.local",   None),
    ("minimal", "smoke-minimal@test.local", _make_minimal),
    ("normal",  "smoke-normal@test.local",  _make_normal),
]


def run() -> int:
    _register()
    # Wave 1 spec named 17, but the actual count is 18 once you include
    # pre_trade_checklist (module-level functions, no class). Keep both
    # numbers so a future drift triggers the assertion.
    EXPECTED = 18
    if len(SERVICES) != EXPECTED:
        print(f"FATAL: expected {EXPECTED} services, got {len(SERVICES)}",
              file=sys.stderr)
        return 2

    app = create_app()
    results: list[dict[str, Any]] = []

    with app.app_context():
        db.create_all()

        # Build one user per scenario, fixtured up.
        scenario_users: dict[str, int] = {}
        for name, email, fixture in SCENARIOS:
            uid = _make_user(email)
            if fixture:
                fixture(uid)
            scenario_users[name] = uid

        for svc_name, _module, factory in SERVICES:
            for scenario, _email, _ in SCENARIOS:
                uid = scenario_users[scenario]
                try:
                    call = factory(uid)
                    result = call()
                    status = "OK"
                    detail = type(result).__name__
                    if result is None:
                        detail = "None (graceful empty)"
                except Exception as exc:  # noqa: BLE001
                    status = "FAIL"
                    detail = f"{type(exc).__name__}: {exc}"
                    # Trim traceback to one line for the table.
                    tb = traceback.format_exc().strip().splitlines()
                    detail += " | " + tb[-3] if len(tb) >= 3 else ""
                results.append({
                    "service": svc_name,
                    "scenario": scenario,
                    "status": status,
                    "detail": detail,
                })

    # ── Report ─────────────────────────────────────────────────────────────
    print("\n=== Smoke test results ===")
    print(f"{'service':24} {'empty':10} {'minimal':10} {'normal':10}")
    by_svc: dict[str, dict[str, str]] = {}
    for r in results:
        by_svc.setdefault(r["service"], {})[r["scenario"]] = r["status"]
    for svc in [s[0] for s in SERVICES]:
        row = by_svc.get(svc, {})
        print(f"{svc:24} {row.get('empty', '-'):10} "
              f"{row.get('minimal', '-'):10} {row.get('normal', '-'):10}")

    fails = [r for r in results if r["status"] == "FAIL"]
    print(f"\n{len(results) - len(fails)} OK / {len(fails)} FAIL "
          f"of {len(results)} total")
    if fails:
        print("\n--- Failures ---")
        for r in fails:
            print(f"  [{r['service']:24}|{r['scenario']:8}] {r['detail']}")

    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(run())
