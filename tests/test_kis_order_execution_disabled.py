"""KIS order execution stays disabled. 자본시장법 (투자일임업).

This is the boundary that keeps the operator out of 투자일임업 territory, and
until 2026-09-10 it had **zero tests** — verified by grepping tests/ for
KIS_READ_ONLY. The only thing watching it was a shell hook in
~/.claude/memory_tools/memory_audit.sh, which grepped for
``def place_order|execute_trade|submit_order``. The real names are
``buy_order``, ``sell_order`` and ``_place_order``, so it matched nothing and
reported "주문 메서드 0건 (0=read-only 정상)" every single day. It would have
reported exactly the same thing if someone had re-enabled all three.

That hook also had the wrong model of the risk. Order methods are not a
regression signal — they exist on purpose, as named refusals, so that a caller
gets a clear error instead of an AttributeError. What makes the boundary hold
is that every one of them refuses. That is what these tests pin.

Structured so a NEW order method cannot slip past: the roster is asserted
explicitly, so adding a fourth fails here until someone looks at it.
"""
from __future__ import annotations

import inspect
import re

import pytest

from services.kis.service import KISService

# Every order-shaped method on the service. Adding one without adding it here
# fails test_no_unreviewed_order_method_appeared — deliberately.
ORDER_METHODS = ("buy_order", "sell_order", "_place_order")

# What a refusal must say. The code is what callers branch on.
REFUSAL_CODE = "KIS_READ_ONLY"


@pytest.fixture()
def svc() -> KISService:
    # __init__ reads env and sets available=False without credentials; it makes
    # no network call, so this is safe in a unit test.
    return KISService()


@pytest.mark.parametrize("name", ORDER_METHODS)
def test_order_method_refuses(svc, name):
    """Calling it returns a refusal — not a fill, not an exception."""
    method = getattr(svc, name)
    if name == "_place_order":
        result = method("005930", 1, 70000, "00", "buy")
    else:
        result = method("005930", 1)

    assert isinstance(result, dict), f"{name} returned {type(result)!r}"
    assert result.get("ok") is False, f"{name} did not refuse: {result!r}"
    assert result.get("code") == REFUSAL_CODE, f"{name}: {result!r}"


@pytest.mark.parametrize("name", ORDER_METHODS)
def test_order_method_makes_no_request(svc, name):
    """A refusal that still hits the broker is not a refusal.

    Source-level rather than mock-level on purpose: a mock only proves this
    one call path is clean, while the source proves there is no request in the
    method at all — including one behind a branch a test happens not to take.
    """
    src = inspect.getsource(getattr(svc, name))
    body = "\n".join(
        line for line in src.splitlines()
        if not line.lstrip().startswith("#")
    )
    # Strip the docstring: it discusses orders at length, in two languages.
    body = re.sub(r'""".*?"""', "", body, flags=re.S)

    for forbidden in ("requests.", "urlopen(", "httpx.", "session.post",
                      "self._request", "aiohttp"):
        assert forbidden not in body, f"{name} still calls out: {forbidden}"


def test_no_unreviewed_order_method_appeared():
    """The roster is the point.

    A widened grep would have reported three matches and cried wolf forever,
    because the methods are supposed to exist. Pinning the exact set instead
    means a FOURTH one — `submit_order`, `execute_trade`, whatever it is
    called — fails here, which is the case the old hook was blind to.
    """
    found = {
        name for name, _ in inspect.getmembers(KISService, inspect.isfunction)
        if "order" in name.lower()
    }
    # get_order_status is a read: it fetches fills the user already made.
    found.discard("get_order_status")

    assert found == set(ORDER_METHODS), (
        f"order-method roster changed: {sorted(found)}. "
        f"If this is a new refusal, add it to ORDER_METHODS. If it executes "
        f"an order, it must not exist — 자본시장법 투자일임업."
    )


def test_the_refusal_tells_the_user_what_to_do_instead():
    """A dead end with no exit is a bug even when the refusal is correct."""
    result = KISService().buy_order("005930", 1)
    assert "KIS app" in (result.get("error") or ""), result
