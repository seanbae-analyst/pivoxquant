"""AI integration package — Claude API + AI models.

Originally at project root (ai_service.py, ai_models.py); consolidated
2026-05-02 into this subpackage for clearer organization.
"""
from services.ai.service import AIService, MODEL, SYSTEM_PROMPT
from services.ai.models import (
    EarningsCallToneAnalyzer,
    AISectorRotation,
    AIRiskSummary,
)

__all__ = [
    "AIService",
    "MODEL",
    "SYSTEM_PROMPT",
    "EarningsCallToneAnalyzer",
    "AISectorRotation",
    "AIRiskSummary",
]
