"""mirror_gap — what the user believes, next to what their record shows.

The behavioural mirrors already report the record. This package supplies
the other half: what the user *said* about themselves before seeing it,
and the distance between the two.

That distance is the product's only claim. A single-shot read of someone's
trades is a commodity — a general assistant does it for free. What a chat
session cannot do is hold what you declared in March and put it beside
what you did by August. So the declaration is captured first, stored, and
never revised silently.

Two rules carried over from ``services/behavior``:

**Never judge.** A gap is two numbers side by side, not a verdict.
"평균 3개월이라 답하셨습니다. 기록은 4일입니다." is a fact the user can
check. "당신은 성급합니다" is an opinion they can argue with, and arguing
with it is how the observation gets dismissed.

**Never state a gap the record cannot support.** Every mirror refuses to
report below its own sample floor, and this package refuses right along
with it. A confident-sounding gap computed from five trades is worse than
silence, because the user has no way to know it was noise.
"""

from services.mirror_gap.declaration import (  # noqa: F401
    DECLARATION_QUESTIONS,
    Declaration,
)
from services.mirror_gap.gap import (  # noqa: F401
    Gap,
    GapReport,
    compute_gap_report,
)

__all__ = [
    "DECLARATION_QUESTIONS",
    "Declaration",
    "Gap",
    "GapReport",
    "compute_gap_report",
]
