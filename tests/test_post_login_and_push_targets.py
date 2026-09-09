"""Where we send a reader after login, and where a push notification lands.

Both are one-way trips. A wrong post-login redirect drops someone straight
after OAuth with no page to go back to, and a push notification is a link
tapped on a phone — if it 404s there is no back button to a page the reader
never reached.

Both were wrong, and neither had a test:

  * ``routes.auth._safe_next`` — the open-redirect guard — had ZERO tests
    (grep over tests/, 2026-09-07). It defaulted every login to ``/home``,
    a route the 2026-08-31 prune deleted, so each OAuth sign-in paid a 308
    before reaching ``/mirror``. The function's own docstring says its job is
    mapping dead routes onto live ones; its fallback was a dead route.
  * ``services.push_service`` deep-linked trade confirmations to ``/trades``,
    which prod answers with a hard **404** — no redirect covers it.

The open-redirect half of that guard matters more than the tidiness half, and
it was equally untested. Both halves are pinned here.
"""
from __future__ import annotations

import pytest

from routes.auth import _safe_next, _POST_LOGIN_DEFAULT
from services import push_service


# Routes the prune deleted. next.config.ts redirects most of them, which is
# why pointing at one is invisible in a browser and needs a test instead.
DELETED = ("/home", "/reports", "/risk", "/discover", "/watchlist",
           "/companion", "/market", "/detail", "/alerts", "/trades")


class TestOpenRedirectDefence:
    """The half that is a security boundary, not a tidiness question."""

    @pytest.mark.parametrize("hostile", [
        "//evil.com",
        "//evil.com/path",
        "https://evil.com",
        "http://evil.com/steal",
        "javascript:alert(1)",
        "mailto:a@b.c",
        "evil.com",
        "\\\\evil.com",
    ])
    def test_offsite_targets_are_refused(self, hostile):
        out = _safe_next(hostile)
        assert out == _POST_LOGIN_DEFAULT
        assert "://" not in out and not out.startswith("//")

    @pytest.mark.parametrize("junk", [None, "", 0, [], {}, 12345])
    def test_non_string_and_empty_fall_back(self, junk):
        assert _safe_next(junk) == _POST_LOGIN_DEFAULT

    def test_a_scheme_hidden_behind_a_query_string_is_still_refused(self):
        # path_only strips the query, so the scheme check must run first.
        assert _safe_next("https://evil.com/?next=/mirror") == _POST_LOGIN_DEFAULT


class TestLiveDestinations:
    def test_the_default_is_not_itself_a_deleted_route(self):
        """The bug this file was written for: the fallback of the
        dead-route mapper was a dead route."""
        assert _POST_LOGIN_DEFAULT not in DELETED

    def test_legitimate_next_is_preserved(self):
        for ok in ("/journal", "/portfolio", "/pre-trade", "/settings"):
            assert _safe_next(ok) == ok

    def test_query_strings_survive(self):
        assert _safe_next("/journal?tab=mirror") == "/journal?tab=mirror"

    @pytest.mark.parametrize("legacy", ["/landing", "/landing/", ""])
    def test_retired_routes_map_onto_a_live_one(self, legacy):
        assert _safe_next(legacy) == _POST_LOGIN_DEFAULT

    def test_beta_gate_link_goes_to_the_public_root(self):
        # The beta gate was retired 2026-09-04; old links still arrive.
        assert _safe_next("/beta") == "/"


class TestPushDeepLinks:
    def test_no_push_target_is_a_deleted_route(self):
        for name in ("PUSH_URL_ALERTS", "PUSH_URL_TRADES"):
            target = getattr(push_service, name)
            assert target not in DELETED, f"{name} points at a pruned route"
            assert target.startswith("/")

    def test_trade_confirmations_land_where_trades_are_shown(self):
        """RecentTransactionsBlock renders on /portfolio. /trades is a 404."""
        assert push_service.PUSH_URL_TRADES == "/portfolio"

    def test_no_module_level_literal_reintroduces_the_old_paths(self):
        """Three copies of one path is how the deleted /home reached all five
        emails. Keep these named in one place."""
        import pathlib
        src = pathlib.Path(push_service.__file__).read_text()
        body = "\n".join(
            l for l in src.splitlines()
            if not l.lstrip().startswith("#")
        )
        assert '"/trades"' not in body
        assert '"/alerts"' not in body
