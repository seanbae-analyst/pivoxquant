"""Daily healthcheck — probes 5 endpoints, writes result, escalates on failure.

Scheduled at 08:00 KST. Independent of Flask app context (uses its own
SQLAlchemy engine bound to DATABASE_URL) so it survives the web process
being down.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any

import requests
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from agent_worker.config import DATABASE_URL, DEV_LOGIN_SECRET, TARGET_URL
from agent_worker.escalation import notify_healthcheck_result, send_slack

log = logging.getLogger(__name__)

_TIMEOUT = 10
# Capital markets law: BUY/SELL and 추천/조언 are prohibited user-facing terms.
_FORBIDDEN_TERMS = ("BUY", "SELL", "HOLD", "추천", "조언", "매수", "매도")
_ALLOWED_SIGNAL_LABELS = {"POSITIVE", "NEGATIVE", "NEUTRAL"}

_engine: Engine | None = None


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL not set")
        _engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    return _engine


def _login(session: requests.Session) -> bool:
    """POST /api/auth/dev-login to obtain session cookie."""
    if not DEV_LOGIN_SECRET:
        log.warning("dev-login: DEV_LOGIN_SECRET not set — healthcheck skipped")
        return False
    url = f"{TARGET_URL}/api/auth/dev-login"
    try:
        resp = session.post(
            url, json={"secret": DEV_LOGIN_SECRET}, timeout=_TIMEOUT
        )
        return resp.status_code == 200 and resp.json().get("ok") is True
    except Exception as exc:
        log.exception("dev-login failed: %s", exc)
        return False


def _check_portfolio(session: requests.Session) -> dict:
    url = f"{TARGET_URL}/api/portfolio"
    try:
        resp = session.get(url, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return {"check": "portfolio", "ok": False, "reason": f"HTTP {resp.status_code}"}
        data = resp.json()
        if "positions" not in data:
            return {"check": "portfolio", "ok": False, "reason": "missing 'positions' key"}
        return {"check": "portfolio", "ok": True, "positions_count": len(data["positions"])}
    except Exception as exc:
        return {"check": "portfolio", "ok": False, "reason": f"exception: {exc}"}


def _check_quote(session: requests.Session, symbol: str, currency: str) -> dict:
    url = f"{TARGET_URL}/api/market/quote"
    check_name = f"quote_{symbol}"
    try:
        resp = session.get(url, params={"symbol": symbol}, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return {"check": check_name, "ok": False, "reason": f"HTTP {resp.status_code}"}
        data = resp.json()
        price = data.get("price")
        if not isinstance(price, (int, float)) or price <= 0:
            return {
                "check": check_name,
                "ok": False,
                "reason": f"invalid price: {price!r}",
            }
        body_currency = data.get("currency") or ""
        symbol_str = json.dumps(data, ensure_ascii=False)
        if currency not in body_currency and currency not in symbol_str:
            return {
                "check": check_name,
                "ok": False,
                "reason": f"missing currency marker {currency}",
            }
        return {"check": check_name, "ok": True, "price": price}
    except Exception as exc:
        return {"check": check_name, "ok": False, "reason": f"exception: {exc}"}


def _check_indices(session: requests.Session) -> dict:
    url = f"{TARGET_URL}/api/market/indices"
    try:
        resp = session.get(url, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return {"check": "indices", "ok": False, "reason": f"HTTP {resp.status_code}"}
        body = json.dumps(resp.json(), ensure_ascii=False)
        if "KOSPI" not in body.upper() and "코스피" not in body:
            return {"check": "indices", "ok": False, "reason": "KOSPI missing"}
        if "KOSDAQ" not in body.upper() and "코스닥" not in body:
            return {"check": "indices", "ok": False, "reason": "KOSDAQ missing"}
        return {"check": "indices", "ok": True}
    except Exception as exc:
        return {"check": "indices", "ok": False, "reason": f"exception: {exc}"}


def _check_signals(session: requests.Session) -> dict:
    url = f"{TARGET_URL}/api/signals"
    try:
        resp = session.get(url, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return {"check": "signals", "ok": False, "reason": f"HTTP {resp.status_code}"}
        data = resp.json()
        items = data if isinstance(data, list) else data.get("signals") or data.get("items")
        if not isinstance(items, list):
            return {"check": "signals", "ok": False, "reason": "not a list"}
        for item in items:
            label = (item.get("label") or "").upper()
            if label and label not in _ALLOWED_SIGNAL_LABELS:
                return {
                    "check": "signals",
                    "ok": False,
                    "reason": f"forbidden label '{label}' (must be POSITIVE/NEGATIVE/NEUTRAL)",
                    "legal_violation": True,
                }
        return {"check": "signals", "ok": True, "count": len(items)}
    except Exception as exc:
        return {"check": "signals", "ok": False, "reason": f"exception: {exc}"}


def _scan_forbidden_terms(results: list[dict]) -> list[str]:
    """Scan all result bodies for capital-markets-law forbidden terms."""
    hits: list[str] = []
    blob = json.dumps(results, ensure_ascii=False)
    for term in _FORBIDDEN_TERMS:
        if term in blob:
            hits.append(term)
    return hits


def _insert_task(engine: Engine, task_type: str, payload: dict, result: dict, risk: int = 0) -> int:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO agent_tasks (type, status, assigned_to, payload, result,
                                         description, risk_score, completed_at)
                VALUES (:type, 'done', 'healthcheck', :payload, :result,
                        :description, :risk, :now)
                RETURNING id
                """
            ),
            {
                "type": task_type,
                "payload": json.dumps(payload, ensure_ascii=False),
                "result": json.dumps(result, ensure_ascii=False),
                "description": f"Daily healthcheck @ {TARGET_URL}",
                "risk": risk,
                "now": datetime.now(timezone.utc).replace(tzinfo=None),
            },
        ).fetchone()
        return row.id


def _insert_investigate_task(engine: Engine, parent_id: int, failed: list[dict]) -> int:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO agent_tasks (type, status, assigned_to, payload,
                                         description, parent_task_id, chain_depth, risk_score)
                VALUES ('investigate', 'pending', 'investigator', :payload,
                        :description, :parent, 1, :risk)
                RETURNING id
                """
            ),
            {
                "payload": json.dumps({"failed_checks": failed}, ensure_ascii=False),
                "description": f"Investigate {len(failed)} healthcheck failures",
                "parent": parent_id,
                "risk": min(50, 20 + 10 * len(failed)),
            },
        ).fetchone()
        return row.id


def run() -> dict[str, Any]:
    """Entry point — called by APScheduler at 08:00 KST daily."""
    log.info("Daily healthcheck starting (target=%s)", TARGET_URL)
    engine = _get_engine()
    session = requests.Session()

    if not _login(session):
        results = [{"check": "dev_login", "ok": False, "reason": "auth failed"}]
        task_id = _insert_task(engine, "healthcheck_result", {}, {"results": results}, risk=80)
        notify_healthcheck_result(all_ok=False, results=results)
        return {"task_id": task_id, "all_ok": False, "results": results}

    checks = [
        _check_portfolio(session),
        _check_quote(session, "AAPL", "$"),
        _check_quote(session, "005930", "₩"),
        _check_indices(session),
        _check_signals(session),
    ]

    all_ok = all(r.get("ok") for r in checks)
    failed = [r for r in checks if not r.get("ok")]

    legal_violation = any(r.get("legal_violation") for r in checks)
    forbidden_hits = _scan_forbidden_terms(checks)

    risk_score = 0
    if legal_violation or forbidden_hits:
        risk_score = 100
    elif not all_ok:
        risk_score = min(80, 30 + 15 * len(failed))

    task_id = _insert_task(
        engine,
        "healthcheck_result",
        {"target": TARGET_URL, "checks": [c["check"] for c in checks]},
        {"results": checks, "forbidden_terms_hit": forbidden_hits},
        risk=risk_score,
    )

    notify_healthcheck_result(all_ok=all_ok and not forbidden_hits, results=checks)

    if legal_violation or forbidden_hits:
        send_slack(
            f"🚨 [LEGAL] Capital markets violation detected on {TARGET_URL}\n"
            f"Terms: {forbidden_hits or 'forbidden signal label'}\n"
            f"Task: {task_id} — 즉시 확인 필요 (risk=100)"
        )

    investigate_id = None
    if failed:
        investigate_id = _insert_investigate_task(engine, task_id, failed)
        log.info("Queued investigate task %s for %s failures", investigate_id, len(failed))

    return {
        "task_id": task_id,
        "investigate_task_id": investigate_id,
        "all_ok": all_ok,
        "results": checks,
        "forbidden_terms_hit": forbidden_hits,
    }
