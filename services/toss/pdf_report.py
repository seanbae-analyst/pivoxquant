"""PivoxReport as a PDF — the whole report, in an attachment.

A link is only as reachable as the session behind it. Opened from an inbox on
a phone there is usually no session at all, and a private page renders as
nothing. A PDF arrives with the mail, so the report is readable wherever the
mail is: no login, no content-security policy, no webfont host to reach.

It renders :func:`services.toss.html_report.render_mirror_html` in its paper
mode, which is the product's own report surface — the report is the same
document either way, only its ground changes.

WeasyPrint is import-time optional: the digest must still send on a box that
cannot build it, so :func:`render_pdf` says so rather than raising at import.
"""
from __future__ import annotations

import logging

from services.toss.html_report import render_mirror_html

logger = logging.getLogger(__name__)

# The stylesheet reaches Google Fonts. WeasyPrint fetches it synchronously, so
# on a box with no egress the render blocks until the socket gives up. The
# families all name a real fallback, so a failed fetch costs the display face
# and nothing else — but it must not cost thirty seconds either.
_FETCH_TIMEOUT = 8


def available() -> bool:
    try:
        import weasyprint  # noqa: F401
    except Exception:  # pragma: no cover - depends on the host's libs
        return False
    return True


def render_pdf(rep: dict, *, offline: bool = False) -> bytes | None:
    """The report as PDF bytes, or ``None`` when WeasyPrint cannot run here.

    ``offline=True`` drops the webfont link before rendering, which is what a
    box without egress wants: the four type roles fall back to the families
    already named beside them and the render returns immediately.
    """
    try:
        from weasyprint import HTML
    except Exception as exc:  # pragma: no cover - depends on the host's libs
        logger.warning("weasyprint unavailable, sending the digest without a PDF: %s", exc)
        return None

    page = render_mirror_html(rep, paper=True)
    if offline:
        page = _strip_remote_links(page)
    try:
        return HTML(string=page, base_url=".").write_pdf()
    except Exception as exc:  # pragma: no cover - a render failure must not eat the send
        logger.warning("PDF render failed, sending the digest without it: %s", exc)
        return None


def _strip_remote_links(page: str) -> str:
    """Drop the stylesheet links. Every family named in them is followed by a
    real fallback, so what this costs is the display face, not the document."""
    return "".join(line for line in page.splitlines(keepends=True)
                   if not (line.startswith("<link ") and "http" in line))
