"""Quant service package — what survives the 2026-08-31 prune.

The product is the record: 기록 → 거울. Scoring a universe, screening it,
backtesting a strategy over it and defending a position in it are all things
this product no longer does, so the modules that did them are gone:

    engine.py (4-pillar QuantEngine)      models.py (16 strategy classes)
    risk_defense.py (7-Layer)             signals.py (behavioural signals)
    backtester.py                         canslim.py
    indicators.py                         composer.py / model_catalog.py

What is left is the arithmetic the portfolio surface actually needs to
describe a book the user already holds.

Public surface
--------------
- :mod:`services.quant.risk_metrics` — GKYZ, ComponentES, Sortino, etc.
- :mod:`services.quant.portfolio`    — HRP, MaxDiversification, ERC, MinVar,
                                       TailRiskParity.

This package never originates a directive. Every description is
observation-only (per ``services.legal.forbidden_terms``) and every public
route surface goes through ``legal_filter.scrub_text`` before returning to
the user.
"""

from .risk_metrics import (
    GKYZVolatility,
    LedoitWolfShrinkage,
    ComponentES,
    ConditionalDrawdown,
    TailRatio,
    SortinoByPosition,
)
from .portfolio import (
    HRP,
    TailRiskParity,
    MaxDiversification,
    EqualRiskContribution,
    MinVariance,
)

__all__ = [
    # risk
    "GKYZVolatility",
    "LedoitWolfShrinkage",
    "ComponentES",
    "ConditionalDrawdown",
    "TailRatio",
    "SortinoByPosition",
    # portfolio
    "HRP",
    "TailRiskParity",
    "MaxDiversification",
    "EqualRiskContribution",
    "MinVariance",
]
