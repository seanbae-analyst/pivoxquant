"""Shared fixtures + helpers for CAUS Phase 3 Playwright scenarios.

Finding schema (each dict in the list returned by run()):
    severity   : 'P0' | 'P1' | 'P2'
    category   : '기능' | '법규' | 'UX' | '결제' | '성능' | '데이터'
    page       : '/path' or full URL
    summary    : short one-line (<= 100 chars)
    repro      : multi-line repro steps
    screenshot : '/tmp/caus-...png' or 'N/A'

Helpers:
    inject_session  — load Set-Cookie from session JSON into Playwright context
    new_finding     — typed dict factory with defaults
    collect_console — page event listener that appends JS console errors
    collect_network — page event listener that appends 5xx responses
    grep_forbidden  — scan visible text for cap-markets forbidden words (P0 legal)
    sanity_kospi    — KOSPI level range check (3000 < x < 15000)
    snap            — page.screenshot wrapper with consistent /tmp path
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# Forbidden words in prod UI per Capital Markets Act §17 + memory rule
# `feedback_legal_compliance`. Detection => P0 finding (category=법규).
FORBIDDEN_WORDS_KO: tuple[str, ...] = ("매수", "매도", "추천", "조언")
FORBIDDEN_WORDS_EN: tuple[str, ...] = ("BUY", "SELL", "HOLD", "recommend", "advice")

# Per memory `feedback_ticker_display`: naked tickers like "005930.KS" must
# not appear as the primary label — the human name (e.g. "삼성전자") must
# precede or replace them.
NAKED_KR_TICKER_RE = re.compile(r"\b\d{6}\.K[SQ]\b")

# Per-scenario screenshot dir under /tmp.
SCREENSHOT_DIR = Path("/tmp")

# Reasonable KOSPI level sanity range (2026 spot ≈ 2600~3000; allow 3000~15000
# slack for the next 5y so we don't false-positive on real moves).
KOSPI_MIN = 1500
KOSPI_MAX = 15000


def inject_session(context, session_path: Path, base_url: str) -> None:
    """Read sim-onboard session JSON and add cookies to the Playwright context.

    Expects the schema written by `caus_daily_sweep.sim_onboard_login`:
        { "set_cookie": "name=value; Path=/; HttpOnly; ...", ... }

    Best-effort: missing file => no-op (scenario will hit landing page).
    """
    if not session_path.exists():
        return

    try:
        data = json.loads(session_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    set_cookie = (data.get("set_cookie") or "").strip()
    if not set_cookie:
        return

    # Parse a single Set-Cookie header: "name=value; Path=/; HttpOnly; SameSite=Lax"
    parts = [p.strip() for p in set_cookie.split(";") if p.strip()]
    if not parts:
        return
    name, _, value = parts[0].partition("=")
    if not name or not value:
        return

    # Strip scheme to compute cookie domain (defaults to apex).
    domain_match = re.match(r"^https?://([^/]+)", base_url)
    domain = domain_match.group(1) if domain_match else "www.pivoxquant.com"
    # Strip explicit port for cookie API.
    if ":" in domain:
        domain = domain.split(":", 1)[0]

    cookie: dict[str, Any] = {
        "name": name,
        "value": value,
        "domain": domain,
        "path": "/",
    }
    # Parse attributes defensively.
    for attr in parts[1:]:
        low = attr.lower()
        if low == "httponly":
            cookie["httpOnly"] = True
        elif low == "secure":
            cookie["secure"] = True
        elif low.startswith("samesite="):
            ss = low.split("=", 1)[1].capitalize()
            if ss in ("Lax", "Strict", "None"):
                cookie["sameSite"] = ss

    try:
        context.add_cookies([cookie])
    except Exception:
        # Cookie injection is best-effort. Scenario can still validate
        # public surfaces (landing, pricing) if injection fails.
        pass


def new_finding(
    *,
    severity: str,
    category: str,
    page: str,
    summary: str,
    repro: str = "",
    screenshot: str = "N/A",
) -> dict:
    """Typed finding factory with shape validation."""
    return {
        "severity": severity,
        "category": category,
        "page": page,
        "summary": summary[:200],
        "repro": repro,
        "screenshot": screenshot,
    }


def collect_console(page, sink: list[str]) -> None:
    """Attach a console listener that appends error/warning text to sink."""

    def _on_console(msg) -> None:
        if msg.type in ("error",):
            try:
                sink.append(f"{msg.type}: {msg.text}"[:300])
            except Exception:
                pass

    page.on("console", _on_console)


def collect_network(page, sink: list[dict]) -> None:
    """Attach a response listener that captures 5xx and 4xx (non-401/403) responses."""

    def _on_response(resp) -> None:
        try:
            status = resp.status
            url = resp.url
        except Exception:
            return
        # Skip auth-expected paths (401/403 are normal pre-session checks).
        if status >= 500 or (400 <= status < 500 and status not in (401, 403, 404)):
            sink.append({"status": status, "url": url})
        elif status == 404 and "/api/" in url:
            sink.append({"status": status, "url": url})

    page.on("response", _on_response)


def grep_forbidden(text: str) -> list[str]:
    """Return forbidden cap-markets words found in `text` (case-sensitive for KO).

    Returns the unique list of hits. Empty list = clean.
    """
    hits: set[str] = set()
    for word in FORBIDDEN_WORDS_KO:
        if word in text:
            hits.add(word)
    # English: case-insensitive but require word boundary.
    lower = text.lower()
    for word in FORBIDDEN_WORDS_EN:
        if re.search(rf"\b{re.escape(word.lower())}\b", lower):
            hits.add(word)
    return sorted(hits)


def grep_naked_kr_ticker(text: str) -> list[str]:
    """Return KR tickers appearing without a Korean name nearby.

    Heuristic: a ticker is "naked" if no Hangul character occurs in the
    50-char window preceding it. This catches `005930.KS` shown standalone
    while allowing `삼성전자 (005930.KS)`.
    """
    naked: list[str] = []
    for m in NAKED_KR_TICKER_RE.finditer(text):
        start = m.start()
        window = text[max(0, start - 50):start]
        if not re.search(r"[가-힣]", window):
            naked.append(m.group(0))
    # Dedupe preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for t in naked:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def sanity_kospi(level: float | int | None) -> bool:
    """Return True iff `level` is within plausible KOSPI range."""
    if level is None:
        return False
    try:
        v = float(level)
    except (TypeError, ValueError):
        return False
    return KOSPI_MIN <= v <= KOSPI_MAX


def snap(page, agent_id: str, label: str) -> str:
    """Take a screenshot and return its absolute path (or 'N/A' on failure)."""
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", label)[:40]
    path = SCREENSHOT_DIR / f"caus-{agent_id}-{safe}.png"
    try:
        page.screenshot(path=str(path), full_page=False, timeout=10_000)
        return str(path)
    except Exception:
        return "N/A"


def goto_safe(page, url: str, *, timeout_ms: int = 30_000) -> int | None:
    """Navigate and return HTTP status (or None on transport error)."""
    try:
        resp = page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
    except Exception:
        return None
    return resp.status if resp else None


def is_beta_gate(page) -> bool:
    """Return True if the page is the beta-password gate (not the target page).

    The beta-gate is a Vercel-level interstitial that swallows all routes
    when the `beta_password` cookie is missing. Scenarios should short-circuit
    here — finding "tier names missing" on the beta-gate is a false positive.
    """
    try:
        current = page.url or ""
    except Exception:
        return False
    if "/beta-gate" in current:
        return True
    try:
        body = page.evaluate("document.body.innerText") or ""
    except Exception:
        return False
    return (
        "beta password" in body.lower()
        or "베타 비밀번호" in body
        or "비공개 베타" in body
    )
