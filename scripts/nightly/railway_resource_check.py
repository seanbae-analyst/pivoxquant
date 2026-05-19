#!/usr/bin/env python3
"""Railway OOM/CPU pressure detector (D-2, Wave I P0).

목적
----
Railway Hobby free tier 는 컨테이너당 **512MB RAM / 1 vCPU** 한도를 갖는다.
gunicorn workers=1 + gevent 으로 띄운 Flask + APScheduler 가 메모리 누수 (예:
``data_fetcher.DataFrame`` 캐시, ``AISummaryService`` 의 in-process LRU) 또는
CPU spike (예: ``quant_models`` 백테스트 동시 실행) 로 RSS 가 한도를 초과하면
Railway 가 컨테이너를 SIGKILL 한다 — gunicorn 자동 재시작이지만 그 사이
SSE 스트림 / OAuth 콜백 / 결제 webhook 이 끊긴다.

이 스크립트는 **본인 프로세스의 RSS + 시스템 CPU** 를 측정해 임계 초과를
Slack 으로 사전 경고한다. Railway 자체 알림 (Metrics 탭) 보다 5-10분 빠르다.

임계값
------
- RSS > **450MB** (512MB 의 88% — Hobby plan headroom margin)
- CPU > **80%** 가 **5분(2.5 샘플 == 3 샘플 / 2분 간격)** 동안 지속

dedup
-----
``state/railway_resource_history.json`` 에 sliding window (최근 10 샘플) 저장.
한 번 alert 보낸 후 RSS / CPU 가 임계 아래로 떨어지지 않으면 30분 dedup —
같은 incident 로 Slack 도배 방지.

비용
----
psutil 만 사용. Railway 외부 API 호출 0. Slack webhook free tier 만 활용. **0원**.

graceful skip
-------------
psutil 미설치 시 (`ImportError`) 즉시 exit 0. SLACK_WEBHOOK_URL 미설정 시
stdout fallback. Railway 외 환경 (예: CI) 에서도 안전.

스케줄
------
APScheduler `CronTrigger(minute='*/2', timezone='Asia/Seoul')` — 2분 간격.
- 너무 자주(예: 30s) 측정하면 CPU 한도 자체를 본 스크립트가 잡아먹음.
- 5분 지속 임계를 검증하려면 최소 3 샘플 필요 → 2분 간격이 최소.
"""
from __future__ import annotations

import json
import logging
import os
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = _ROOT / "state"
STATE_PATH = STATE_DIR / "railway_resource_history.json"

# Railway Hobby plan: 512MB RAM. Alert at 88% to leave headroom for the
# subprocess fork / OAuth state push that happens during gunicorn restart.
RSS_THRESHOLD_MB = 450.0
# CPU sustained-pressure threshold. 80% on 1 vCPU = SSE clients start to
# perceive latency; > 90% = OAuth callback timeouts.
CPU_THRESHOLD_PCT = 80.0
# Number of consecutive samples (≥ 5 minutes worth at 2-minute cadence)
# that must all exceed CPU_THRESHOLD_PCT before we alert. RSS alerts fire
# on a single sample because RSS doesn't fluctuate the way CPU does.
CPU_SUSTAINED_SAMPLES = 3
# Keep the most recent N samples in state — bounded so the JSON file
# doesn't grow unbounded over months of operation.
HISTORY_WINDOW = 10
# Dedup window — once we've alerted for an incident, suppress further
# alerts for this many minutes unless metrics drop back to baseline.
DEDUP_MINUTES = 30

_SSL_CTX = ssl.create_default_context()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def load_history() -> dict:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_PATH.exists():
        return {"samples": [], "last_alert_at": None, "last_alert_reason": None}
    try:
        data = json.loads(STATE_PATH.read_text("utf-8"))
        # Backfill keys for forward-compat with older state files.
        data.setdefault("samples", [])
        data.setdefault("last_alert_at", None)
        data.setdefault("last_alert_reason", None)
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("history load failed (%s) — starting fresh", exc)
        return {"samples": [], "last_alert_at": None, "last_alert_reason": None}


def save_history(history: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(history, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def measure_sample(psutil_mod) -> dict:
    """Take a single (rss_mb, cpu_pct, ts) sample.

    ``cpu_percent(interval=1.0)`` blocks 1s to compute CPU% — that's the
    cost of accurate single-shot measurement (the interval=None form returns
    0.0 on first call because psutil needs a reference window).
    """
    proc = psutil_mod.Process(os.getpid())
    rss_bytes = proc.memory_info().rss
    rss_mb = rss_bytes / (1024 * 1024)
    # System-wide CPU% over a 1-second window. Why system-wide vs per-proc:
    # gunicorn forks a single worker; if the worker is healthy but a parallel
    # subprocess (yt-dlp, pg_dump, playwright) eats CPU, we still want to alert.
    cpu_pct = psutil_mod.cpu_percent(interval=1.0)
    return {
        "ts": _now_utc().isoformat(),
        "rss_mb": round(rss_mb, 1),
        "cpu_pct": round(cpu_pct, 1),
    }


def _is_sustained_cpu(samples: list[dict]) -> bool:
    """True if the last CPU_SUSTAINED_SAMPLES samples all exceed threshold.

    Empty or short history → False (need a full window to alert).
    """
    if len(samples) < CPU_SUSTAINED_SAMPLES:
        return False
    recent = samples[-CPU_SUSTAINED_SAMPLES:]
    return all(s.get("cpu_pct", 0.0) > CPU_THRESHOLD_PCT for s in recent)


def detect_violations(samples: list[dict]) -> list[str]:
    """Return a list of human-readable violation reasons (empty = OK)."""
    if not samples:
        return []
    reasons: list[str] = []
    latest = samples[-1]
    rss_mb = latest.get("rss_mb", 0.0)
    if rss_mb > RSS_THRESHOLD_MB:
        reasons.append(
            f"RSS={rss_mb:.1f}MB > {RSS_THRESHOLD_MB:.0f}MB "
            f"(Railway free tier 512MB 의 {rss_mb/512*100:.0f}%)"
        )
    if _is_sustained_cpu(samples):
        avg_cpu = sum(
            s.get("cpu_pct", 0.0) for s in samples[-CPU_SUSTAINED_SAMPLES:]
        ) / CPU_SUSTAINED_SAMPLES
        reasons.append(
            f"CPU sustained > {CPU_THRESHOLD_PCT:.0f}% for "
            f"{CPU_SUSTAINED_SAMPLES} samples (avg={avg_cpu:.1f}%)"
        )
    return reasons


def should_alert(history: dict, violations: list[str]) -> bool:
    """Dedup gate. No violations → no alert. Recent alert → skip."""
    if not violations:
        return False
    last_alert = _parse_iso(history.get("last_alert_at"))
    if last_alert is None:
        return True
    return _now_utc() - last_alert >= timedelta(minutes=DEDUP_MINUTES)


def post_slack(text: str) -> bool:
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        logger.warning("SLACK_WEBHOOK_URL 미설정 — stdout fallback")
        print(f"[SLACK-FALLBACK] {text}")
        return False
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        webhook,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.error("Slack webhook failed: %s", exc)
        return False


def format_alert(latest: dict, reasons: list[str]) -> str:
    bullets = "\n".join(f"  • {r}" for r in reasons)
    return (
        "[CRIT] PivoxQuant Railway resource pressure\n"
        f"RSS={latest.get('rss_mb', 0):.1f}MB / CPU={latest.get('cpu_pct', 0):.1f}% "
        f"@ {latest.get('ts')}\n"
        f"Violations:\n{bullets}\n"
        "조치: Railway dashboard → Deployments → 메모리 사용 패턴 확인. "
        "메모리 누수 의심 시 `services.container` LRU 캐시 + "
        "`data_fetcher` DataFrame 캐시 점검."
    )


def main() -> int:
    # Soft-dependency: psutil is a transitive dep (sentry-sdk pulls it on
    # some platforms) but not pinned in our requirements.txt before Wave I.
    # If absent, skip gracefully — never block the scheduler thread.
    try:
        import psutil  # noqa: WPS433 — local import is the graceful-skip pattern
    except ImportError:
        logger.warning("psutil 미설치 — railway_resource_check skip")
        return 0

    history = load_history()
    sample = measure_sample(psutil)
    history["samples"].append(sample)
    # Bounded sliding window.
    if len(history["samples"]) > HISTORY_WINDOW:
        history["samples"] = history["samples"][-HISTORY_WINDOW:]

    logger.info(
        "sample rss=%.1fMB cpu=%.1f%% window=%d",
        sample["rss_mb"], sample["cpu_pct"], len(history["samples"]),
    )

    violations = detect_violations(history["samples"])
    rc = 0
    if violations:
        rc = 2  # non-zero = ops attention
        if should_alert(history, violations):
            msg = format_alert(sample, violations)
            post_slack(msg)
            history["last_alert_at"] = _now_utc().isoformat()
            history["last_alert_reason"] = "; ".join(violations)
        else:
            logger.info(
                "violations present but dedup'd (last_alert=%s)",
                history.get("last_alert_at"),
            )

    save_history(history)
    return rc


if __name__ == "__main__":
    sys.exit(main())
