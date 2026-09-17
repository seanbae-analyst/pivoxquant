"""tests/test_sentry_body_scrub.py — request bodies must not reach Sentry raw.

2026-09-17. A security probe measured the leak with the real SDK: sentry-sdk
puts multipart form fields into ``event["request"]["data"]`` regardless of
``send_default_pii=False``, and its built-in EventScrubber matches key names
EXACTLY — ``password`` is filtered, ``pdf_password`` is not. A sub-10KB
multipart body (the "medium" ``max_request_body_size`` threshold) shipped
``{"pdf_password": "900131"}`` verbatim.

That value is the holder's 6-digit birth date, which brokers use to lock the
statement PDF and which PIPA §22 ⑥ age verification rests on here. These tests
pin ``app._mask_body`` so the next field named like a secret cannot slip past.
"""
from __future__ import annotations

from app import _mask_body


class TestMaskBody:
    def test_pdf_password_is_filtered(self):
        data = {"consent": "true", "pdf_password": "900131", "file": ""}
        _mask_body(data)
        assert data["pdf_password"] == "[Filtered]"
        assert data["consent"] == "true"          # non-secret fields untouched

    def test_plain_password_still_filtered(self):
        data = {"password": "hunter2"}
        _mask_body(data)
        assert data["password"] == "[Filtered]"

    def test_suffix_match_catches_future_names(self):
        # The guard matches a key that ENDS in a sensitive word, so a field
        # added later without touching this list is still covered.
        data = {"user_password": "x", "refresh_token": "y", "broker_app_key": "z"}
        _mask_body(data)
        assert set(data.values()) == {"[Filtered]"}

    def test_nested_dicts_and_lists(self):
        # The import webhook posts {"rows": [...]}; nesting must not hide a key.
        data = {"rows": [{"token": "abc", "ticker": "AAPL"}],
                "nested": {"client_secret": "s3cr3t", "keep": 1}}
        _mask_body(data)
        assert data["rows"][0]["token"] == "[Filtered]"
        assert data["rows"][0]["ticker"] == "AAPL"
        assert data["nested"]["client_secret"] == "[Filtered]"
        assert data["nested"]["keep"] == 1

    def test_case_insensitive(self):
        data = {"PDF_Password": "900131", "Authorization": "Bearer x"}
        _mask_body(data)
        assert data["PDF_Password"] == "[Filtered]"

    def test_tolerates_non_dict_payloads(self):
        # A JSON body can be a list or a bare string; the filter runs on every
        # event and must never raise inside Sentry's before_send.
        for payload in (None, "raw string", 42, [1, 2, 3], []):
            _mask_body(payload)  # must not raise

    def test_ticker_is_not_mistaken_for_a_secret(self):
        # "token" is sensitive but "ticker" merely starts the same way —
        # a substring match here would blank real data.
        data = {"ticker": "AAPL", "tokens_used": 5}
        _mask_body(data)
        assert data["ticker"] == "AAPL"
        assert data["tokens_used"] == 5


class TestSentryFilterIntegration:
    def test_filter_scrubs_body_headers_and_env_together(self):
        from app import _sentry_filter
        event = {
            "request": {
                "headers": {"Authorization": "Bearer secret", "Accept": "*/*"},
                "env": {"HTTP_COOKIE": "session=abc"},
                "data": {"pdf_password": "900131", "consent": "true"},
            }
        }
        out = _sentry_filter(event, {})
        assert out is not None
        assert out["request"]["data"]["pdf_password"] == "[Filtered]"
        assert out["request"]["headers"]["Authorization"] == "***"
        assert out["request"]["headers"]["Accept"] == "*/*"
        assert "HTTP_COOKIE" not in out["request"]["env"]

    def test_event_without_request_is_untouched(self):
        from app import _sentry_filter
        event = {"logentry": {"message": "something broke"}}
        assert _sentry_filter(event, {}) is event
