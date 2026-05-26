"""Quant Composer service package.

Public surface
--------------
- :mod:`services.quant.model_catalog` — the 40-entry (39 active) metadata catalog.
- :mod:`services.quant.composer`      — user-composition apply/validate
  helpers used by ``services.quant.engine`` and ``routes/quant_composer.py``.
- :mod:`services.quant.engine`        — QuantEngine (4-pillar scoring, discover pool)
- :mod:`services.quant.models`        — 16 quant strategy classes
- :mod:`services.quant.risk_defense`  — 7-Layer RiskDefenseSystem
- :mod:`services.quant.risk_metrics`  — GKYZ, ComponentES, Sortino, etc.
- :mod:`services.quant.portfolio`     — HRP, MaxDiversification, ERC, MinVar, TailRiskParity
- :mod:`services.quant.signals`       — Behavioral signals (Disposition, Herding, Anchoring, etc.)
- :mod:`services.quant.backtester`    — Backtester (transaction costs, Sharpe/Sortino/Calmar)
- :mod:`services.quant.canslim`       — CANSLIMScreener (7-factor)
- :mod:`services.quant.indicators`    — AdditionalIndicators, AdditionalFundamentals

This package never originates a directive. All model descriptions are
observation-only (per ``services.legal.forbidden_terms``) and every
public route surface goes through ``legal_filter.scrub_text`` before
returning to the user.
"""
from .model_catalog import MODEL_CATALOG, MODEL_BY_NAME, CATEGORIES
from .composer import (
    apply_user_composition,
    validate_composition,
    get_persona_preset,
    apply_persona_preset,
    PERSONA_QUANT_PRESETS,
)

# Quant engine (top-level)
from .engine import QuantEngine

# Quant strategy models (16 classes)
from .models import (
    StatArb,
    MeanReversion,
    MomentumBreakout,
    VolatilityRegime,
    RegimeSwitching,
    CrossAssetMomentum,
    VIXStrategy,
    MLSignal,
    AdaptiveParams,
    VarianceRatioFilter,
    TSMOM,
    FiftyTwoWeekHigh,
    DonchianBreakout,
    DualMomentum,
    CorrelationRegime,
    InterestRateRegime,
)

# Risk defense system
from .risk_defense import RiskDefenseSystem

# Risk metrics
from .risk_metrics import (
    GKYZVolatility,
    LedoitWolfShrinkage,
    ComponentES,
    ConditionalDrawdown,
    TailRatio,
    SortinoByPosition,
)

# Portfolio optimization
from .portfolio import (
    HRP,
    TailRiskParity,
    MaxDiversification,
    EqualRiskContribution,
    MinVariance,
)

# Behavioral signals
from .signals import (
    DispositionEffect,
    HerdingIntensity,
    SentimentPriceDivergence,
    OrderFlowImbalance,
    AnchoringBias,
)

# Backtester
from .backtester import Backtester

# CANSLIM screener
from .canslim import CANSLIMScreener

# Additional indicators / fundamentals
from .indicators import AdditionalIndicators, AdditionalFundamentals

__all__ = [
    # composer / catalog
    "MODEL_CATALOG",
    "MODEL_BY_NAME",
    "CATEGORIES",
    "apply_user_composition",
    "validate_composition",
    "get_persona_preset",
    "apply_persona_preset",
    "PERSONA_QUANT_PRESETS",
    # engine
    "QuantEngine",
    # models
    "StatArb",
    "MeanReversion",
    "MomentumBreakout",
    "VolatilityRegime",
    "RegimeSwitching",
    "CrossAssetMomentum",
    "VIXStrategy",
    "MLSignal",
    "AdaptiveParams",
    "VarianceRatioFilter",
    "TSMOM",
    "FiftyTwoWeekHigh",
    "DonchianBreakout",
    "DualMomentum",
    "CorrelationRegime",
    "InterestRateRegime",
    # risk
    "RiskDefenseSystem",
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
    # signals
    "DispositionEffect",
    "HerdingIntensity",
    "SentimentPriceDivergence",
    "OrderFlowImbalance",
    "AnchoringBias",
    # backtester
    "Backtester",
    # canslim
    "CANSLIMScreener",
    # indicators
    "AdditionalIndicators",
    "AdditionalFundamentals",
]
