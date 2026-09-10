"""Modules removed by the prunes must not be importable.

Found 2026-09-10: ``import services.ai`` SUCCEEDED locally. The package's
files were deleted in the 2026-09-01 AI removal, but the directory survived
holding nothing but ``__pycache__`` — and Python 3 treats a bare directory as
a namespace package, so the import resolved to a module object whose
``__file__`` was ``None``.

That is the worst shape a leftover can take. A fresh clone has no such
directory (git tracks zero files under it), so the same import raises
ModuleNotFoundError in production. Code written against it would pass every
local test and fail only after deploy. The nightly "삭제 잔해" check would not
have caught it either: that greps for import STATEMENTS, and finds none until
somebody writes one — by which point the trap has already been sprung.

Nothing imports these today. This test exists so that stays true, and so a
stale directory cannot quietly make one of them importable again.
"""
from __future__ import annotations

import importlib

import pytest

# Everything the 2026-04 → 2026-09 prunes removed. Sources: CLAUDE.md §기술
# 스택 (AI), §구조 (quant, autotrade), 함정 §7 (CAUS / sim_onboard), and the
# 08-31 artefact prune.
DELETED_MODULES = [
    "services.ai",          # 2026-09-01, AI removed entirely
    "services.quant",       # 2026-08-31
    "services.broker",
    "services.mock_data",
    "services.trading",
    "services.artifacts",   # 2026-08-31 artefact prune
    "routes.artifacts",
    "routes.sim_onboard",   # 2026-09-01, with CAUS
    "routes.daytrade",
    "agent_worker",         # autonomous worker, never had a consumer
]


@pytest.mark.parametrize("name", DELETED_MODULES)
def test_module_is_not_importable(name):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(name)


@pytest.mark.parametrize("name", DELETED_MODULES)
def test_no_namespace_package_shell_remains(name):
    """The specific failure that motivated this file.

    The raises() above already covers it; this exists for the message. When it
    fails the cause is almost always an empty directory left behind by a
    delete, and the fix is to remove the directory — not to touch any code.
    """
    try:
        mod = importlib.import_module(name)
    except ModuleNotFoundError:
        return
    raise AssertionError(
        f"{name} imports as a namespace package (__file__={mod.__file__!r}). "
        f"A directory for it still exists — most likely holding only "
        f"__pycache__ — so this passes locally and raises in production. "
        f"Delete the directory."
    )
