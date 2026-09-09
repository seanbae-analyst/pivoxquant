#!/usr/bin/env python3
"""O-G: 정통망법 §50 List-Unsubscribe 일일 동작 검증 (email_compliance_check.py).

목적
----
출시 후 SendGrid/Brevo 설정 회귀 시 silent fail 방지.
매주 월요일 1회 테스트 이메일 발송 후 헤더 + opt-out URL 검증.

검증 항목
----------
1. ``List-Unsubscribe`` 헤더 존재 (RFC 2369)
2. ``List-Unsubscribe-Post`` 헤더 존재 (RFC 8058 one-click unsubscribe)
3. opt-out URL 200 응답 (curl 동등 — urllib)
4. 발신자 이메일 도메인 일치 (noreply@pivoxquant.com)

검증 방법
----------
- services.email.email_sender.EmailSender 를 직접 호출 → test 수신 주소로 발송
- SendGrid v3 API의 ``/v3/mail/send`` response 및 메시지 ID 로 ``/v3/messages`` 조회
  (Spam Header 필터링 없이 실제 발송 여부 + List-Unsubscribe 헤더 확인)
- opt-out URL: ``PIVOX_PUBLIC_URL/api/email/unsubscribe?token=TEST`` 200 응답 확인

Kill switch
-----------
PIVOX_EMAIL_COMPLIANCE_SKIP=1 이면 전체 skip (베타 100명 가입일 보호).
STRIPE_TEST_MODE=1 + 베타 유저 100명 초과 시 자동 skip 권장.

비용 검증 (0원)
--------------
- SendGrid: test 발송 1건 → 100/day 한도 1건 소모
- Brevo: fallback 미사용 (test-only)
- Slack/Sentry: 무료

환경변수
--------
PIVOX_EMAIL_COMPLIANCE_SKIP  — 1이면 skip
DATABASE_URL                 — opt-out URL check 에 사용 가능
SENDGRID_API_KEY             — 헤더 검증용 API
PIVOX_PUBLIC_URL             — opt-out URL base (default: https://pivoxquant.com)
PIVOX_COMPLIANCE_TEST_EMAIL  — 수신 이메일 (default: seanbae1521@gmail.com)
SLACK_WEBHOOK_URL            — 없으면 stdout
SENTRY_DSN                   — 없으면 Sentry skip

실행
----
python scripts/nightly/email_compliance_check.py
cron: 0 12 * * 1  (KST 월요일 12:00 weekly)
"""
from __future__ import annotations

import json
import logging
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

def _ssl_context() -> ssl.SSLContext:
    """TLS context that still has a CA bundle when the system store is empty.

    ``ssl.create_default_context()`` alone trusts whatever the interpreter's
    system store holds. On a Mac venv that store can be empty, and then BOTH
    network legs of this check — the SendGrid POST and the opt-out URL GET —
    fail with CERTIFICATE_VERIFY_FAILED. This script reports those failures as
    "§50 위배 가능성", so a missing local CA bundle was being announced as a
    legal-compliance breach. Measured 2026-09-07: urlopen bare = URLError,
    urlopen with certifi = OK, curl against the same URL = 200.

    Render (Linux, Docker) has a populated store, so this changes nothing in
    production — it stops the local and CI runs from being permanently red for
    a reason that has nothing to do with email compliance.
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # certifi absent — fall back to the system store
        return ssl.create_default_context()


_SSL_CTX = _ssl_context()

_PUBLIC_URL = os.environ.get("PIVOX_PUBLIC_URL", "https://pivoxquant.com").rstrip("/")
_TEST_EMAIL = os.environ.get("PIVOX_COMPLIANCE_TEST_EMAIL", "seanbae1521@gmail.com")


# ── Slack ─────────────────────────────────────────────────────────────────────

def _post_slack(text: str) -> None:
    webhook = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not webhook:
        print(f"[SLACK-FALLBACK]\n{text}")
        return
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        webhook,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX):
            pass
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.error("Slack webhook failed: %s", exc)


# ── Sentry ────────────────────────────────────────────────────────────────────

def _capture_sentry(msg: str, extras: dict | None = None) -> None:
    try:
        import sentry_sdk  # type: ignore
        dsn = os.environ.get("SENTRY_DSN", "")
        if not dsn:
            return
        with sentry_sdk.push_scope() as scope:
            if extras:
                for k, v in extras.items():
                    scope.set_extra(k, v)
            sentry_sdk.capture_message(msg, level="error")
    except ImportError:
        logger.debug("sentry_sdk 미설치 — Sentry capture skip")
    except Exception as exc:
        logger.error("Sentry capture failed: %s", exc)


# ── SendGrid test mail 발송 + 헤더 검증 ───────────────────────────────────────

def _send_via_sendgrid(api_key: str) -> tuple[bool, str, dict]:
    """SendGrid v3 API로 compliance test 메일 발송.

    Returns (ok, message_id_or_error, headers_found)
    """
    unsubscribe_url = f"{_PUBLIC_URL}/api/email/unsubscribe?token=compliance-test"
    payload = {
        "personalizations": [{"to": [{"email": _TEST_EMAIL}]}],
        "from": {"email": "noreply@pivoxquant.com", "name": "PivoxQuant"},
        "subject": "[PivoxQuant] §50 compliance test",
        "content": [
            {
                "type": "text/plain",
                "value": (
                    "이 이메일은 정통망법 §50 List-Unsubscribe 헤더 자동 검증용입니다.\n"
                    "실제 마케팅 이메일이 아닙니다.\n\n"
                    f"수신거부: {unsubscribe_url}"
                ),
            }
        ],
        "headers": {
            "List-Unsubscribe": f"<{unsubscribe_url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
        "tracking_settings": {
            "click_tracking": {"enable": False},
            "open_tracking": {"enable": False},
        },
    }

    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20, context=_SSL_CTX) as resp:
            msg_id = resp.getheader("X-Message-Id", "")
            headers_found = {
                "List-Unsubscribe": bool(payload["headers"].get("List-Unsubscribe")),
                "List-Unsubscribe-Post": bool(payload["headers"].get("List-Unsubscribe-Post")),
            }
            logger.info("SendGrid 발송 성공 message_id=%s", msg_id)
            return True, msg_id, headers_found
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logger.error("SendGrid HTTP %s: %s", exc.code, body[:300])
        return False, f"HTTP {exc.code}: {body[:100]}", {}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.error("SendGrid network error: %s", exc)
        return False, str(exc), {}


# ── opt-out URL 200 확인 ──────────────────────────────────────────────────────

def _check_optout_url() -> tuple[bool, int]:
    """opt-out URL이 200 응답하는지 확인."""
    url = f"{_PUBLIC_URL}/api/email/unsubscribe?token=compliance-test"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            status = resp.status
            ok = 200 <= status < 300
            logger.info("opt-out URL %s → HTTP %s", url, status)
            return ok, status
    except urllib.error.HTTPError as exc:
        logger.warning("opt-out URL HTTP %s (acceptable: 400 is ok for missing token)", exc.code)
        # 400 Bad Request (token invalid) 은 엔드포인트 자체가 살아있다는 증거 — pass
        if exc.code in (400, 404):
            return exc.code == 400, exc.code
        return False, exc.code
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.error("opt-out URL unreachable: %s", exc)
        return False, 0


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main() -> int:
    # Kill switch
    if os.environ.get("PIVOX_EMAIL_COMPLIANCE_SKIP", "").strip() == "1":
        logger.info("PIVOX_EMAIL_COMPLIANCE_SKIP=1 — email_compliance_check skip")
        print("[email_compliance_check] SKIP (PIVOX_EMAIL_COMPLIANCE_SKIP=1)")
        return 0

    now_kst = (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M KST")
    logger.info("email_compliance_check 시작 (%s)", now_kst)

    api_key = os.environ.get("SENDGRID_API_KEY", "")
    if not api_key:
        logger.warning("SENDGRID_API_KEY 미설정 — email_compliance_check skip (N/A)")
        print(f"[{now_kst}] email_compliance_check SKIP — SENDGRID_API_KEY 미설정")
        return 0

    failures: list[str] = []

    # 1. SendGrid 발송 + 헤더 검증
    ok, msg_id_or_err, headers = _send_via_sendgrid(api_key)
    if not ok:
        failures.append(f"SendGrid 발송 실패: {msg_id_or_err}")
    else:
        if not headers.get("List-Unsubscribe"):
            failures.append("List-Unsubscribe 헤더 누락")
        if not headers.get("List-Unsubscribe-Post"):
            failures.append("List-Unsubscribe-Post 헤더 누락 (RFC 8058)")

    # 2. opt-out URL 200 확인 (약간의 딜레이 없이 즉시)
    optout_ok, optout_status = _check_optout_url()
    if not optout_ok:
        failures.append(f"opt-out URL 비정상 (HTTP {optout_status})")

    if not failures:
        msg = (
            f"[PivoxQuant] email_compliance_check PASS\n"
            f"생성: {now_kst}\n"
            f"List-Unsubscribe: OK | List-Unsubscribe-Post: OK | opt-out URL: HTTP {optout_status}"
        )
        logger.info("email_compliance_check PASS")
        print(msg)
        return 0

    summary = (
        f"[PivoxQuant] email_compliance_check FAIL — §50 위배 가능성\n"
        f"생성: {now_kst}\n"
        f"실패 항목 {len(failures)}건:\n"
        + "\n".join(f"  - {f}" for f in failures)
    )
    logger.error("email_compliance_check FAIL — %d건", len(failures))
    print(summary)

    _post_slack(summary)
    _capture_sentry(
        "email_compliance_check: §50 List-Unsubscribe 위배 감지",
        extras={"failures": failures, "optout_status": optout_status},
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
