"""Risk-metric methodology catalog — the reproducibility anchor for the
risk surface, mirroring ``model_catalog`` for the quant/signal models.

==============================================================================
Why this exists
==============================================================================
Data-trust strategy Stage 1 (``docs/strategy/DATA_TRUST_STRATEGY.md``): the
strongest proof of trustworthiness is *reproducibility* — "every number we
show can be re-derived from public, licensed data." ``/api/methodology``
already exposes the 40-model quant catalog; this catalog adds the **risk
metrics** (VaR / CDaR / Sortino / Ledoit-Wolf / …) so the methodology page
can state, per metric, *how the number is computed* and *where the method is
published*. The formula is public; the weights stay proprietary.

==============================================================================
Single source of truth (no drift)
==============================================================================
Each ``methodology`` string below is the **verbatim** string emitted by the
corresponding ``routes/risk_quant.py`` endpoint response. They are kept in
sync by ``tests/test_risk_methodology_sync.py`` — if a risk endpoint changes
its methodology wording, that test fails until this catalog is updated. This
is the same truthfulness discipline as ``data_source_resolver`` (표시광고법
§3): the trust surface may only state methods the engine actually uses.

Legal posture: observation-only. No 추천 / 조언 / 매수 / 매도. These are
descriptions of *measurement methods*, never trading directives.
"""
from __future__ import annotations

# Field contract (locked — routes/methodology.py + frontend depend on these):
#   key             : str — stable identifier (frontend React key)
#   label_kr        : str — Korean display name
#   label_en        : str — English display name
#   methodology     : str — VERBATIM match to routes/risk_quant.py (drift-guarded)
#   academic_source : str — published method anchor (reproducibility hook)
RISK_METHODOLOGY: tuple[dict[str, str], ...] = (
    {
        "key": "var",
        "label_kr": "VaR · 최대예상손실",
        "label_en": "Value at Risk",
        "methodology": "parametric (normal) + historical simulation",
        "academic_source": "J.P. Morgan RiskMetrics (1996); historical simulation",
    },
    {
        "key": "equity_curve",
        "label_kr": "손익곡선 · 낙폭",
        "label_en": "Equity Curve / Drawdown",
        "methodology": "historical equity curve reconstruction",
        "academic_source": "Standard historical P&L reconstruction (no forward fill)",
    },
    {
        "key": "component_es",
        "label_kr": "구성요소 ES · 위험기여",
        "label_en": "Component Expected Shortfall",
        "methodology": "Historical Component ES (Euler decomposition)",
        "academic_source": "Acerbi & Tasche (2002), Expected Shortfall; Euler allocation (Tasche 2002)",
    },
    {
        "key": "cdar",
        "label_kr": "CDaR · 조건부낙폭위험",
        "label_en": "Conditional Drawdown at Risk",
        "methodology": "Conditional Drawdown at Risk (historical)",
        "academic_source": "Chekhlov, Uryasev & Zabarankin (2005)",
    },
    {
        "key": "tail_ratio",
        "label_kr": "꼬리비율",
        "label_en": "Tail Ratio",
        "methodology": "|95th| / |5th| percentile ratio",
        "academic_source": "Standard tail-ratio (95th / 5th return percentile)",
    },
    {
        "key": "sortino",
        "label_kr": "소르티노 비율",
        "label_en": "Sortino Ratio",
        "methodology": "Sortino ratio — downside deviation only (MAR = risk-free)",
        "academic_source": "Sortino & Price (1994), downside-risk performance measurement",
    },
    {
        "key": "ledoit_wolf",
        "label_kr": "Ledoit-Wolf 공분산 수축",
        "label_en": "Ledoit-Wolf Covariance Shrinkage",
        "methodology": "Ledoit-Wolf (2004) shrinkage toward scaled identity",
        "academic_source": "Ledoit & Wolf (2004), Honey, I Shrunk the Sample Covariance Matrix",
    },
)

RISK_METHODOLOGY_COUNT = len(RISK_METHODOLOGY)
