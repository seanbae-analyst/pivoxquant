"""2026-06-12 토큰 최적화 회귀 가드.

세 가지 변경을 잠근다 (제품 Anthropic 지출 최적화):

1. 뉴스 감성 경로 (services/data/fetcher.py)
   - TTL 600s → 6h: _scheduled_refresh(3분 cron) × 포지션 fan-out 구조에서
     10분 TTL은 같은 헤드라인을 종목당 하루 ~144회 재채점했다.
   - DailyAiBudget breaker 신설 (B3 사각지대): 소진 시 키워드 폴백.
2. AI 결과 앱 캐시 (services/cache_service.py): swot/competitor/
   sector_trend/commentary — ticker(sector) 단위 비개인화 분석 6h 캐시.
3. 라우트 와이어링 (routes/ai.py): 캐시 히트가 §101 allowlist 를
   우회하지 않을 것 (조회가 allowlist 검사 *이후*).
"""
from __future__ import annotations

import time

import pytest

from services.ai_budget import DailyAiBudget


# ── 1. 뉴스 감성 경로 ────────────────────────────────────────────────────────

def test_news_score_ttl_is_hours_not_minutes():
    """TTL 회귀 가드: 600s 로 되돌아가면 3분 cron 구조에서 일 수천 콜이
    부활한다. 최소 1h 이상을 강제."""
    from services.data.fetcher import DataFetcher
    assert DataFetcher._NEWS_SCORE_TTL >= 3600, (
        f"_NEWS_SCORE_TTL={DataFetcher._NEWS_SCORE_TTL}s — 분 단위 TTL 은 "
        "engine.analyze 핫패스에서 Claude 재채점 폭주를 부활시킨다"
    )


def test_news_ai_budget_exhaustion_falls_back_to_keywords(monkeypatch):
    """예산 소진 → _score_news_with_ai 가 None → 호출자는 키워드 폴백.
    Anthropic 클라이언트는 절대 호출되지 않아야 한다."""
    from services.data.fetcher import DataFetcher

    f = DataFetcher.__new__(DataFetcher)  # 네트워크 init 우회
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")

    exhausted = DailyAiBudget("news_sentiment", 1)
    exhausted.try_consume()  # 마지막 1 소진
    monkeypatch.setattr(DataFetcher, "_NEWS_AI_BUDGET", exhausted)

    class _Boom:  # 호출되면 테스트 실패
        def __getattr__(self, name):
            raise AssertionError("budget exhausted 인데 Anthropic 호출 시도")

    monkeypatch.setattr(DataFetcher, "_news_ai_client", _Boom())

    out = f._score_news_with_ai("AAPL", [{"title": "Apple ships record units"}])
    assert out is None  # → 호출자에서 keyword scorer 로 폴백


def test_news_ai_budget_lazy_singleton():
    from services.data.fetcher import DataFetcher
    DataFetcher._NEWS_AI_BUDGET = None  # reset
    b1 = DataFetcher._news_ai_budget()
    b2 = DataFetcher._news_ai_budget()
    assert b1 is b2
    assert b1.kind == "news_sentiment"


# ── 2. AI 결과 캐시 ──────────────────────────────────────────────────────────

def test_ai_result_cache_roundtrip_and_ttl(monkeypatch):
    from services import cache_service as cs

    cs.ai_result_cache.clear()
    cs.ai_result_cache_set("swot", "aapl", {"swot": "x"})
    # 대소문자 정규화 + 엔드포인트 분리
    assert cs.ai_result_cache_get("swot", "AAPL") == {"swot": "x"}
    assert cs.ai_result_cache_get("competitor", "AAPL") is None

    # TTL 경과 → None
    key = ("swot", "AAPL")
    cs.ai_result_cache[key]["ts"] = time.time() - cs.AI_RESULT_TTL - 1
    assert cs.ai_result_cache_get("swot", "AAPL") is None


def test_ai_result_cache_lru_prune(monkeypatch):
    from services import cache_service as cs

    cs.ai_result_cache.clear()
    monkeypatch.setattr(cs, "AI_RESULT_MAX_ENTRIES", 8)
    for i in range(9):
        cs.ai_result_cache_set("swot", f"T{i}", {"i": i})
    assert len(cs.ai_result_cache) <= 8  # 25% 정리 후 상한 이하


# ── 3. 라우트 와이어링 (캐시 히트 ≠ 게이트 우회) ─────────────────────────────

class _StubAI:
    """generate_* 호출 횟수를 세는 AI 스텁."""

    available = True
    last_error = None

    def __init__(self):
        self.calls = 0

    def generate_swot(self, d):
        self.calls += 1
        return {"swot": f"gen-{self.calls}", "swot_kr": "한국어"}


@pytest.fixture
def pro_client(client, make_user):
    user = make_user(email="token_opt_pro@test.com", tier="pro")
    resp = client.post("/api/auth/login", json={
        "email": user["email"], "password": user["password"],
    })
    assert resp.status_code == 200
    return client


def test_swot_second_call_served_from_cache(pro_client, monkeypatch):
    import routes.ai as rai
    from services import cache_service as cs

    cs.ai_result_cache.clear()
    stub = _StubAI()
    monkeypatch.setattr(rai, "ai", stub)
    monkeypatch.setattr(rai, "is_user_allowed_ticker", lambda uid, t: True)

    body = {"ticker": "MSFT", "name": "Microsoft"}
    r1 = pro_client.post("/api/ai/swot", json=body)
    assert r1.status_code == 200, r1.get_data(as_text=True)
    r2 = pro_client.post("/api/ai/swot", json=body)
    assert r2.status_code == 200

    assert stub.calls == 1, "두 번째 호출은 캐시에서 — Claude 재호출 금지"
    assert r2.get_json()["swot"] == r1.get_json()["swot"]


def test_swot_cache_hit_does_not_bypass_allowlist(pro_client, monkeypatch):
    """다른 유저가 채운 캐시가 있어도 allowlist 거부 유저는 403 — 조회가
    접근통제 *이후*라는 순서를 잠근다."""
    import routes.ai as rai
    from services import cache_service as cs

    cs.ai_result_cache.clear()
    cs.ai_result_cache_set("swot", "NVDA", {"swot": "cached", "swot_kr": "캐시"})

    stub = _StubAI()
    monkeypatch.setattr(rai, "ai", stub)
    monkeypatch.setattr(rai, "is_user_allowed_ticker", lambda uid, t: False)

    r = pro_client.post("/api/ai/swot", json={"ticker": "NVDA"})
    assert r.status_code in (403, 404), (
        f"allowlist 거부가 캐시 히트로 우회됨: {r.status_code}"
    )
    assert stub.calls == 0
