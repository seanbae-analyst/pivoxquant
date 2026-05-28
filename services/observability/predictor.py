"""Predictive issue detection — v57-C2 SPEC SKELETON.

본 파일은 spec 골격이다. 구현은 v58 wave에서 진행.
의도적으로 NotImplementedError를 남겨 import는 가능하되 실행 시 명시적으로
"미구현" 신호를 준다 (silent no-op 금지 — feedback_no_false_reports 룰).

설계: docs/agents/SELF_IMPROVING_MEMORY_LOOP.md Loop 2 참조.

Constraints (메모리 룰)
-----------------------
- 추가 비용 0원: 외부 ML 라이브러리 금지, Python stdlib 만 사용
- silent fail 금지: 모든 미구현 경로는 NotImplementedError
- ML 없음: poisson burst / weekday rate / chain failure 같은 simple stats only
- 출력: .claude/memory/predictions.json (구조는 spec 문서 §2 Loop 2 참조)

데이터 소스
-----------
1. autopilot_log.md (90일)
2. crontab logs ~/Library/Logs/pivoxquant/*.log
3. Sentry free tier API (월 5K 이벤트 한도, env-gated)

호출 진입점
-----------
cron entry: ops_predictive_scan (매일 23:00 KST, v58 추가 예정)
  cd ~/dev/pivoxquant && python3 -m services.observability.predictor
"""

from __future__ import annotations

import json
import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths (절대경로 — agent threads cwd 리셋 대응)
# ---------------------------------------------------------------------------

REPO_ROOT = Path("/Users/seanbae/dev/pivoxquant")
MEMORY_DIR = REPO_ROOT / ".claude" / "memory"
PREDICTIONS_PATH = MEMORY_DIR / "predictions.json"
ISSUE_PATTERNS_PATH = MEMORY_DIR / "issue_patterns.json"

USER_MEMORY = Path(
    "/Users/seanbae/.claude/projects/-Users-seanbae-Desktop---/memory"
)
AUTOPILOT_LOG = USER_MEMORY / "autopilot_log.md"

CRON_LOG_DIR = Path.home() / "Library" / "Logs" / "pivoxquant"

# ---------------------------------------------------------------------------
# Confidence thresholds (메모리 룰: false positive 시 CEO 짜증)
# ---------------------------------------------------------------------------

CONFIDENCE_BRIEFING_PREPEND = 0.75  # morning-briefing top에 prepend
CONFIDENCE_AUTO_EXECUTE = 0.85  # 자동 실행 (현재는 사용 안함)
CONFIDENCE_WATCHING = 0.50  # 단순 기록

# Statistical thresholds
BURST_SIGMA_THRESHOLD = 2.0  # mean + 2σ 초과 시 burst window
WEEKDAY_FAIL_RATE_THRESHOLD = 0.2  # fragile weekday 태그
CHAIN_FAILURE_THRESHOLD = 0.7  # upstream blocker 태그

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class FragileWindow:
    """특정 시간대 fail 빈도 burst."""

    cron_id: str
    window_start_hour: int  # 0~23 KST
    window_end_hour: int
    expected_fail_probability: float
    based_on: str  # 근거 (e.g. "burst N=23 in 30 days")
    preventive_action: str


@dataclass
class WeekdayFragility:
    """요일별 fail rate."""

    cron_id: str
    weekday: int  # 0=Mon ... 6=Sun
    fail_rate: float
    sample_size: int


@dataclass
class ChainFailure:
    """cron A fail → cron B fail 연쇄."""

    upstream_id: str
    downstream_id: str
    correlation: float
    sample_size: int


@dataclass
class RegressionSignal:
    """신규 commit 후 fail rate 변화."""

    suspect_commit: str
    metric: str  # "vitest_pass_rate" / "pytest_pass_rate" / "cron_fail_rate"
    change_pct: float
    based_on: str
    confidence: float


@dataclass
class PredictionReport:
    """최종 출력 — predictions.json 직렬화."""

    generated_at: str
    horizon_hours: int = 24
    fragile_windows: list[FragileWindow] = field(default_factory=list)
    weekday_fragilities: list[WeekdayFragility] = field(default_factory=list)
    chain_failures: list[ChainFailure] = field(default_factory=list)
    regression_signals: list[RegressionSignal] = field(default_factory=list)
    precision_30d: float | None = None
    recall_30d: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "generated_at": self.generated_at,
            "horizon_hours": self.horizon_hours,
            "fragile_windows": [w.__dict__ for w in self.fragile_windows],
            "weekday_fragilities": [
                w.__dict__ for w in self.weekday_fragilities
            ],
            "chain_failures": [c.__dict__ for c in self.chain_failures],
            "regression_signals": [r.__dict__ for r in self.regression_signals],
            "precision_30d": self.precision_30d,
            "recall_30d": self.recall_30d,
        }


# ---------------------------------------------------------------------------
# Parsers (v58 구현 예정)
# ---------------------------------------------------------------------------


def parse_autopilot_log(path: Path = AUTOPILOT_LOG) -> list[dict[str, Any]]:
    """autopilot_log.md → 구조화 events.

    각 entry는 {timestamp, agent_id, status, message} 형식.
    헤더 규약: "## YYYY-MM-DD HH:MM agent-name"
    """
    raise NotImplementedError(
        "v58 wave에서 구현 — docs/agents/SELF_IMPROVING_MEMORY_LOOP.md Phase B-D1"
    )


def parse_cron_logs(log_dir: Path = CRON_LOG_DIR) -> list[dict[str, Any]]:
    """crontab fire logs → {cron_id, timestamp, exit_code, duration}."""
    raise NotImplementedError(
        "v58 wave에서 구현 — Phase B-D1, 데이터 입력 90일치"
    )


def parse_git_log(days: int = 90) -> list[dict[str, Any]]:
    """git log --since="{days} days ago" → commits."""
    raise NotImplementedError("v58 wave에서 구현 — Phase B-D1")


# ---------------------------------------------------------------------------
# Statistical detectors (simple stats only, no ML)
# ---------------------------------------------------------------------------


def detect_fragile_windows(
    events: list[dict[str, Any]],
) -> list[FragileWindow]:
    """1시간 bucket 30일 누적 → poisson mean + 2σ 초과 burst.

    알고리즘 (의도, 구현은 v58):
    1. cron_id 별로 events 그룹화
    2. 각 cron에서 1시간 bucket (24개) × 일자 (30개) → fail count matrix
    3. 일자 차원 mean + std 계산
    4. mean + BURST_SIGMA_THRESHOLD * std 초과 bucket → fragile window
    5. expected_fail_probability = count / total_runs
    """
    raise NotImplementedError("v58 wave — Phase B-D2 statistical model")


def detect_weekday_fragility(
    events: list[dict[str, Any]],
) -> list[WeekdayFragility]:
    """요일별 fail rate > WEEKDAY_FAIL_RATE_THRESHOLD."""
    raise NotImplementedError("v58 wave — Phase B-D2")


def detect_chain_failures(
    events: list[dict[str, Any]], window_minutes: int = 5
) -> list[ChainFailure]:
    """cron A fail → window_minutes 내 cron B fail 빈도 > CHAIN_FAILURE_THRESHOLD."""
    raise NotImplementedError("v58 wave — Phase B-D2")


def detect_regression_signals(
    events: list[dict[str, Any]], commits: list[dict[str, Any]]
) -> list[RegressionSignal]:
    """신규 commit X 후 24h 내 fail rate 변화 +50% 초과."""
    raise NotImplementedError("v58 wave — Phase B-D2")


# ---------------------------------------------------------------------------
# Self-evaluation (precision/recall)
# ---------------------------------------------------------------------------


def evaluate_past_predictions() -> tuple[float | None, float | None]:
    """이전 predictions.json vs 실제 발생 → precision/recall 계산.

    Returns:
        (precision_30d, recall_30d) — 첫 실행 시 (None, None)
    """
    raise NotImplementedError("v58 wave — Phase B-D6 self-eval")


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def write_predictions(report: PredictionReport, path: Path = PREDICTIONS_PATH) -> None:
    """predictions.json 갱신 — atomic write (temp + rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    tmp.replace(path)
    logger.info("predictions.json 갱신 완료: %s", path)


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------


def run_predictive_scan() -> PredictionReport:
    """ops_predictive_scan cron entry point.

    Returns:
        PredictionReport — predictions.json에 직렬화 완료
    """
    raise NotImplementedError(
        "v57-C2 spec only. 구현 진입은 v58 wave. "
        "docs/agents/SELF_IMPROVING_MEMORY_LOOP.md §3 Phase B 참조."
    )


if __name__ == "__main__":
    # 의도적으로 NotImplementedError 발생 → cron 도입 전 silent 실행 방지
    logging.basicConfig(level=logging.INFO)
    run_predictive_scan()
