"""
T10 — 데이터 무결성 통합 회귀 게이트.

3 axis (fx-consistency-guard / data-freshness-monitor / cache-poisoning-sentinel)
의 핵심 invariant 를 한 파일에 박아 PR 회귀를 차단한다.

이 파일은 비즈니스 로직을 수정하지 않는다 — 기존 API 의 contract 만 assert.

Precedent (메모리 v44.9):
- portfolio_history +52,281% (KRW+USD raw 합산)            → FX axis
- risk_summary 700배 inflation (raw 합산)                  → FX axis
- earnings_tone 24h cross-user leak (PR #488)              → cache axis
- risk_summary 24h cross-user leak (commit 69b583af)       → cache axis
- SignalCache cross-user sizing leak (v44.9)               → cache axis
- KIS / FMP stale 가격 (60+s)                              → freshness axis
"""
from __future__ import annotations

import time

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# AXIS 1 — FX consistency (Pattern 7)
# ─────────────────────────────────────────────────────────────────────────────


class TestFxConsistency:
    """fx-consistency-guard agent 의 회귀 case."""

    def test_fx_service_exposes_get_rate(self):
        """fx_service.get_rate() 는 portfolio_history / risk_summary 의
        FX 정규화 진입점. 시그니처 변경 시 12+ aggregation site 가 침묵 깨짐."""
        from services import fx_service

        assert callable(getattr(fx_service, "get_rate", None)), (
            "fx_service.get_rate() removed/renamed — aggregation sites will "
            "fall back to raw KRW+USD sum (Pattern 7 P0 regression)"
        )
        rate = fx_service.get_rate()
        assert isinstance(rate, (int, float)), f"non-numeric rate: {rate!r}"
        # 정상 USD/KRW 범위 — 1000 미만이면 EUR/JPY 등으로 오염된 것.
        assert rate > 1000, f"USD/KRW rate suspiciously low: {rate}"
        assert rate < 5000, f"USD/KRW rate suspiciously high: {rate}"

    def test_fx_service_exposes_is_stale(self):
        """is_stale() 가 사라지면 stale FX 가 silent 로 portfolio 합산에 박힘."""
        from services import fx_service

        assert callable(getattr(fx_service, "is_stale", None)), (
            "fx_service.is_stale() removed — staleness signal lost, "
            "aggregation sites silently use stale rate"
        )
        # 부팅 직후엔 _usdkrw_ts=0 → True 가 기대 동작.
        # (set_rate 호출됐을 수도 있으니 타입만 검증)
        assert isinstance(fx_service.is_stale(), bool)

    def test_fx_service_set_rate_rejects_below_threshold(self):
        """1000 미만 값은 USD/KRW 가 아님 → set_rate 가 무시해야 함.
        이 가드가 깨지면 FMP/exchangerate 가 EUR rate 반환 시 portfolio 침수."""
        from services import fx_service

        original = fx_service.get_rate()
        try:
            fx_service.set_rate(500.0)  # EUR-ish 잘못된 값
            assert fx_service.get_rate() == original, (
                "set_rate accepted sub-1000 value — "
                "aggregation sites will multiply KRW positions by EUR rate"
            )
        finally:
            # 원상복구는 set_rate(original) — original 자체가 >1000 이므로 OK.
            if original > 1000:
                fx_service.set_rate(original)

    def test_fx_aggregation_sites_import_fx_service(self):
        """precedent regression: portfolio_history / risk_board / weekly_memo
        등 알려진 aggregation site 가 fx_service import 를 유지해야 함."""
        from pathlib import Path

        repo = Path(__file__).resolve().parents[1]
        # SoT: agent 화이트리스트 + memory v44.9 fix 위치.
        sites = [
            "services/artifacts/risk_board_service.py",
            "services/artifacts/weekly_memo_service.py",
            "services/artifacts/dividend_income_service.py",
            "services/artifacts/monthly_finance_service.py",
            "services/broker/user_kis_service.py",
        ]
        missing = []
        for rel in sites:
            p = repo / rel
            if not p.exists():
                continue  # 파일 자체가 사라진 건 별도 issue, 본 게이트 범위 X
            content = p.read_text(encoding="utf-8", errors="ignore")
            if "fx_service" not in content:
                missing.append(rel)
        assert not missing, (
            f"FX aggregation sites lost fx_service import — Pattern 7 P0:\n  "
            + "\n  ".join(missing)
        )


# ─────────────────────────────────────────────────────────────────────────────
# AXIS 2 — Data freshness (KIS / FMP / SignalCache TTL)
# ─────────────────────────────────────────────────────────────────────────────


class TestDataFreshness:
    """data-freshness-monitor agent 의 회귀 case."""

    def test_fx_stale_threshold_constant_exists(self):
        """STALE_SECONDS 가 사라지면 freshness 비교 path 가 KeyError 로 침묵."""
        from services import fx_service

        assert hasattr(fx_service, "STALE_SECONDS"), (
            "fx_service.STALE_SECONDS removed — freshness gate broken"
        )
        assert isinstance(fx_service.STALE_SECONDS, (int, float))
        # 5분~1시간 범위 sanity. 너무 짧으면 false alarm, 너무 길면 stale 침묵.
        assert 60 <= fx_service.STALE_SECONDS <= 3600

    def test_signal_cache_ttl_imported(self):
        """SignalCache TTL 모듈 (cache_ttl) 이 import 가능해야 함.
        price_overlay 의 3-tier fallback (fresh → SignalCache → price_display 파싱)
        의 2단계 가드."""
        try:
            from services import cache_ttl  # noqa: F401
        except ImportError:
            pytest.fail(
                "services.cache_ttl removed — SignalCache freshness gate gone, "
                "price_overlay tier-2 falls back to stale data silently"
            )

    def test_price_overlay_module_present(self):
        """price_overlay.py 가 사라지면 portfolio/watchlist 가 stale SignalCache
        를 fresh 처럼 노출 (v44.x precedent)."""
        try:
            import services.price_overlay as overlay
        except ImportError:
            pytest.fail("services.price_overlay removed — stale SignalCache leak path open")
        assert callable(getattr(overlay, "overlay_prices", None)), (
            "overlay_prices() helper missing — portfolio /watchlist routes "
            "lose 3-tier freshness fallback"
        )

    def test_unofficial_data_sources_not_imported(self):
        """feedback_official_data_only — yfinance / pykrx / naver/daum finance
        영구 금지. requirements.txt 직접 검증."""
        from pathlib import Path

        repo = Path(__file__).resolve().parents[1]
        banned = ("yfinance", "pykrx")
        for req in ("requirements.txt", "requirements-dev.txt"):
            p = repo / req
            if not p.exists():
                continue
            content = p.read_text(encoding="utf-8", errors="ignore").lower()
            for pkg in banned:
                # 주석 줄 제거 후 검사.
                for line in content.splitlines():
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#"):
                        continue
                    # `pkg==` 또는 `pkg>=` 등 dependency 라인만.
                    if stripped.split("==")[0].split(">=")[0].split("<")[0].strip() == pkg:
                        pytest.fail(
                            f"BANNED dependency '{pkg}' in {req} — "
                            f"feedback_official_data_only violation"
                        )


# ─────────────────────────────────────────────────────────────────────────────
# AXIS 3 — Cache poisoning (Pattern 6, cross-user PII leak)
# ─────────────────────────────────────────────────────────────────────────────


class TestCachePoisoning:
    """cache-poisoning-sentinel agent 의 회귀 case."""

    def test_risk_snapshot_cache_isolates_users(self):
        """risk_snapshot_cache 가 user_id 를 key 에 포함하는지 직접 검증.
        user_A 가 쓰고 user_B 가 같은 signature 로 read → None 반환 필수."""
        from services import cache_service

        cache_service.risk_snapshot_cache_clear()
        try:
            sig = "test_positions_signature_v1"
            payload_a = {"var_95": 0.123, "owner": "user_A"}
            cache_service.risk_snapshot_cache_set(user_id=101, signature=sig, payload=payload_a)

            # 같은 signature, 다른 user_id → cross-user leak 차단 확인.
            leaked = cache_service.risk_snapshot_cache_get(user_id=202, signature=sig)
            assert leaked is None, (
                f"P0 CACHE POISONING: user_B read user_A payload via shared "
                f"signature — risk_snapshot_cache key composition broken. "
                f"leaked={leaked!r}"
            )

            # 동일 user_id 는 정상적으로 read 가능해야 함 (regression sanity).
            own = cache_service.risk_snapshot_cache_get(user_id=101, signature=sig)
            assert own == payload_a, "owner read broken"
        finally:
            cache_service.risk_snapshot_cache_clear()

    def test_risk_snapshot_cache_rejects_falsy_user_id(self):
        """user_id=None / 0 / '' 면 cache set 자체가 skip 되어야 함.
        anonymous 가 캐시에 박히면 모든 unauthenticated 요청이 같은 entry 공유."""
        from services import cache_service

        cache_service.risk_snapshot_cache_clear()
        try:
            cache_service.risk_snapshot_cache_set(user_id=None, signature="sig", payload={"x": 1})
            cache_service.risk_snapshot_cache_set(user_id=0, signature="sig", payload={"x": 2})
            cache_service.risk_snapshot_cache_set(user_id="", signature="sig", payload={"x": 3})
            # 어느 것도 read 되면 안 됨.
            for uid in (None, 0, "", 1):
                got = cache_service.risk_snapshot_cache_get(user_id=uid, signature="sig")
                assert got is None, (
                    f"falsy user_id={uid!r} accepted into cache — "
                    f"anonymous cross-user leak path open"
                )
        finally:
            cache_service.risk_snapshot_cache_clear()

    def test_discover_cache_documented_as_user_keyed(self):
        """discover_cache 는 user_id keyed dict (services/cache_service.py:17 주석).
        주석/구조 보존 — global dict 가 되면 user A 의 KR/US movers 가 user B 노출."""
        from pathlib import Path

        repo = Path(__file__).resolve().parents[1]
        src = (repo / "services" / "cache_service.py").read_text(encoding="utf-8")
        # 주석에 "user_id" 가 박혀있어야 함 (key 구성 문서화).
        assert "user_id" in src.split("discover_cache:")[1].split("\n")[0], (
            "discover_cache 주석에서 user_id key 표시 사라짐 — "
            "global dict 로 바뀌면 P0 cross-user leak"
        )

    def test_earnings_tone_cache_is_ticker_global_by_design(self):
        """earnings_tone_cache 는 의도적으로 ticker 만 key — earnings 톤은 public
        시장 정보이므로 user-agnostic. 화이트리스트로 명시적 보호.

        regression 방향: 만약 누군가 user-specific 데이터 (예: 개인 코멘트, persona
        분석 결과) 를 earnings_tone_cache 에 박으면 cross-user leak. 본 테스트는
        API 시그니처가 ticker 만 받는지 확인 — user_id 인자 추가되면 화이트리스트
        재평가 필요."""
        import inspect

        from services import cache_service

        sig = inspect.signature(cache_service.earnings_tone_cache_set)
        params = list(sig.parameters.keys())
        # 기대: (ticker, data). user_id 가 등장하면 화이트리스트 재평가 알림.
        assert params == ["ticker", "data"], (
            f"earnings_tone_cache_set signature drifted from (ticker, data) "
            f"to {params} — if user_id added, ensure key composition includes it "
            f"(Pattern 6 precedent: PR #488)"
        )

    def test_earnings_tone_cache_ttl_within_safe_bound(self):
        """TTL 이 90일 → 만약 user-specific 데이터가 박히는 회귀 발생 시
        cross-user 노출 기간이 90일. 본 테스트는 TTL 이 의도 범위 유지를 보증."""
        from services import cache_service

        assert hasattr(cache_service, "EARNINGS_TONE_TTL")
        ttl = cache_service.EARNINGS_TONE_TTL
        # earnings 는 분기별 → 90일 = 90*86400. 365일 넘어가면 의도 이탈.
        assert 7 * 86400 <= ttl <= 180 * 86400, (
            f"EARNINGS_TONE_TTL drifted to {ttl}s — 분기 사이클 범위 이탈, "
            f"화이트리스트 정당화 근거 약화"
        )

    def test_cache_service_max_entries_bounded(self):
        """EARNINGS_TONE_MAX_ENTRIES / RISK_SNAPSHOT_MAX_ENTRIES — unbounded
        dict 면 OOM + LRU 미동작으로 인해 stale entry 가 영원히 살아남음."""
        from services import cache_service

        assert hasattr(cache_service, "EARNINGS_TONE_MAX_ENTRIES")
        assert hasattr(cache_service, "RISK_SNAPSHOT_MAX_ENTRIES")
        assert 0 < cache_service.EARNINGS_TONE_MAX_ENTRIES <= 10_000
        assert 0 < cache_service.RISK_SNAPSHOT_MAX_ENTRIES <= 10_000


# ─────────────────────────────────────────────────────────────────────────────
# Meta — 3 agent 정의 파일 존재 (workflow dispatch 의 전제조건)
# ─────────────────────────────────────────────────────────────────────────────


def test_three_data_integrity_agents_defined():
    """wave-data-integrity workflow 가 호출하는 3 agent .md 파일이 실재해야 함."""
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    agents = [
        "fx-consistency-guard.md",
        "data-freshness-monitor.md",
        "cache-poisoning-sentinel.md",
    ]
    missing = [a for a in agents if not (repo / ".claude" / "agents" / a).exists()]
    assert not missing, f"missing dormant agents: {missing}"
