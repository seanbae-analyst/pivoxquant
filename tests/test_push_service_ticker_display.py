"""Regression guard for push-service ticker display.

Mirrors tests/test_alert_ticker_display.py — same feedback_ticker_display
rule, but for the push-notification side-channel (services/push_service.py).
The CEO has repeated 3+ times that surfaces should prefer "이름 (티커)" over
raw tickers. notify_alert / notify_trade now use _label_for_ticker; this
test pins that contract so a future regression to "raw ticker only" is
caught locally before merge.
"""
from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pytest


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

_DUP_PAREN = re.compile(r"(\S+)\s*\(\1\)")  # bans "X (X)" pattern in titles


def _captured_send_push():
    """Patch services.push_service.send_push_to_user and return the
    MagicMock so individual tests can inspect title / body kwargs.

    F3-03 sister fix (2026-05-17): the patch path used to be
    ``routes.push.send_push_to_user`` — but PR #437 moved the function
    to services.push_service and ``routes.push`` only keeps a thin
    re-export. The notify_alert / notify_trade helpers in
    services.push_service call the *module-local* binding, which the old
    patch never bound — every test below was running the real sender
    (which no-op'd at the VAPID check) and the
    ``send.assert_called_once`` line raised silently before mock checks
    landed. Re-target the patch at the actual module-level symbol.
    """
    return patch("services.push_service.send_push_to_user", new=MagicMock())


# --------------------------------------------------------------------------
# notify_alert
# --------------------------------------------------------------------------

class TestNotifyAlertLabel:
    def test_kr_ticker_resolved_renders_name_with_ticker(self, app):
        from services.push_service import notify_alert
        with _captured_send_push() as send:
            with patch(
                "services.name_resolver.resolve_stock_name_with_db",
                return_value="삼성전자",
            ):
                notify_alert(
                    user_id=1,
                    alert_data={
                        "signal": "POSITIVE",
                        "ticker": "005930.KS",
                        "message": "msg",
                    },
                )
        send.assert_called_once()
        title = send.call_args.kwargs["title"]
        assert "삼성전자 (005930.KS)" in title
        assert not _DUP_PAREN.search(title)

    def test_kr_ticker_unresolved_renders_ticker_only(self, app):
        from services.push_service import notify_alert
        with _captured_send_push() as send:
            with patch(
                "services.name_resolver.resolve_stock_name_with_db",
                return_value=None,
            ):
                notify_alert(
                    user_id=1,
                    alert_data={
                        "signal": "NEGATIVE",
                        "ticker": "124500.KQ",
                        "message": "msg",
                    },
                )
        title = send.call_args.kwargs["title"]
        assert "124500.KQ" in title
        # critical: no "124500.KQ (124500.KQ)" duplication
        assert not _DUP_PAREN.search(title)

    def test_resolver_returns_ticker_itself_collapses_to_ticker(self, app):
        """If the resolver echoes the ticker back (a known degenerate path),
        the label must NOT be "X (X)".
        """
        from services.push_service import notify_alert
        with _captured_send_push() as send:
            with patch(
                "services.name_resolver.resolve_stock_name_with_db",
                return_value="ZZZZ",
            ):
                notify_alert(
                    user_id=1,
                    alert_data={
                        "signal": "POSITIVE",
                        "ticker": "ZZZZ",
                        "message": "msg",
                    },
                )
        title = send.call_args.kwargs["title"]
        assert not _DUP_PAREN.search(title)
        assert title.endswith("ZZZZ")

    def test_resolver_exception_falls_back_to_ticker(self, app):
        from services.push_service import notify_alert
        with _captured_send_push() as send:
            with patch(
                "services.name_resolver.resolve_stock_name_with_db",
                side_effect=RuntimeError("db down"),
            ):
                notify_alert(
                    user_id=1,
                    alert_data={
                        "signal": "POSITIVE",
                        "ticker": "AAPL",
                        "message": "msg",
                    },
                )
        title = send.call_args.kwargs["title"]
        assert "AAPL" in title
        assert not _DUP_PAREN.search(title)


# --------------------------------------------------------------------------
# notify_trade
# --------------------------------------------------------------------------

class TestNotifyTradeLabel:
    def test_trade_body_uses_resolved_name(self, app):
        from services.push_service import notify_trade
        with _captured_send_push() as send:
            with patch(
                "services.name_resolver.resolve_stock_name_with_db",
                return_value="Apple Inc.",
            ):
                notify_trade(
                    user_id=1,
                    ticker="AAPL",
                    action="buy",
                    shares=10,
                    price=180.0,
                )
        body = send.call_args.kwargs["body"]
        assert "Apple Inc. (AAPL)" in body
        assert not _DUP_PAREN.search(body)

    def test_trade_body_falls_back_to_ticker_on_miss(self, app):
        from services.push_service import notify_trade
        with _captured_send_push() as send:
            with patch(
                "services.name_resolver.resolve_stock_name_with_db",
                return_value=None,
            ):
                notify_trade(
                    user_id=1,
                    ticker="ZZZZ",
                    action="sell",
                    shares=5,
                    price=10.0,
                )
        body = send.call_args.kwargs["body"]
        assert "ZZZZ" in body
        assert not _DUP_PAREN.search(body)


# --------------------------------------------------------------------------
# Cross-surface ban
# --------------------------------------------------------------------------

class TestNoDupParenAcrossSurfaces:
    """Catch any future "X (X)" duplication regardless of which helper
    is patched. Lightweight contract test."""

    @pytest.mark.parametrize("ticker", ["AAPL", "005930.KS", "124500.KQ"])
    def test_notify_alert_never_dups(self, app, ticker):
        from services.push_service import notify_alert
        with _captured_send_push() as send:
            with patch(
                "services.name_resolver.resolve_stock_name_with_db",
                return_value=ticker,  # degenerate echo
            ):
                notify_alert(
                    user_id=1,
                    alert_data={"signal": "POSITIVE", "ticker": ticker, "message": "m"},
                )
        title = send.call_args.kwargs["title"]
        assert not _DUP_PAREN.search(title), (
            f"duplication detected in title for {ticker}: {title!r}"
        )
