# DEPRECATED 2026-05-30: AI 점수화 폐기(DECISIONS). 크론·API 비활성. 물리 컬럼
# drop 은 prod self-heal 함정 때문에 careful 마이그레이션으로 후속. 거울/export/
# persona benchmark 호환 위해 모델 보존.
"""Weekly behavioural-score package — Feature 7."""
from .scorer import (
    compute_weekly_score,
    run_weekly_for_all_users,
)

__all__ = ["compute_weekly_score", "run_weekly_for_all_users"]
