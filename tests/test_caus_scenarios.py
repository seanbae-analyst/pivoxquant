"""Regression guards for `scripts/caus_scenarios/` (CAUS Phase 3).

Smoke-only — these tests do NOT launch a browser (Playwright is slow/flaky
in unit tests). They verify:

  - All 7 scenario modules import cleanly
  - Each exposes `run(page, context, *, agent_id, base_url) -> list[dict]`
  - The Day0..Day6 rotation maps each module to the correct index
  - `_base` helpers behave correctly (forbidden grep, naked ticker grep,
    KOSPI sanity, finding factory)

Browser-dependent assertions live in `scripts/caus_daily_sweep.py --scenario
dayN` manual smoke (see PR body for first-run evidence).
"""
from __future__ import annotations

import importlib
import importlib.util
import inspect
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def caus():
    """Load caus_daily_sweep (it's a script, not a package member)."""
    script_path = REPO_ROOT / "scripts" / "caus_daily_sweep.py"
    spec = importlib.util.spec_from_file_location("caus_daily_sweep", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["caus_daily_sweep"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def base():
    """Load the _base helpers module via package import (parents on sys.path)."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return importlib.import_module("scripts.caus_scenarios._base")


# --- Scenario module shape contract ----------------------------------------


SCENARIO_NAMES = [
    "day0_signup",
    "day1_kr_search",
    "day2_us_watchlist",
    "day3_portfolio_risk",
    "day4_alert_simulation",
    "day5_reports",
    "day6_payment",
]


@pytest.mark.parametrize("module_name", SCENARIO_NAMES)
def test_scenario_module_imports(module_name):
    """Every scenario module imports without error."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    mod = importlib.import_module(f"scripts.caus_scenarios.{module_name}")
    assert mod is not None


@pytest.mark.parametrize("module_name", SCENARIO_NAMES)
def test_scenario_module_run_signature(module_name):
    """run() must accept (page, context, *, agent_id, base_url)."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    mod = importlib.import_module(f"scripts.caus_scenarios.{module_name}")
    run_fn = getattr(mod, "run", None)
    assert callable(run_fn), f"{module_name}.run not callable"
    sig = inspect.signature(run_fn)
    params = sig.parameters
    assert "page" in params, f"{module_name}.run missing 'page'"
    assert "context" in params, f"{module_name}.run missing 'context'"
    assert "agent_id" in params, f"{module_name}.run missing 'agent_id'"
    assert "base_url" in params, f"{module_name}.run missing 'base_url'"
    # agent_id + base_url must be keyword-only.
    for kw in ("agent_id", "base_url"):
        assert params[kw].kind == inspect.Parameter.KEYWORD_ONLY, \
            f"{module_name}.run.{kw} must be keyword-only"


def test_scenario_day_index_rotation(caus):
    """DAY_SCENARIOS[i][0] matches the day{i}_* prefix exactly."""
    for i, (module_name, _label) in enumerate(caus.DAY_SCENARIOS):
        assert module_name == SCENARIO_NAMES[i], \
            f"Day {i} rotation mismatch: {module_name} != {SCENARIO_NAMES[i]}"


# --- _base helper contracts ------------------------------------------------


def test_new_finding_shape(base):
    f = base.new_finding(
        severity="P0", category="법규", page="/ai", summary="x",
    )
    for k in ("severity", "category", "page", "summary", "repro", "screenshot"):
        assert k in f
    assert f["repro"] == ""
    assert f["screenshot"] == "N/A"


def test_new_finding_truncates_summary(base):
    long = "x" * 500
    f = base.new_finding(
        severity="P1", category="UX", page="/h", summary=long,
    )
    assert len(f["summary"]) == 200


def test_grep_forbidden_ko(base):
    assert "매수" in base.grep_forbidden("지금 매수 타이밍")
    assert "추천" in base.grep_forbidden("AI 추천 종목")


def test_grep_forbidden_en(base):
    hits = base.grep_forbidden("BUY this stock now")
    assert "BUY" in hits


def test_grep_forbidden_clean(base):
    assert base.grep_forbidden("POSITIVE 시그널입니다") == []
    assert base.grep_forbidden("NEUTRAL") == []


def test_grep_forbidden_word_boundary(base):
    """'BUYER' should NOT match BUY (word boundary)."""
    assert "BUY" not in base.grep_forbidden("BUYER seller")


def test_naked_kr_ticker_with_korean_name(base):
    """'삼성전자 (005930.KS)' is NOT naked."""
    text = "삼성전자 (005930.KS) 시그널"
    assert base.grep_naked_kr_ticker(text) == []


def test_naked_kr_ticker_standalone(base):
    """Bare '005930.KS' without 한글 in 50-char window IS naked."""
    text = "Today: 005930.KS rose 2%"
    naked = base.grep_naked_kr_ticker(text)
    assert "005930.KS" in naked


def test_naked_kr_ticker_dedup(base):
    """Duplicate naked tickers reported once."""
    text = "005930.KS A 005930.KS B 005930.KS"
    naked = base.grep_naked_kr_ticker(text)
    assert naked == ["005930.KS"]


def test_sanity_kospi_in_range(base):
    assert base.sanity_kospi(2700) is True
    assert base.sanity_kospi(3500) is True


def test_sanity_kospi_out_of_range(base):
    assert base.sanity_kospi(0) is False
    assert base.sanity_kospi(50000) is False
    assert base.sanity_kospi(None) is False
    assert base.sanity_kospi("not-a-number") is False


def test_inject_session_missing_file_noop(base, tmp_path):
    """Missing session file → no exception, no cookies."""
    class FakeCtx:
        added = []
        def add_cookies(self, c):
            self.added.extend(c)
    ctx = FakeCtx()
    base.inject_session(ctx, tmp_path / "nope.json", "https://www.pivoxquant.com")
    assert ctx.added == []


def test_is_beta_gate_detects_url(base):
    """`is_beta_gate` returns True when URL contains /beta-gate."""

    class FakePage:
        url = "https://www.pivoxquant.com/beta-gate?redirect=%2Fpricing"
        def evaluate(self, _):
            return ""

    assert base.is_beta_gate(FakePage()) is True


def test_is_beta_gate_detects_korean_text(base):
    """`is_beta_gate` returns True when body contains '베타 비밀번호'."""

    class FakePage:
        url = "https://www.pivoxquant.com/pricing"
        def evaluate(self, _):
            return "베타 비밀번호를 입력하세요"

    assert base.is_beta_gate(FakePage()) is True


def test_is_beta_gate_negative(base):
    """`is_beta_gate` returns False on normal page."""

    class FakePage:
        url = "https://www.pivoxquant.com/home"
        def evaluate(self, _):
            return "안녕하세요 환영합니다"

    assert base.is_beta_gate(FakePage()) is False


def test_inject_session_parses_set_cookie(base, tmp_path):
    sess = tmp_path / "sim.json"
    sess.write_text(
        '{"set_cookie": "session=abc123; Path=/; HttpOnly; SameSite=Lax"}',
        encoding="utf-8",
    )

    class FakeCtx:
        added: list = []
        def add_cookies(self, c):
            self.added.extend(c)

    ctx = FakeCtx()
    base.inject_session(ctx, sess, "https://www.pivoxquant.com")
    assert len(ctx.added) == 1
    cookie = ctx.added[0]
    assert cookie["name"] == "session"
    assert cookie["value"] == "abc123"
    assert cookie["domain"] == "www.pivoxquant.com"
    assert cookie["path"] == "/"
    assert cookie.get("httpOnly") is True
    assert cookie.get("sameSite") == "Lax"
