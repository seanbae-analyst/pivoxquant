"""Virtual-user sweep — pytest gate.

The 20-user sweep (scripts/qa/virtual_user_sweep.py) previously ran ONLY from
the 03:39 daily cron, which gets skipped whenever the git guard trips (e.g.
2026-06-11: uncommitted CEO work → whole run skipped). This gate runs a
smaller N inside the normal suite so sweep-class regressions (5xx, NaN,
suffix-bucketing, tier-gate misses, proxy-disclosure drops, broken artifact
persistence) fail CI/full-suite instead of waiting for the next clean cron.

N=6 covers all 4 tier slots (free×2/pro/premium … pattern repeats) and the
empty / kr_only / us_only archetypes — the cheapest slice that still
exercises every check class, including the per-tier artifact-generate leg.
The nightly cron keeps running the full 20 for the long tail.

The sweep builds its own Flask app against the SAME temp SQLite the test
session uses; requesting the `app` fixture ensures `_reset_db` truncates the
sweep's rows afterwards, keeping other tests isolated.
"""
from __future__ import annotations


def _format(findings: list[dict]) -> str:
    return "\n".join(
        f"[{f['severity']}] {f['user']}: {f['title']} — {f['detail'][:160]}"
        for f in findings
    )


def test_virtual_user_sweep_clean(app):  # noqa: ARG001 — fixture triggers _reset_db cleanup
    from scripts.qa.virtual_user_sweep import Sweep

    sweep = Sweep(6)
    sweep.run(report=False)

    blocking = [f for f in sweep.findings if f["severity"] in ("P0", "P1")]
    assert not blocking, (
        f"virtual-user sweep found {len(blocking)} P0/P1 "
        f"({sweep.calls} calls):\n{_format(blocking)}"
    )
    # P2/P3 are contract drift notes — surface them in -v output without
    # failing the build (the nightly cron triages them).
    if sweep.findings:
        print(f"\n[sweep] non-blocking findings ({len(sweep.findings)}):\n"
              + _format(sweep.findings))
