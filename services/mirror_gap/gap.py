"""Put the declaration next to the record.

Each gap pairs one stated belief with the mirror that measures the same
thing. Nothing here interprets, scores or ranks — a gap carries both
numbers and the sentence that states them, and stops.

Silence is a valid output and the common one early on. Every mirror
refuses to report below its own sample floor, and a gap inherits that
refusal: with nothing measured there is nothing to sit beside a belief,
and inventing a comparison would break the one promise the product makes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from services.mirror_gap.declaration import Declaration


@dataclass
class Gap:
    """One belief beside one measurement."""

    key: str
    label: str
    declared_text: str
    observed_text: str
    statement: str
    # Ratio of observed to declared, when both are numbers. Reported so a
    # caller can order gaps by size; deliberately not turned into a score,
    # a grade or a percentage "accuracy" — those invite the user to argue
    # with the number instead of looking at it.
    magnitude: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "declared": self.declared_text,
            "observed": self.observed_text,
            "statement": self.statement,
            "magnitude": self.magnitude,
        }


@dataclass
class GapReport:
    gaps: list[Gap] = field(default_factory=list)
    # Questions answered but not yet measurable. Surfaced rather than
    # dropped so the UI can say "아직 기록이 부족합니다" instead of quietly
    # showing less than the user answered.
    pending: list[dict[str, str]] = field(default_factory=list)

    @property
    def has_any(self) -> bool:
        return bool(self.gaps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gaps": [g.to_dict() for g in self.gaps],
            "pending": self.pending,
        }


def _fmt_days(value: float) -> str:
    if value < 1:
        return "하루 미만"
    if value < 30:
        return f"{value:.0f}일"
    months = value / 30.0
    if months < 12:
        return f"약 {months:.0f}개월"
    return f"약 {value / 365.0:.1f}년"


def _fmt_days_pair(a: float, b: float) -> tuple[str, str]:
    """Format two durations in one shared unit.

    The disposition comparison lives or dies on the contrast between the
    two numbers, and "5일 vs 약 2개월" makes the reader convert before they
    can see it. Days stay days for both sides unless both are long enough
    that days would be the harder read.
    """
    if a < 90 or b < 90:
        return f"{a:.0f}일", f"{b:.0f}일"
    return _fmt_days(a), _fmt_days(b)


def _fmt_count(value: float) -> str:
    return f"{value:.0f}회" if value >= 1 else f"{value:.1f}회"


def _magnitude(declared: float, observed: float) -> float | None:
    """How many times the observed value differs from the declared one."""
    if declared <= 0 or observed <= 0:
        return None
    return round(max(declared, observed) / min(declared, observed), 1)


def compute_gap_report(
    declaration: Declaration,
    *,
    turnover: dict | None = None,
    profit_loss: dict | None = None,
) -> GapReport:
    """Pair each declared belief with its mirror.

    ``turnover`` and ``profit_loss`` are the dicts returned by
    ``services.behavior``. Both may be None or report insufficient data;
    every such case yields a *pending* entry rather than a gap.
    """
    report = GapReport()
    if declaration.is_empty:
        return report

    _hold_days_gap(report, declaration, turnover)
    _frequency_gap(report, declaration, turnover)
    _disposition_gap(report, declaration, profit_loss)

    # Largest divergence first — with a screen this small, the one worth
    # looking at should not need scrolling to reach.
    report.gaps.sort(key=lambda g: g.magnitude or 0, reverse=True)
    return report


def _pend(report: GapReport, key: str, label: str, reason: str) -> None:
    report.pending.append({"key": key, "label": label, "reason": reason})


def _hold_days_gap(report: GapReport, decl: Declaration, turnover: dict | None) -> None:
    if decl.hold_days is None:
        return
    label = "평균 보유기간"
    if not turnover or not turnover.get("sufficient_data"):
        _pend(report, "hold_days", label, "매매 기록이 아직 부족합니다.")
        return
    observed = turnover.get("mean_hold_days")
    if observed is None:
        _pend(report, "hold_days", label, "보유기간을 계산할 만한 종결 거래가 없습니다.")
        return

    declared_text, observed_text = _fmt_days(decl.hold_days), _fmt_days(observed)
    report.gaps.append(Gap(
        key="hold_days",
        label=label,
        declared_text=declared_text,
        observed_text=observed_text,
        statement=f"평균 {declared_text} 보유한다고 답하셨습니다. 기록은 {observed_text}입니다.",
        magnitude=_magnitude(decl.hold_days, observed),
    ))


def _frequency_gap(report: GapReport, decl: Declaration, turnover: dict | None) -> None:
    if decl.trades_per_month is None:
        return
    label = "매매 빈도"
    if not turnover or not turnover.get("sufficient_data"):
        _pend(report, "trades_per_month", label, "매매 기록이 아직 부족합니다.")
        return

    count = turnover.get("trade_count")
    period = turnover.get("period_days")
    if not count or not period:
        _pend(report, "trades_per_month", label, "기간을 특정할 수 없습니다.")
        return

    # Normalised to 30 days so the comparison is like-for-like. Over a very
    # short window this extrapolates hard, so it is withheld under a month
    # rather than reported as if a fortnight predicted a month.
    if period < 30:
        _pend(report, "trades_per_month", label,
              f"기록이 {period:.0f}일치라 월 단위로 비교하기엔 짧습니다.")
        return

    observed = count * 30.0 / period
    declared_text = f"월 {_fmt_count(decl.trades_per_month)}"
    observed_text = f"월 {_fmt_count(observed)}"
    report.gaps.append(Gap(
        key="trades_per_month",
        label=label,
        declared_text=declared_text,
        observed_text=observed_text,
        statement=f"{declared_text} 매매한다고 답하셨습니다. 기록은 {observed_text}입니다.",
        magnitude=_magnitude(decl.trades_per_month, observed),
    ))


def _disposition_gap(report: GapReport, decl: Declaration, pl: dict | None) -> None:
    if decl.hold_longer is None:
        return
    label = "수익·손실 보유기간"
    if not pl or not pl.get("sufficient_data"):
        _pend(report, "hold_longer", label, "종결된 매매가 아직 부족합니다.")
        return
    if pl.get("one_sided"):
        _pend(report, "hold_longer", label, "수익 또는 손실 한쪽 거래만 있어 비교할 수 없습니다.")
        return

    win = (pl.get("take_profit") or {}).get("mean_hold_days")
    lose = (pl.get("stop_loss") or {}).get("mean_hold_days")
    if win is None or lose is None:
        _pend(report, "hold_longer", label, "양쪽 보유기간을 계산할 수 없습니다.")
        return

    win_text, lose_text = _fmt_days_pair(win, lose)
    if win > lose:
        actual = "profit"
        observed_text = f"수익 {win_text} · 손실 {lose_text}"
    elif lose > win:
        actual = "loss"
        observed_text = f"손실 {lose_text} · 수익 {win_text}"
    else:
        actual = "same"
        observed_text = f"양쪽 모두 {win_text}"

    declared_text = {
        "profit": "수익 난 쪽을 더 오래",
        "loss": "손실 난 쪽을 더 오래",
        "same": "비슷하다",
        "unsure": "잘 모르겠다",
    }[decl.hold_longer]

    if decl.hold_longer == "unsure":
        statement = f"기록은 {observed_text}입니다."
    elif decl.hold_longer == actual:
        # Agreement is reported too. A mirror that only speaks when the
        # user is wrong is not a mirror, and a user who is right about
        # themselves has earned being told so.
        statement = f"{declared_text} 답하셨고, 기록도 같습니다 — {observed_text}."
    else:
        statement = f"{declared_text} 답하셨습니다. 기록은 반대입니다 — {observed_text}."

    report.gaps.append(Gap(
        key="hold_longer",
        label=label,
        declared_text=declared_text,
        observed_text=observed_text,
        statement=statement,
        magnitude=_magnitude(win, lose),
    ))
