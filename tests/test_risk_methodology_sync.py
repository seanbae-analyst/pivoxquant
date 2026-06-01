"""Drift guard — RISK_METHODOLOGY catalog ↔ routes/risk_quant.py verbatim.

The methodology page (``/api/methodology``) surfaces ``RISK_METHODOLOGY`` as
the reproducibility anchor for the risk surface. Each ``methodology`` string
MUST be the verbatim string the corresponding risk_quant endpoint emits —
otherwise the trust surface would misstate *how* a number is computed
(표시광고법 §3 기만표시). If a risk endpoint changes its wording, this test
fails until the catalog is re-synced. Same discipline as
``tests/test_no_hardcoded_samples.py`` / ``data_source_resolver``.
"""
from __future__ import annotations

import pathlib

from services.quant.risk_methodology import (
    RISK_METHODOLOGY,
    RISK_METHODOLOGY_COUNT,
)

_RISK_QUANT_SRC = (
    pathlib.Path(__file__).resolve().parents[1] / "routes" / "risk_quant.py"
).read_text(encoding="utf-8")


def test_every_methodology_string_present_verbatim_in_risk_quant():
    """Each catalog ``methodology`` is emitted verbatim by risk_quant.py."""
    for r in RISK_METHODOLOGY:
        needle = f'"methodology": "{r["methodology"]}"'
        assert needle in _RISK_QUANT_SRC, (
            f"catalog/risk_quant drift for {r['key']!r}: "
            f"{needle!r} not found in routes/risk_quant.py — re-sync the catalog"
        )


def test_catalog_entries_complete_and_unique():
    """Every entry carries the locked fields; keys are unique."""
    seen: set[str] = set()
    for r in RISK_METHODOLOGY:
        for field in (
            "key", "label_kr", "label_en", "methodology", "academic_source",
        ):
            assert r.get(field), f"risk metric {r.get('key')!r} missing {field}"
        assert r["key"] not in seen, f"duplicate key {r['key']!r}"
        seen.add(r["key"])
    assert len(seen) == RISK_METHODOLOGY_COUNT


def test_no_advisory_language_in_methodology_catalog():
    """Observation-only — measurement descriptions, never directives."""
    banned_ko = ("매수", "매도", "추천", "조언")
    banned_en = (" buy ", " sell ", " hold ", "recommend", "advice")
    for r in RISK_METHODOLOGY:
        blob = " ".join(str(v) for v in r.values())
        for tok in banned_ko:
            assert tok not in blob, f"banned KO {tok!r} in {r['key']!r}"
        padded = f" {blob.lower()} "
        for tok in banned_en:
            assert tok not in padded, f"banned EN {tok!r} in {r['key']!r}"
