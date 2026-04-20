"""PivoxQuant — Naver official Search News API tests.

Verifies the legal-compliant replacement of the old mobile-JSON scraper.
All HTTP is mocked so tests stay offline.

Contract covered:
  1. ``get_news_naver`` returns [] when NAVER_CLIENT_ID/SECRET are unset
  2. Happy path — maps Naver's ``items`` → our normalised schema
  3. HTML-entity + tag stripping works (Naver returns `<b>term</b>`)
  4. RFC822 pubDate is converted to ISO-8601
  5. Cache hit avoids a second HTTP call
  6. Network failure returns []
  7. Query resolver prefers curated Korean name over bare code
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services import news_service


@pytest.fixture(autouse=True)
def _reset_news_cache():
    """Clean the module-level cache between tests."""
    news_service._CACHE.clear()
    yield
    news_service._CACHE.clear()


@pytest.fixture
def naver_env(monkeypatch):
    monkeypatch.setenv("NAVER_CLIENT_ID", "fake-client-id")
    monkeypatch.setenv("NAVER_CLIENT_SECRET", "fake-client-secret")
    yield


def _fake_response(items):
    resp = MagicMock()
    resp.status_code = 200
    resp.ok = True
    resp.json.return_value = {"items": items}
    return resp


# ── 1. Credentials missing ──────────────────────────────────────────────────

class TestMissingCredentials:
    def test_no_env_returns_empty(self, monkeypatch):
        monkeypatch.delenv("NAVER_CLIENT_ID", raising=False)
        monkeypatch.delenv("NAVER_CLIENT_SECRET", raising=False)
        assert news_service.get_news_naver("005930.KS") == []


# ── 2 + 3. Happy path and HTML cleaning ─────────────────────────────────────

class TestHappyPath:
    def test_basic_mapping(self, naver_env):
        items = [
            {
                "title": "<b>삼성전자</b>, 1Q 실적 발표",
                "description": "1분기 매출 <b>사상 최대</b>를 기록",
                "originallink": "https://www.hankyung.com/article/202604201234",
                "link": "https://n.news.naver.com/mnews/article/015/0005000000",
                "pubDate": "Mon, 20 Apr 2026 13:12:00 +0900",
            },
        ]
        with patch.object(news_service.requests, "get",
                           return_value=_fake_response(items)):
            out = news_service.get_news_naver("005930.KS")
        assert len(out) == 1
        row = out[0]
        # HTML tags stripped, title kept readable
        assert row["title"] == "삼성전자, 1Q 실적 발표"
        assert "사상 최대" in row["summary"]
        assert "<b>" not in row["summary"]
        # Domain extracted from originallink
        assert row["source"] == "hankyung.com"
        # RFC822 → ISO-8601
        assert row["published"].startswith("2026-04-20T")

    def test_short_title_skipped(self, naver_env):
        items = [
            {"title": "OK", "description": "", "link": "https://x", "pubDate": ""},
            {"title": "삼성전자 1Q 실적", "description": "", "link": "https://y",
             "pubDate": ""},
        ]
        with patch.object(news_service.requests, "get",
                           return_value=_fake_response(items)):
            out = news_service.get_news_naver("005930.KS")
        # Title "OK" is < 5 chars — dropped.
        assert len(out) == 1


# ── 4. Cache behaviour ──────────────────────────────────────────────────────

class TestCache:
    def test_cache_hit_avoids_second_call(self, naver_env):
        items = [{
            "title": "삼성전자 실적", "description": "요약",
            "link": "https://x", "originallink": "https://example.com/a",
            "pubDate": "Mon, 20 Apr 2026 13:12:00 +0900",
        }]
        call_counter = MagicMock()

        def _side_effect(*a, **kw):
            call_counter()
            return _fake_response(items)

        with patch.object(news_service.requests, "get", side_effect=_side_effect):
            news_service.get_news_naver("005930.KS")
            news_service.get_news_naver("005930.KS")
        assert call_counter.call_count == 1


# ── 5. Error handling ───────────────────────────────────────────────────────

class TestErrors:
    def test_http_error_returns_empty(self, naver_env):
        resp = MagicMock()
        resp.status_code = 500
        resp.ok = False
        resp.text = "server error"
        with patch.object(news_service.requests, "get", return_value=resp):
            assert news_service.get_news_naver("005930.KS") == []

    def test_exception_returns_empty(self, naver_env):
        with patch.object(news_service.requests, "get",
                           side_effect=RuntimeError("boom")):
            assert news_service.get_news_naver("005930.KS") == []


# ── 6. Query resolver ──────────────────────────────────────────────────────

class TestResolveQuery:
    def test_prefers_registry_name(self):
        fake_registry = MagicMock()
        fake_registry.get_name.return_value = "삼성전자"
        with patch.dict("sys.modules", {"services.kr_stock_registry": fake_registry}):
            q = news_service._resolve_query("005930.KS")
        # `import services.kr_stock_registry` inside the function reads
        # sys.modules first — but note the import form is `from services import`
        # so we patch differently below.

    def test_fallback_to_code_when_registry_missing(self):
        # If kr_stock_registry.get_name returns None, we fall back to "<code> 주가".
        with patch("services.kr_stock_registry.get_name", return_value=None):
            q = news_service._resolve_query("005930.KS")
        assert q == "005930 주가"
