"""Every shipping mail's links must point at routes that still exist.

Found 2026-09-07 by hunting, not by a test: all five mails that actually
ship — welcome, d3_guide, d7_summary, d30_summary, inactive_nudge — put
``/home`` in their primary call to action. ``/home`` was deleted; the
frontend answers it with a 308 to ``/mirror``. From the nudge's own
hard-coded default the measured chain was ``pivoxquant.com/home`` → 307 →
``www`` → 308 → ``/mirror``: two hops, and a deleted surface named in the
one link the reader is most likely to press. CLAUDE.md's standing rule is
"삭제된 표면을 가리키는 링크·문구를 만들지 마라".

Nothing caught it because nothing rendered these templates outside the
dispatch path, and the dispatch path is flag-gated off. These tests render
them directly, so the templates are checked whether or not the flags are on.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

# Routes the 2026-08-31 prune removed. next.config.ts redirects them, so a
# link still "works" and the breakage is invisible in a browser — which is
# exactly why it needs a test rather than a click-through.
DELETED_ROUTES = ("/home", "/detail/", "/reports", "/risk", "/discover",
                  "/watchlist", "/companion", "/market")


def _user():
    return SimpleNamespace(
        id=1, name="배상현", email="seanbae1521@gmail.com", is_simulated=False,
    )


def _shipping_bodies() -> list[tuple[str, str, str]]:
    """(label, html, txt) for every mail that can actually be sent today."""
    from services.email import onboarding_sequence as ob
    from services.email import retention_sequence as rt
    from services.customer import inactive_nudge as nz

    out: list[tuple[str, str, str]] = []
    u = _user()

    # active_sequence() excludes the Stage-1 d7_pro_nudge while paid plans are
    # off — deliberately follow that, so this asserts on what ships, not on
    # what is parked in the tree.
    for step in ob.active_sequence():
        html, txt = ob._render(step.template_basename, user=u)
        out.append((f"onboarding/{step.template_basename}", html, txt))

    record = {
        "window_days": 7,
        "lines": ["지난 7일 동안 3번 멈춰 서서 기록을 남기셨습니다."],
    }
    for base in ("d7_summary", "d30_summary"):
        html, txt = rt._render(
            base, user=u,
            unsubscribe_url="https://www.pivoxquant.com/api/email/unsubscribe?token=T",
            record=record,
        )
        out.append((f"retention/{base}", html, txt))

    html, txt = nz._render_email(
        "배상현",
        unsubscribe_url="https://www.pivoxquant.com/api/email/unsubscribe?token=T",
    )
    out.append(("customer/inactive_nudge", html, txt))
    return out


_BODIES = _shipping_bodies()
# ids= keeps a failure readable: without it pytest renders the entire rendered
# HTML body into the test id and the assertion message is lost in it.
_IDS = [b[0] for b in _BODIES]


@pytest.mark.parametrize("label,html,txt", _BODIES, ids=_IDS)
def test_no_link_points_at_a_deleted_route(label, html, txt):
    for body, kind in ((html, "html"), (txt, "txt")):
        for dead in DELETED_ROUTES:
            assert dead not in body, f"{label} ({kind}) links to deleted {dead}"


@pytest.mark.parametrize("label,html,txt", _BODIES, ids=_IDS)
def test_no_placeholder_survives_rendering(label, html, txt):
    """An unsubstituted {{ token }} ships as literal braces to the reader."""
    for body, kind in ((html, "html"), (txt, "txt")):
        assert "{{" not in body and "}}" not in body, f"{label} ({kind})"


@pytest.mark.parametrize("label,html,txt", _BODIES, ids=_IDS)
def test_no_internal_editor_note_ships(label, html, txt):
    """d7_pro_nudge carries a bracketed STAGE-1 note meant for whoever revives
    it. It is correctly excluded from active_sequence() today; if a future
    edit lets a note-bearing template through, the reader sees the note."""
    for body, kind in ((html, "html"), (txt, "txt")):
        assert "[STAGE" not in body, f"{label} ({kind}) leaks an internal note"
        assert "TODO" not in body and "FIXME" not in body, f"{label} ({kind})"


def test_dashboard_url_has_exactly_one_implementation():
    """Three copies existed and had already diverged (the nudge hard-coded the
    apex, the other two derived it). CLAUDE.md §10's lesson, same shape."""
    from services.email import urls, onboarding_sequence, retention_sequence

    assert onboarding_sequence._dashboard_url() == urls.dashboard_url()
    assert retention_sequence._dashboard_url() == urls.dashboard_url()
    assert onboarding_sequence._pricing_url() == urls.pricing_url()


def test_dashboard_url_names_the_live_home_screen():
    from services.email.urls import dashboard_url
    assert dashboard_url().endswith("/mirror")
