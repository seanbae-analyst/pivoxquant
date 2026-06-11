"""Shared per-UTC-day AI call budget — B3 fix (cohort-scaled ceiling).

Why this exists (docs/strategy/business_model_audit_2026-06-10.md §B3):
each AI-calling artifact service kept its own module-global
``{"day": ..., "count": 0}`` counter with a FIXED ceiling. The ceiling
doubled as a paid-user cap — with 200 weekly-memo calls/day, the 201st
entitled Pro user silently got placeholder content ("오늘 예산 소진").
The retention damage scales with growth while the cost the cap protects
against (Haiku, roughly $0.001–0.01 per artifact call) does not.

The fix keeps the cost defence but makes the ceiling track entitlement::

    effective_limit = max(base_limit, ceil(entitled_today * headroom))

Cron entry-points call :meth:`DailyAiBudget.note_entitled` with the size
of the cohort they are about to serve, so legitimate fan-out can never
starve a paying user, while a runaway loop (a bug retrying far beyond the
cohort) still trips the ceiling. ``note_entitled`` is cumulative within
the UTC day — repeated scans (e.g. the prebrief 10-minute matcher) only
widen headroom, never shrink it. Exhaustion is observable: one WARNING
per day at >= 80% of the effective limit.

Deliberately NOT per-user: both artifact call paths are already
once-per-logical-generation by construction (weekly memo = 1 call per
user per Sunday; prebrief consumes once per generation — its FIX 6), so
a per-user counter would add plumbing without changing outcomes. The
earnings-tone budget stays GLOBAL on purpose too: tone results are cached
per ticker for 90 days and shared across users, so that budget gates
new-ticker analyses per day, not users. Revisit if a per-user retry storm
is ever observed in the wild.

In-process state only (matching the counters this replaces): Railway runs
one web process, and the artifact crons run in it. ₩0-infra rule — no
Redis. A restart resets the day's count, which only ever errs generous.
"""
from __future__ import annotations

import logging
import math
import os
import threading
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

#: Fraction of the effective limit at which the once-a-day WARNING fires.
WARN_PCT = 0.8


class DailyAiBudget:
    """Thread-safe daily AI-call budget with a cohort-scaled ceiling.

    Parameters
    ----------
    kind:
        Short label for logs (``"weekly_memo"``).
    base_limit:
        Floor for the daily ceiling when no cohort has been noted (and the
        minimum even when one has — ``max()`` semantics).
    env_var:
        Optional environment variable that overrides ``base_limit`` at
        read time (positive int). Lets ops raise a cap without a code
        change.
    headroom:
        Multiplier applied to the noted cohort size. 1.25 = the cohort
        plus 25% slack for legitimate retries/re-runs.
    """

    def __init__(
        self,
        kind: str,
        base_limit: int,
        *,
        env_var: str | None = None,
        headroom: float = 1.25,
    ) -> None:
        self.kind = kind
        self._base_limit = int(base_limit)
        self._env_var = env_var
        self._headroom = float(headroom)
        self._lock = threading.Lock()
        self._day = None
        self._count = 0
        self._entitled = 0
        self._warned = False

    # ── internals ───────────────────────────────────────────────────────

    @staticmethod
    def _today():
        return datetime.now(timezone.utc).replace(tzinfo=None).date()

    def _roll_locked(self, today) -> None:
        if self._day != today:
            self._day = today
            self._count = 0
            self._entitled = 0
            self._warned = False

    def _base(self) -> int:
        if self._env_var:
            raw = os.environ.get(self._env_var, "").strip()
            if raw:
                try:
                    v = int(raw)
                    if v > 0:
                        return v
                except ValueError:
                    logger.warning(
                        "ai_budget[%s]: ignoring non-int %s=%r",
                        self.kind, self._env_var, raw,
                    )
        return self._base_limit

    def _effective_locked(self) -> int:
        base = self._base()
        if self._entitled > 0:
            return max(base, math.ceil(self._entitled * self._headroom))
        return base

    def _maybe_warn_locked(self) -> None:
        limit = self._effective_locked()
        # floor(), not the raw float: ``count >= WARN_PCT*limit`` evaluates to
        # ``count >= ceil`` for ints, which equals ``limit`` itself for limit<=4
        # (0.8*4=3.2 → warns at 4 = the last allowed call, i.e. AT exhaustion,
        # not before). floor() gives a genuine advance warning whenever limit>=2
        # (limit=1 cannot warn in advance) while leaving prod limits (50/100/200)
        # unchanged: floor(0.8*200)=160 == the old threshold.
        threshold = max(1, math.floor(WARN_PCT * limit))
        if not self._warned and limit > 0 and self._count >= threshold:
            self._warned = True
            logger.warning(
                "ai_budget[%s]: %d/%d daily AI calls used (>=80%%) — raise %s "
                "or check for a runaway loop",
                self.kind, self._count, limit,
                self._env_var or "the base limit",
            )

    # ── public API ──────────────────────────────────────────────────────

    def note_entitled(self, count) -> None:
        """Record that ``count`` entitled generations are about to run today.

        Cumulative within the UTC day; non-positive / non-int input is a
        no-op (budget must never raise into a cron path).
        """
        try:
            count = int(count)
        except (TypeError, ValueError):
            return
        if count <= 0:
            return
        with self._lock:
            self._roll_locked(self._today())
            self._entitled += count

    def available(self) -> bool:
        """True while today's count is below the effective ceiling."""
        with self._lock:
            self._roll_locked(self._today())
            return self._count < self._effective_locked()

    def consume(self) -> None:
        """Record one AI call. Split from :meth:`available` on purpose —
        weekly memo / prebrief check early but only consume on a call that
        actually went out (prebrief FIX 6: once per logical generation)."""
        with self._lock:
            self._roll_locked(self._today())
            self._count += 1
            self._maybe_warn_locked()

    def try_consume(self) -> bool:
        """Atomic check-and-spend for call sites that gate and consume in
        one step (earnings tone). Returns False when exhausted."""
        with self._lock:
            self._roll_locked(self._today())
            if self._count >= self._effective_locked():
                return False
            self._count += 1
            self._maybe_warn_locked()
            return True

    def snapshot(self) -> dict:
        """Ops/test introspection — never used on a hot path."""
        with self._lock:
            self._roll_locked(self._today())
            return {
                "kind": self.kind,
                "day": str(self._day),
                "count": self._count,
                "entitled": self._entitled,
                "limit": self._effective_locked(),
            }


__all__ = ["DailyAiBudget", "WARN_PCT"]
