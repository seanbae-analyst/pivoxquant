"""Regression: earnings pre-brief push title + email subject must use
"name (ticker)" via ``_label_for_ticker`` instead of the raw ticker.

Memory rule ``feedback_ticker_display`` (CEO directive, repeated 3+ times):
- All user-facing surfaces (push, email subject, artifact label) should
  prefer the company name primary, ticker secondary in parens.
- When the resolver can't find a name, render ONLY the ticker — never
  produce ``"X (X)"`` (the duplicated-token bug).

Background: prior to 2026-05-13 the earnings pre-brief push title and
email subject embedded the raw ticker directly:

    title_text = f"{currency_prefix(ticker)}{ticker} 실적 30분 전"
    subject    = f"[Pre-Brief] ${ticker} — Earnings in {lead} min"

This bypassed the central ``_label_for_ticker`` resolver and surfaced
``₩005930.KS 실적 30분 전`` to KR users instead of the readable
``₩삼성전자 (005930.KS) 실적 30분 전``. The fix routes both through
``_label_for_ticker``; this test pins that contract.
"""
from __future__ import annotations

import re
from unittest.mock import MagicMock, patch


_DUP_PAREN = re.compile(r"(\S+)\s*\(\1\)")  # bans "X (X)" duplication


# ── push title (earnings pre-brief send_notification) ───────────────────────


class TestEarningsPrebriefPushTitle:
    """``EarningsPreBriefService.send_notification`` push branch must use the
    label resolver in the title text it hands to ``send_push_to_user``.
    """

    def test_kr_ticker_resolved_renders_name_with_ticker(self, app, make_user):
        from services.artifacts.earnings_prebrief_service import (
            EarningsPreBriefService,
        )
        from models import User
        user = make_user(email="prebrief-kr-hit@test.com")
        user_obj = db_get_user(user["id"])

        svc = EarningsPreBriefService()
        data = {"ticker": "005930.KS", "_artifact_id": 42}

        with patch(
            "services.name_resolver.resolve_stock_name_with_db",
            return_value="삼성전자",
        ), patch(
            "routes.push.send_push_to_user", new=MagicMock(),
        ) as send, patch.object(
            svc, "_send_email", return_value=False,
        ):
            svc.send_notification(user_obj, b"", "<html/>", data)

        # send_push_to_user must have been called with a title that includes
        # "삼성전자 (005930.KS)" — never the raw ticker alone.
        send.assert_called_once()
        title = send.call_args.kwargs["title"]
        assert "삼성전자 (005930.KS)" in title, title
        assert not _DUP_PAREN.search(title), title

    def test_kr_ticker_unresolved_renders_ticker_only_no_dup(
        self, app, make_user,
    ):
        from services.artifacts.earnings_prebrief_service import (
            EarningsPreBriefService,
        )
        user = make_user(email="prebrief-kr-miss@test.com")
        user_obj = db_get_user(user["id"])

        svc = EarningsPreBriefService()
        data = {"ticker": "124500.KQ", "_artifact_id": 99}

        with patch(
            "services.name_resolver.resolve_stock_name_with_db",
            return_value=None,
        ), patch(
            "routes.push.send_push_to_user", new=MagicMock(),
        ) as send, patch.object(
            svc, "_send_email", return_value=False,
        ):
            svc.send_notification(user_obj, b"", "<html/>", data)

        send.assert_called_once()
        title = send.call_args.kwargs["title"]
        # The ticker should still be there (single copy) — the bug is
        # producing "124500.KQ (124500.KQ)".
        assert "124500.KQ" in title, title
        assert not _DUP_PAREN.search(title), title

    def test_us_ticker_resolved_renders_name_with_ticker(self, app, make_user):
        from services.artifacts.earnings_prebrief_service import (
            EarningsPreBriefService,
        )
        user = make_user(email="prebrief-us-hit@test.com")
        user_obj = db_get_user(user["id"])

        svc = EarningsPreBriefService()
        data = {"ticker": "AAPL", "_artifact_id": 1}

        with patch(
            "services.name_resolver.resolve_stock_name_with_db",
            return_value="Apple Inc.",
        ), patch(
            "routes.push.send_push_to_user", new=MagicMock(),
        ) as send, patch.object(
            svc, "_send_email", return_value=False,
        ):
            svc.send_notification(user_obj, b"", "<html/>", data)

        send.assert_called_once()
        title = send.call_args.kwargs["title"]
        assert "Apple Inc. (AAPL)" in title, title
        assert not _DUP_PAREN.search(title), title


# ── email digest subject (single-ticker branch) ─────────────────────────────


class TestEarningsPrebriefDigestSubject:
    """The single-ticker digest subject path must also honour the rule."""

    def test_digest_subject_single_ticker_uses_label(self, app, make_user):
        from services.artifacts.earnings_prebrief_service import (
            EarningsPreBriefService,
        )

        user = make_user(email="digest-subject-kr@test.com")
        user_obj = db_get_user(user["id"])

        svc = EarningsPreBriefService()
        entries = [{"ticker": "005930.KS"}]

        captured = {}

        class _CapturingSender:
            def send(self, *_args, **kwargs):
                captured.update(kwargs)
                return True

        with patch(
            "services.name_resolver.resolve_stock_name_with_db",
            return_value="삼성전자",
        ), patch(
            "services.artifacts.earnings_prebrief_service.EmailSender",
            _CapturingSender,
            create=True,
        ), patch(
            "services.email.EmailSender", _CapturingSender,
        ):
            svc._send_digest_email(user_obj, "<html/>", entries)

        subject = captured.get("subject", "")
        assert "삼성전자 (005930.KS)" in subject, subject
        assert not _DUP_PAREN.search(subject), subject

    def test_digest_subject_unresolved_no_dup(self, app, make_user):
        from services.artifacts.earnings_prebrief_service import (
            EarningsPreBriefService,
        )

        user = make_user(email="digest-subject-miss@test.com")
        user_obj = db_get_user(user["id"])

        svc = EarningsPreBriefService()
        entries = [{"ticker": "ZZZZ"}]

        captured = {}

        class _CapturingSender:
            def send(self, *_args, **kwargs):
                captured.update(kwargs)
                return True

        with patch(
            "services.name_resolver.resolve_stock_name_with_db",
            return_value=None,
        ), patch(
            "services.email.EmailSender", _CapturingSender,
        ):
            svc._send_digest_email(user_obj, "<html/>", entries)

        subject = captured.get("subject", "")
        assert "ZZZZ" in subject, subject
        assert not _DUP_PAREN.search(subject), subject


# ── per-user email subject (single artifact send path) ──────────────────────


class TestEarningsPrebriefSingleEmailSubject:
    """``_send_email`` (single-ticker per-user path) must also honour the
    label rule.
    """

    def test_single_email_subject_uses_label(self, app, make_user):
        from services.artifacts.earnings_prebrief_service import (
            EarningsPreBriefService,
        )

        user = make_user(email="single-email-subject@test.com")
        user_obj = db_get_user(user["id"])

        svc = EarningsPreBriefService()
        data = {"ticker": "005930.KS"}

        captured = {}

        class _CapturingSender:
            def send(self, *_args, **kwargs):
                captured.update(kwargs)
                return True

        with patch(
            "services.name_resolver.resolve_stock_name_with_db",
            return_value="삼성전자",
        ), patch(
            "services.email.EmailSender", _CapturingSender,
        ):
            svc._send_email(user_obj, b"", "<html/>", data)

        subject = captured.get("subject", "")
        assert "삼성전자 (005930.KS)" in subject, subject
        assert not _DUP_PAREN.search(subject), subject


# ── helpers ─────────────────────────────────────────────────────────────────


def db_get_user(uid):
    """Use Session.get() to silence the SQLAlchemy 2.0 legacy warning."""
    from extensions import db
    from models import User
    return db.session.get(User, uid)
