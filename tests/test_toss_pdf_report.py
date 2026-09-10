"""PivoxReport as a PDF attachment.

The attachment exists because a link does not travel: opened from an inbox
there is usually no session behind it, and the published page is private. The
tests here are about that contract — the PDF must be a real PDF, must be the
paper document rather than the app-chrome one, and must never take the send
down with it when the host cannot build one.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime

import pytest

from services.toss import pdf_report
from services.toss.mirror_report import build_mirror_report

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "toss", "sample_raw_history.json")


@pytest.fixture
def report():
    with open(FIX, encoding="utf-8") as fh:
        raw = json.load(fh)
    return build_mirror_report(
        account=raw["account"], holdings=raw["holdings"], closed_orders=raw["closed_orders"],
        open_orders=raw["open_orders"], fx=raw["fx"], history_since=raw["history_since"],
        window_days=90, names=raw["names"], prices=raw.get("prices"),
        as_of=datetime.fromisoformat(raw["fetched_at"]),
    )


def test_offline_drops_every_remote_stylesheet_so_a_boxed_in_host_still_renders(report):
    from services.toss.html_report import render_mirror_html
    stripped = pdf_report._strip_remote_links(render_mirror_html(report, paper=True))
    assert "https://" not in stripped
    # paper wraps each Korean word in an unbreakable span (see _keep_all), so
    # the title is read back through the same lens the renderer sees it with
    assert "기록이 되비추는 것" in re.sub(r"</?span[^>]*>", "", stripped)


def test_a_host_without_weasyprint_loses_the_attachment_and_nothing_else(report, monkeypatch):
    """The digest is the deliverable; the PDF is the better copy of it. A host
    that cannot build one must still send."""
    import builtins
    real = builtins.__import__

    def no_weasyprint(name, *a, **kw):
        if name == "weasyprint":
            raise ImportError("no libpango here")
        return real(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", no_weasyprint)
    assert pdf_report.available() is False
    assert pdf_report.render_pdf(report) is None


@pytest.mark.skipif(not pdf_report.available(), reason="weasyprint's native libs are not installed here")
def test_the_pdf_is_the_paper_document(report):
    blob = pdf_report.render_pdf(report, offline=True)
    assert blob and blob.startswith(b"%PDF-")
    assert len(blob) > 5_000
