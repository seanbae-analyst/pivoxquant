#!/usr/bin/env python3
"""Layer C — Scan Railway logs for recurring runtime errors.

Sentry is not set up yet, so we fall back to Railway's public API + CLI.
The goal is to identify **patterns that recur 3+ times in the last hour**
so the self-healer does not chase single-event noise.

Output
------
Writes a JSONL file with one row per distinct error pattern:
    {
      "fingerprint": "<sha1 of file:line:exception_class>",
      "count": 7,
      "first_seen": "2026-04-24T03:12:10Z",
      "last_seen":  "2026-04-24T03:58:41Z",
      "file": "services/ai_service.py",
      "line": 142,
      "exception": "KeyError",
      "message": "'symbol'",
      "stack_excerpt": "...",
      "sample_lines": ["..."]
    }

Railway access
--------------
Two modes:
1. `RAILWAY_TOKEN` + service id — uses `railway logs --json` (preferred).
2. Dry-run / CI without Railway CLI — reads a fixture at
   `scripts/self_healing/fixtures/railway_sample.log` if present.

This script never talks to Claude and never modifies code. It is a pure
observer. The downstream `propose_fix.py` consumes its JSONL.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

OUT_PATH = Path(os.environ.get(
    "RAILWAY_SCAN_OUT",
    Path(__file__).resolve().parents[2] / "self_healing_artifacts" / "railway_patterns.jsonl",
))
WINDOW_MINUTES = int(os.environ.get("RAILWAY_WINDOW_MINUTES", "60"))
MIN_COUNT = int(os.environ.get("RAILWAY_MIN_COUNT", "3"))
DRY_RUN = os.environ.get("SELF_HEALING_DRY_RUN", "1") == "1"  # default dry-run

# Python traceback pattern — captures file/line/exception class + message
TRACEBACK_RE = re.compile(
    r'File "(?P<file>[^"]+)", line (?P<line>\d+).*?\n(?P<exc>[A-Z][A-Za-z_]*Error|Exception): (?P<msg>[^\n]+)',
    re.DOTALL,
)
# Simpler single-line exception pattern (Flask/gunicorn often collapses)
ONELINE_RE = re.compile(
    r'(?P<exc>[A-Z][A-Za-z_]*(?:Error|Exception)): (?P<msg>.{5,200})'
)

# Files/paths we will NEVER attempt auto-fix on (critical surface).
PROTECTED_PATHS = (
    "autotrader.py",
    "risk_defense.py",
    "services/legal_filter.py",
    "services/legal/",
    "services/agents/legal_gate.py",
    "billing/",
    "routes/auth",
    "security.py",
    "migrations/",
)


def fetch_logs() -> str:
    """Return raw log text. Falls back to fixture if Railway CLI absent."""
    if shutil.which("railway") and os.environ.get("RAILWAY_TOKEN"):
        # railway CLI needs an interactive project selection unless we
        # pass `--service`. Service name must be injected via env.
        service = os.environ.get("RAILWAY_SERVICE", "web")
        cmd = ["railway", "logs", "--service", service]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
            return out.stdout
        except Exception as e:
            print(f"[scan] railway CLI failed: {e}", file=sys.stderr)
    # Fallback: fixture
    fixture = Path(__file__).resolve().parent / "fixtures" / "railway_sample.log"
    if fixture.exists():
        print(f"[scan] using fixture {fixture}", file=sys.stderr)
        return fixture.read_text(encoding="utf-8", errors="replace")
    # Empty — nothing to analyze
    return ""


def is_protected(path: str) -> bool:
    p = path.replace("\\", "/")
    return any(prot in p for prot in PROTECTED_PATHS)


def normalize_file(path: str) -> str:
    """Convert abs paths like /app/services/foo.py → services/foo.py."""
    p = path.replace("\\", "/")
    for prefix in ("/app/", "/workspace/", "/home/runner/work/"):
        if p.startswith(prefix):
            p = p[len(prefix):]
    return p


def extract_patterns(log_text: str) -> list[dict[str, Any]]:
    """Group traceback occurrences by (file, line, exception class)."""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=WINDOW_MINUTES)
    groups: dict[str, dict[str, Any]] = {}

    for m in TRACEBACK_RE.finditer(log_text):
        file = normalize_file(m.group("file"))
        line = int(m.group("line"))
        exc = m.group("exc")
        msg = m.group("msg").strip()[:200]
        # Cheap fingerprint: file:line:exception
        key_raw = f"{file}:{line}:{exc}"
        fp = hashlib.sha1(key_raw.encode()).hexdigest()[:12]
        g = groups.setdefault(fp, {
            "fingerprint": fp,
            "file": file,
            "line": line,
            "exception": exc,
            "message": msg,
            "count": 0,
            "first_seen": now.isoformat(),
            "last_seen": now.isoformat(),
            "sample_lines": [],
            "protected": is_protected(file),
        })
        g["count"] += 1
        if len(g["sample_lines"]) < 3:
            g["sample_lines"].append(msg)

    # Filter by MIN_COUNT
    hot = [g for g in groups.values() if g["count"] >= MIN_COUNT]
    hot.sort(key=lambda x: (-x["count"], x["file"]))
    return hot


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_text = fetch_logs()
    if not log_text:
        print("[scan] no log data available (no RAILWAY_TOKEN + no fixture). "
              "Writing empty output.", file=sys.stderr)
        OUT_PATH.write_text("", encoding="utf-8")
        return 0

    patterns = extract_patterns(log_text)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        for p in patterns:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"[scan] wrote {len(patterns)} patterns to {OUT_PATH}")
    if DRY_RUN:
        for p in patterns:
            protected = " [PROTECTED]" if p["protected"] else ""
            print(f"  - {p['fingerprint']} x{p['count']} {p['file']}:{p['line']} "
                  f"{p['exception']}: {p['message'][:60]}{protected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
