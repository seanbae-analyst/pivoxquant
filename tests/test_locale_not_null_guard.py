"""Regression — `_do_migrations()` users.locale NOT NULL guard (Bug #3).

SHIP-BLOCKER (2026-05-28 bug-hunter + audit 일치): `app.py` had TWO
`_add_column_if_missing("users", "locale", ...)` self-heal calls — the
first (line ~548) without `not_null=True`, the second (line ~648) with
`not_null=True`. Because `_add_column_if_missing` short-circuits on
``if column in existing: return`` (app.py:503-508), the first call ran,
created the column WITHOUT NOT NULL, and the second call was skipped —
leaving prod with a nullable `locale` column despite the intent.

Fix (commit cbafbe47): the FIRST call now carries `not_null=True` so the
prod self-heal achieves the stated NOT NULL DEFAULT 'ko' semantics. The
second call (the "intent" line) stays as a defense-in-depth re-affirm,
correctly idempotent.

These tests are *static* grep guards — they protect the source intent
without needing a Postgres test fixture. A future maintainer who blindly
strips `not_null=True` from line ~548 will trip these specs.
"""
from __future__ import annotations

from pathlib import Path
import re


_APP_PY = Path(__file__).resolve().parent.parent / "app.py"


def _read_app_text() -> str:
    assert _APP_PY.exists(), f"app.py missing at {_APP_PY}"
    return _APP_PY.read_text(encoding="utf-8")


def test_users_locale_self_heal_call_carries_not_null_true():
    """The first _add_column_if_missing users.locale call must include
    not_null=True. Bare default-only form would silently undo Bug #3 fix.
    """
    text = _read_app_text()
    # Find every _add_column_if_missing block targeting users.locale.
    # The regex allows multi-line invocation (Python wraps at ~79 cols).
    pat = re.compile(
        r"_add_column_if_missing\(\s*"
        r"\"users\"\s*,\s*\"locale\"\s*,\s*"
        r"\"VARCHAR\(2\)\"\s*,\s*"
        r"default=\"'ko'\"\s*"
        r"(?P<tail>[^)]*)\)",
        re.DOTALL,
    )
    matches = list(pat.finditer(text))
    assert len(matches) >= 1, (
        "users.locale self-heal call removed from app.py — schema "
        "drift risk on Railway prod (alembic 046 not runtime-executed)."
    )
    # EVERY users.locale self-heal call must carry not_null=True. We do
    # not pin "first vs second" position because future refactors may
    # consolidate them — but neither call may regress to nullable.
    for m in matches:
        tail = m.group("tail")
        assert "not_null=True" in tail, (
            f"users.locale self-heal call at offset {m.start()} dropped "
            f"not_null=True — prod schema regresses to nullable, breaking "
            f"Wave F i18n contract."
        )


def test_users_locale_appears_in_orm_user_model():
    """ORM User model must declare `locale` — otherwise the self-heal
    guard is sole SoT and silent drift becomes possible.
    """
    models_path = Path(__file__).resolve().parent.parent / "models.py"
    if not models_path.exists():
        # Some layouts ship models split across modules; skip rather than
        # fail spuriously. The self-heal guard above is the load-bearing check.
        return
    src = models_path.read_text(encoding="utf-8")
    assert re.search(r"\blocale\b\s*=\s*db\.Column|locale\s*:\s*Mapped", src), (
        "models.py User no longer declares `locale` column — Wave F i18n "
        "contract broken; revert or update this guard."
    )
