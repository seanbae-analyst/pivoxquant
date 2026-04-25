"""Quant Composer service package.

Public surface
--------------
- :mod:`services.quant.model_catalog` — the 40-model metadata catalog.
- :mod:`services.quant.composer`      — user-composition apply/validate
  helpers used by ``engine.py`` and ``routes/quant_composer.py``.

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

__all__ = [
    "MODEL_CATALOG",
    "MODEL_BY_NAME",
    "CATEGORIES",
    "apply_user_composition",
    "validate_composition",
    "get_persona_preset",
    "apply_persona_preset",
    "PERSONA_QUANT_PRESETS",
]
