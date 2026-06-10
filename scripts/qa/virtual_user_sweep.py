#!/usr/bin/env python3
"""Virtual-user sweep — N simulated users exercise the real route surface.

CEO order (2026-06-10 overnight): "가상유저 한 20명 만들어서 테스트 돌리자".
CAUS (scripts/caus_daily_sweep.py) drives ONE browser user per day through one
scenario; this sweep is the complementary wide pass — 20 users with deliberately
diverse personas/portfolios hammer the API surface in-process (Flask test
client, isolated SQLite DB), so it is deterministic, costs ₩0, never touches
prod or external APIs, and finishes in seconds.

What each user does (per persona/portfolio archetype):
  login → add positions (KR/US/mixed/edge sizes) → GET /api/portfolio (NAV
  totals sanity: suffix-bucketing, no NaN) → pre-trade deposition
  (start → proceed, observed-context capture) → journal feed → persona read →
  signals/risk/alerts/watchlist reads → settings surfaces.

Checks collected as findings:
  * any 5xx anywhere
  * unexpected 4xx (vs the documented contract)
  * literal NaN/Infinity in any JSON body
  * portfolio totals that violate suffix bucketing (KR value in USD bucket)
  * pre-trade rows missing after proceed

Usage:
    ./venv/bin/python scripts/qa/virtual_user_sweep.py [--users 20]

Report: docs/qa/virtual_user_sweep_<date>.md
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

# Reuse the test harness' env isolation + app factory (kills live API keys,
# isolated SQLite, scheduler off). Importing tests.conftest runs that setup.
import tests.conftest as _conftest  # noqa: E402

RATIONALE = "가상유저 스위프 — 실적 추세 확인 후 분할 진입 계획. 손절은 직전 저점 아래."

# 20-user archetype matrix: (persona, tier, portfolio archetype)
PERSONAS = ["growth", "value", "balanced", "income",
            "quant", "beginner", "speculator", "daytrader"]

PORTFOLIOS = {
    "empty":      [],
    "kr_only":    [("005930.KS", 10, 70000), ("035720.KS", 5, 45000)],
    "us_only":    [("AAPL", 10, 180.0), ("MSFT", 4, 410.0)],
    "mixed":      [("005930.KS", 10, 70000), ("AAPL", 6, 175.0), ("NVDA", 2, 900.0)],
    "fractional": [("AAPL", 0.37, 182.55)],
    "huge_qty":   [("005930.KS", 999_999, 70000)],
    "one_share":  [("BRK-A", 1, 620_000.0)],
    "kosdaq":     [("035760.KQ", 20, 12000)],
}
ARCHETYPE_ORDER = [
    "empty", "empty",
    "kr_only", "kr_only", "kr_only",
    "us_only", "us_only", "us_only",
    "mixed", "mixed", "mixed", "mixed", "mixed", "mixed",
    "fractional", "fractional",
    "huge_qty", "one_share", "kosdaq", "kosdaq",
]

READ_ENDPOINTS = [
    ("portfolio",  "/api/portfolio"),
    ("positions",  "/api/portfolio/positions"),
    ("journal",    "/api/pre-trade/list"),
    ("persona",    "/api/profile/persona"),
    ("profile",    "/api/profile"),
    ("signals",    "/api/signals"),
    ("alerts",     "/api/alerts"),
    ("watchlist",  "/api/watchlist"),
    ("risk",       "/api/risk/summary"),
    ("me",         "/api/auth/me"),
]


def _body_text(resp) -> str:
    try:
        return resp.get_data(as_text=True) or ""
    except Exception:
        return ""


def _has_bad_float(text: str) -> bool:
    # Literal NaN/Infinity leaking into JSON (json.dumps allow_nan artifacts).
    return any(tok in text for tok in (": NaN", ":NaN", "Infinity", '"nan"', "$nan"))


class Sweep:
    def __init__(self, n_users: int):
        self.n = n_users
        self.findings: list[dict] = []
        self.calls = 0
        self.app = _conftest._build_test_app()

    def finding(self, user: str, severity: str, title: str, detail: str):
        self.findings.append({
            "user": user, "severity": severity, "title": title, "detail": detail,
        })

    # ── per-user flow ────────────────────────────────────────────────
    def run_user(self, idx: int):
        persona = PERSONAS[idx % len(PERSONAS)]
        archetype = ARCHETYPE_ORDER[idx % len(ARCHETYPE_ORDER)]
        tier = ["free", "free", "pro", "premium"][idx % 4]
        email = f"vu{idx + 1}@pivoxquant-test.local"
        label = f"vu{idx + 1}[{persona}/{tier}/{archetype}]"

        from extensions import db
        from models import User

        with self.app.app_context():
            u = User(
                email=email, name=f"VU {idx + 1}",
                available_capital=10_000_000.0,
                available_capital_krw=10_000_000_000.0,
                subscription_tier=tier,
                onboarding_completed=True,
            )
            u.birthdate = date(1990, 1, 1)
            u.is_simulated = True
            u.set_pw("sweep-pass-123")
            db.session.add(u)
            db.session.commit()

            # Persona declaration — direct profile row (the questionnaire UI
            # path is covered by its own tests; here we need the read surface).
            try:
                from models import InvestmentProfile
                db.session.add(InvestmentProfile(
                    user_id=u.id, profile_type=persona,
                ))
                db.session.commit()
            except Exception:
                db.session.rollback()  # column mismatch → persona read tests fallback

        client = self.app.test_client()
        r = client.post("/api/auth/login",
                        json={"email": email, "password": "sweep-pass-123"})
        self.calls += 1
        if r.status_code != 200:
            self.finding(label, "P0", "login failed",
                         f"{r.status_code}: {_body_text(r)[:160]}")
            return

        # CSRF — double-submit cookie (security.py): the server sets a
        # `csrf_token` cookie; mutating requests must echo it in the
        # X-CSRF-Token header. Same mechanics as tests/conftest.CSRFTestClient.
        client.get("/api/auth/me")  # force the cookie to be issued
        csrf = None
        try:
            for c in client._cookies.values():  # Flask 3 test client jar
                if c.key == "csrf_token":
                    csrf = c.value
                    break
        except AttributeError:
            pass
        headers = {"X-CSRF-Token": csrf} if csrf else {}

        # 1) Build the portfolio.
        for (tk, qty, px) in PORTFOLIOS[archetype]:
            r = client.post("/api/portfolio/positions", headers=headers, json={
                "symbol": tk, "side": "Long", "quantity": qty, "price": px,
                "purchase_date": "2026-06-01", "note": "",
            })
            self.calls += 1
            if r.status_code >= 500:
                self.finding(label, "P0", f"position add 5xx ({tk})",
                             f"{r.status_code}: {_body_text(r)[:200]}")
            elif r.status_code not in (200, 201):
                self.finding(label, "P2", f"position add rejected ({tk})",
                             f"{r.status_code}: {_body_text(r)[:200]}")

        # 2) Pre-trade deposition: start → proceed (the record spine).
        r = client.post("/api/pre-trade/start", headers=headers, json={
            "ticker": "AAPL", "side": "BUY", "shares": 1,
            "rationale": RATIONALE,
            "devil_advocate": "Q1 … → (acknowledged)",
        })
        self.calls += 1
        if r.status_code != 200:
            self.finding(label, "P1", "pre-trade start failed",
                         f"{r.status_code}: {_body_text(r)[:200]}")
        else:
            rid = (r.get_json() or {}).get("reflection", {}).get("id")
            if rid:
                rp = client.post(f"/api/pre-trade/{rid}/proceed", headers=headers)
                self.calls += 1
                if rp.status_code != 200:
                    self.finding(label, "P1", "pre-trade proceed failed",
                                 f"{rp.status_code}: {_body_text(rp)[:200]}")

        # 3) Read surface — every endpoint must be 5xx-free and NaN-free.
        for name, url in READ_ENDPOINTS:
            r = client.get(url)
            self.calls += 1
            body = _body_text(r)
            if r.status_code >= 500:
                self.finding(label, "P0", f"GET {name} 5xx",
                             f"{r.status_code}: {body[:200]}")
                continue
            if r.status_code not in (200, 204) and name not in ("risk",):
                # risk/summary may legitimately 4xx on an empty book — note others.
                self.finding(label, "P3", f"GET {name} -> {r.status_code}",
                             body[:160])
            if _has_bad_float(body):
                self.finding(label, "P1", f"GET {name} body contains NaN/Infinity",
                             body[:200])

        # 4) Portfolio totals: suffix bucketing must hold (2026-06-10 fix).
        r = client.get("/api/portfolio")
        self.calls += 1
        if r.status_code == 200:
            d = r.get_json() or {}
            kr_sum = sum(
                p.get("market_value") or 0 for p in d.get("positions", [])
                if str(p.get("ticker", "")).upper().endswith((".KS", ".KQ"))
            )
            tk = d.get("total_value_krw")
            if tk is not None and abs((tk or 0) - kr_sum) > max(1.0, kr_sum * 0.001):
                self.finding(label, "P1", "NAV KRW bucket != suffix sum",
                             f"total_value_krw={tk} vs suffix-sum={kr_sum}")
            for key in ("total_value_usd", "total_value_krw", "total_value_all_krw"):
                v = d.get(key)
                if isinstance(v, float) and not math.isfinite(v):
                    self.finding(label, "P0", f"{key} non-finite", str(v))

        # 5) Journal must contain the proceeded reflection.
        r = client.get("/api/pre-trade/list")
        self.calls += 1
        if r.status_code == 200:
            rows = (r.get_json() or {}).get("reflections", [])
            if not rows:
                self.finding(label, "P2", "journal empty after proceed",
                             "expected >=1 reflection")

    # ── orchestration ────────────────────────────────────────────────
    def run(self) -> Path:
        started = datetime.now(timezone.utc)
        for i in range(self.n):
            try:
                self.run_user(i)
            except Exception as exc:  # noqa: BLE001 — record, keep sweeping
                self.finding(f"vu{i + 1}", "P0", "sweep harness exception",
                             f"{type(exc).__name__}: {exc}")
        return self.report(started)

    def report(self, started) -> Path:
        out_dir = REPO / "docs" / "qa"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"virtual_user_sweep_{date.today().isoformat()}.md"
        sev_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        self.findings.sort(key=lambda f: sev_order.get(f["severity"], 9))
        counts = {s: sum(1 for f in self.findings if f["severity"] == s)
                  for s in ("P0", "P1", "P2", "P3")}
        lines = [
            f"# Virtual-user sweep — {date.today().isoformat()}",
            "",
            f"- users: {self.n} (8 personas × free/pro/premium × 8 portfolio archetypes)",
            f"- HTTP calls: {self.calls} (in-process test client, isolated SQLite, ₩0)",
            f"- started: {started.isoformat()}",
            f"- findings: {len(self.findings)} "
            f"(P0 {counts['P0']} / P1 {counts['P1']} / P2 {counts['P2']} / P3 {counts['P3']})",
            "",
            "## Findings",
            "",
        ]
        if not self.findings:
            lines.append("_no findings — clean sweep_")
        for f in self.findings:
            lines.append(f"- **[{f['severity']}] {f['title']}** — `{f['user']}`")
            lines.append(f"  - {f['detail']}")
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int, default=20)
    args = ap.parse_args()
    sweep = Sweep(args.users)
    out = sweep.run()
    print(f"report: {out}")
    print(f"calls: {sweep.calls}  findings: {len(sweep.findings)}")
    for f in sweep.findings[:30]:
        print(f"  [{f['severity']}] {f['user']}: {f['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
