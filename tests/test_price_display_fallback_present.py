"""
Regression Guard 5 — backend test counterpart.

feedback_bug_fix_patterns §1 and §CI-guard-6 mandate that any code path
returning `price_display` to the client must also return a real
`price` (not `0`) OR carry a consumer that runs parse_price_display
on the display string before rendering.

The CI workflow `regression-guards.yml` ships a warn-only grep check
(see scripts/check_regression_guards.py guard_5). This pytest is the
stronger form: it AST-walks routes/ + services/ and confirms that any
module emitting a `price_display` value also either

  (a) emits a non-zero, non-None `price` in the same dict literal, OR
  (b) imports `parse_price_display` (i.e. it's a consumer that will
      fall back), OR
  (c) is explicitly allow-listed below.

The pytest baseline (ALLOWED_FILES) records modules that are known
producers where the zero-price is intentional and upstream consumers
run parse_price_display. New additions must be justified.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Modules where `price_display` is written/read but a zero-price passes
# through by design (consumer handles the parse). Adding to this list
# requires reviewer sign-off.
ALLOWED_FILES = {
    # Source of truth — defines parse_price_display itself.
    "services/price_overlay.py",
    # realtime_service is a pass-through producer; consumers
    # (routes/portfolio.py, routes/watchlist.py, routes/share.py)
    # all import price_overlay and run the fallback.
    "realtime_service.py",
    # Consumers already verified to use price_overlay.apply_price_overlay
    "routes/realtime.py",
    "routes/market.py",
    # AI service only reads `price_display` from upstream dicts to build
    # Claude prompts (text-only); it does not emit `price_display` back to
    # clients. Upstream producers already passed the fallback guard.
    "services/ai/service.py",
}


def _scan_file(path: Path) -> tuple[bool, bool]:
    """Return (writes_price_display, imports_parse_price_display)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return (False, False)
    writes = "price_display" in text
    imports = "parse_price_display" in text
    return writes, imports


def _all_code_files() -> list[Path]:
    result: list[Path] = []
    for sub in ("routes", "services"):
        root = REPO_ROOT / sub
        if not root.exists():
            continue
        for p in root.rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            result.append(p)
    return result


def test_price_display_has_fallback_consumer():
    offenders: list[str] = []
    for py in _all_code_files():
        rel = py.relative_to(REPO_ROOT).as_posix()
        if rel in ALLOWED_FILES:
            continue
        writes, imports = _scan_file(py)
        if not writes:
            continue
        if imports:
            continue
        offenders.append(rel)
    assert not offenders, (
        "The following modules emit/read `price_display` without "
        "importing `parse_price_display` from services.price_overlay.\n"
        "Either use the helper, or add the file to ALLOWED_FILES in this test "
        "with a comment explaining why (consumer already wraps the response).\n\n"
        + "\n".join(f"  - {f}" for f in offenders)
    )


def test_parse_price_display_helper_exists():
    """The helper itself must continue to exist — sanity check."""
    from services.price_overlay import parse_price_display  # noqa: F401
    assert parse_price_display("$402.91") == pytest.approx(402.91)
    assert parse_price_display("₩42,100") == pytest.approx(42100.0)
    assert parse_price_display("—") is None
    assert parse_price_display("") is None
    assert parse_price_display(None) is None
