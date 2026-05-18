"""
v44.9 PR #488 regression guard — earnings_tone cache poisoning.

transcript_text (Pro user-supplied) 결과는 shared cache 미저장.
FMP-sourced (transcript_text=None) 결과만 cache.

이 가드가 없으면 비공개 transcript 결과가 24h cross-user 노출 위험.
2026-05-19 Wave 8 hotfix 회귀 점검에서 적용 누락 발견 + 본 fix 후 추가.
"""
from unittest.mock import patch


def test_transcript_supplied_result_not_cached(app):
    """transcript_text 제공 시 _set_cache 호출 안 함을 검증."""
    from services.ai import models

    with app.app_context():
        models._cache.clear()
        with patch.object(models, "_claude_json", return_value={
            "ticker": "AAPL",
            "sentiment": "neutral",
            "summary": "test transcript-supplied result",
            "risks": [],
            "catalysts": [],
        }):
            result, status = models.EarningsCallToneAnalyzer.analyze(
                "AAPL", transcript_text="Pro user private transcript"
            )
        assert status == 200
        # cache 에 저장 X (transcript_text 제공)
        cache_key = "earnings_tone:AAPL"
        assert cache_key not in models._cache, (
            f"transcript_text-supplied result must NOT be cached, "
            f"but {cache_key} found in shared cache"
        )


def test_fmp_sourced_result_cached(app):
    """transcript_text=None 시 FMP fetch 후 결과는 cache 저장."""
    from services.ai import models

    with app.app_context():
        models._cache.clear()
        with patch.object(models.EarningsCallToneAnalyzer, "_fetch_transcript",
                          return_value="FMP-sourced public transcript"):
            with patch.object(models, "_claude_json", return_value={
                "ticker": "MSFT",
                "sentiment": "positive",
                "summary": "FMP transcript result",
                "risks": [],
                "catalysts": [],
            }):
                result, status = models.EarningsCallToneAnalyzer.analyze("MSFT")
        assert status == 200
        # cache 에 저장 O (FMP-sourced, transcript_text=None)
        cache_key = "earnings_tone:MSFT"
        assert cache_key in models._cache, (
            f"FMP-sourced result must be cached for cross-user benefit, "
            f"but {cache_key} not found in shared cache"
        )
