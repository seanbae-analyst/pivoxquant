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


# ---------------------------------------------------------------------------
# 2026-05-15: stronger assertions — CAUS was reporting "0 findings clean"
# while bug-hunter (manual agent) found 9 launch-blocker bugs on the same
# surfaces in the same period. Root cause: scenarios only checked HTTP 200
# + keyword presence + 5xx absence. A real user looks at the rendered
# numbers and goes "this is ₩0, broken." These helpers give scenarios that
# same shape of judgment so they actually catch the bug-hunter-class
# regressions next tick.
# ---------------------------------------------------------------------------

# Money-formatted strings the frontend emits via fmtMoney / fmtMoneyCell.
# KRW: "₩" + digits (no decimals, ko-KR thousand sep).
# USD: "$" + digits + "." + 2 decimals (en-US thousand sep).
# Negative form prepends "-".
_MONEY_KRW_RE = re.compile(r"-?₩(?:0|[1-9][\d,]*)")
_MONEY_USD_RE = re.compile(r"-?\$(?:0\.\d{2}|[1-9][\d,]*\.\d{2})")
_MONEY_ZERO_KRW = "₩0"
_MONEY_ZERO_USD_RE = re.compile(r"\$0\.0+\b")


def find_pervasive_zero_money(
    text: str, *, min_total_money: int = 2
) -> tuple[int, int]:
    """Count money-formatted strings + how many are literal-zero.

    Returns (total_money_strings, zero_money_strings). A scenario can
    treat ``total >= min_total_money and zero == total`` as P0 — the
    page is rendering money everywhere but every single value is zero,
    indistinguishable from "every position is worthless" only by being
    impossible (positions wouldn't all be exactly zero in a real book).

    Calibrated against the 2026-05-15 P0 bug: bug-hunter saw all 4
    Holdings rows render as ``₩0 / $0.00 / 0.00%`` for every user
    because the frontend read ``avg_cost`` / ``current_price`` against
    a payload that emitted camelCase. CAUS day3 scenario didn't catch
    it because it only checked page-load + 7-Layer-keyword presence.

    NOT a fingerprint for ad-hoc zero rows (a user might genuinely
    own a stock that's gone to zero in a single position). The
    pervasive-zero pattern only fires when EVERY money string the page
    rendered is zero AND the page rendered at least ``min_total_money``
    money strings (so a placeholder skeleton with one "₩0" doesn't
    false-positive).
    """
    krw_all = _MONEY_KRW_RE.findall(text)
    usd_all = _MONEY_USD_RE.findall(text)
    total = len(krw_all) + len(usd_all)
    if total < min_total_money:
        return total, 0
    zero_krw = sum(1 for s in krw_all if s == _MONEY_ZERO_KRW or s == "-₩0")
    zero_usd = sum(1 for s in usd_all if _MONEY_ZERO_USD_RE.fullmatch(s.lstrip("-")))
    return total, zero_krw + zero_usd


# Internal trace IDs that occasionally leak into JSX (Companion request_id
# was a 12-char uppercase hex chunk). General pattern: long hex
# sequences in visible text that aren't a known SHA / build hash position.
_INTERNAL_HEX_RE = re.compile(r"\b[0-9A-F]{12,16}\b")


def grep_internal_hex_id(text: str) -> list[str]:
    """Return uppercase-hex strings 12-16 chars long appearing in visible text.

    Calibrated against the 2026-05-15 Companion finding (PR #384): the
    backend request_id was rendered as "919790CD3943" above every AI
    bubble. End users have no use for an internal trace tag and it
    reads as debug-mode leakage in production. This catches the
    pattern in any scenario that visits a chat / artifact page.

    Returns empty list when clean.
    """
    hits: list[str] = []
    seen: set[str] = set()
    for m in _INTERNAL_HEX_RE.finditer(text):
        v = m.group(0)
        if v not in seen:
            seen.add(v)
            hits.append(v)
    return hits


# Docker absolute paths that occasionally leak into API responses (the
# Bug #7 artifact path leak shipped with PR #379's d1cb297b but a future
# regression should re-fire this). Matches "/app/..." prefixes in visible
# text only — JSON API responses are out of CAUS scope.
_DOCKER_PATH_RE = re.compile(r"/app/[\w./\-]+")


def grep_container_path_leak(text: str) -> list[str]:
    """Return ``/app/<path>`` occurrences visible to the user.

    Calibrated against Bug #7 (PR #379): artifact API used to emit
    ``pdf_path: '/app/artifacts/brag_card/.../2026-04_Brag_Card.png'``,
    a Railway container path of no use to the user.
    """
    hits: list[str] = []
    seen: set[str] = set()
    for m in _DOCKER_PATH_RE.finditer(text):
        v = m.group(0)
        if v not in seen:
            seen.add(v)
            hits.append(v)
    return hits


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
