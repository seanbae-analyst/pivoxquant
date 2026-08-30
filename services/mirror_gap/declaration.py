"""What the user says about themselves, before they see the record.

Three questions, each chosen because a mirror already measures the same
thing. A question the record cannot answer would produce a declaration
with nothing to sit beside, which is just a survey — and every Korean
brokerage is legally required to make the user fill one of those already
(자본시장법 적합성 원칙). Repeating it adds nothing.

Deliberately not a personality classifier. The tree this replaces sorted
users into eight personas across nine dimensions — 4,345 lines to produce
a label. A label is read once and then inert, it reads as true to almost
everyone, and the user already has one from their broker. Three numbers
they can be wrong about are worth more than a bucket they can agree with.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

# Answer keys are stable identifiers — they are stored per user and
# compared against months later, so renaming one silently invalidates
# every declaration already on file.
HoldLonger = Literal["profit", "loss", "same", "unsure"]


@dataclass(frozen=True)
class Question:
    key: str
    prompt: str
    helper: str
    kind: Literal["days", "count", "choice"]
    choices: tuple[tuple[str, str], ...] = ()


DECLARATION_QUESTIONS: tuple[Question, ...] = (
    Question(
        key="hold_days",
        prompt="한 종목을 평균 얼마나 보유한다고 생각하세요?",
        helper="정확하지 않아도 됩니다. 지금 떠오르는 대로 답해주세요.",
        kind="days",
    ),
    Question(
        key="trades_per_month",
        prompt="한 달에 몇 번 정도 매매하시나요?",
        helper="매수와 매도를 합쳐서입니다.",
        kind="count",
    ),
    Question(
        # The disposition effect, asked without naming it. Naming it would
        # tell the user which answer is the "wrong" one, and the value of
        # this question is entirely in being answered honestly first.
        key="hold_longer",
        prompt="수익이 난 종목과 손실이 난 종목 중, 어느 쪽을 더 오래 들고 계신 것 같나요?",
        helper="느낌대로 골라주세요.",
        kind="choice",
        choices=(
            ("profit", "수익 난 쪽을 더 오래"),
            ("loss", "손실 난 쪽을 더 오래"),
            ("same", "비슷하다"),
            ("unsure", "잘 모르겠다"),
        ),
    ),
)

_BY_KEY = {q.key: q for q in DECLARATION_QUESTIONS}

# A declaration is a memory of a belief, not a measurement, so the bounds
# are only wide enough to reject nonsense that would make a gap meaningless
# — a negative holding period, or a claim of a thousand trades a day.
_MAX_HOLD_DAYS = 3650      # ten years
_MAX_TRADES_PER_MONTH = 1000


@dataclass
class Declaration:
    """One user's stated beliefs, captured before they saw any mirror."""

    hold_days: float | None = None
    trades_per_month: float | None = None
    hold_longer: HoldLonger | None = None

    @property
    def is_empty(self) -> bool:
        return (
            self.hold_days is None
            and self.trades_per_month is None
            and self.hold_longer is None
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "hold_days": self.hold_days,
            "trades_per_month": self.trades_per_month,
            "hold_longer": self.hold_longer,
        }

    @classmethod
    def from_answers(cls, answers: dict[str, Any]) -> tuple["Declaration", list[str]]:
        """Build from raw form input.

        Returns ``(declaration, rejected_keys)``. An unusable answer is
        dropped and named rather than coerced — a declaration is the fixed
        half of the comparison, so a value quietly rounded into range would
        misstate the gap forever after.
        """
        if not isinstance(answers, dict):
            return cls(), list(_BY_KEY)

        declaration = cls()
        rejected: list[str] = []

        hold = _positive_number(answers.get("hold_days"), _MAX_HOLD_DAYS)
        if hold is None:
            if answers.get("hold_days") is not None:
                rejected.append("hold_days")
        else:
            declaration.hold_days = hold

        trades = _positive_number(answers.get("trades_per_month"), _MAX_TRADES_PER_MONTH)
        if trades is None:
            if answers.get("trades_per_month") is not None:
                rejected.append("trades_per_month")
        else:
            declaration.trades_per_month = trades

        longer = answers.get("hold_longer")
        valid = {c[0] for c in _BY_KEY["hold_longer"].choices}
        if isinstance(longer, str) and longer.strip() in valid:
            declaration.hold_longer = longer.strip()  # type: ignore[assignment]
        elif longer is not None:
            rejected.append("hold_longer")

        return declaration, rejected


def _positive_number(raw: Any, ceiling: float) -> float | None:
    """Coerce to a number in (0, ceiling]. Returns None for anything else."""
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value != value or value in (float("inf"), float("-inf")):  # NaN / inf
        return None
    if value <= 0 or value > ceiling:
        return None
    return value
