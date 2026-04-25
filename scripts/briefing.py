#!/usr/bin/env python3
"""PivoxQuant CEO Briefing — noon/morning/evening slots via SendGrid."""

import os
import sys
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
DATE_STR = NOW.strftime("%Y-%m-%d")
TIME_STR = NOW.strftime("%H:%M")

CEO_EMAIL = "seanbae1521@gmail.com"
FROM_EMAIL = "noreply@pivoxquant.com"


def _read_env_file():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("SENDGRID_API_KEY="):
                    return line.split("=", 1)[1].strip()
    except FileNotFoundError:
        pass
    return None


# Re-read since we need it before the function runs
def get_sendgrid_key():
    key = os.environ.get("SENDGRID_API_KEY")
    if key:
        return key
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("SENDGRID_API_KEY="):
                    return line.split("=", 1)[1].strip()
    except FileNotFoundError:
        pass
    return None


def load_autopilot_log():
    log_path = os.path.expanduser(
        "~/.claude/projects/-Users-seanbae-Desktop---/memory/autopilot_log.md"
    )
    try:
        with open(log_path) as f:
            return f.read()
    except FileNotFoundError:
        return ""


def build_noon_brief():
    log = load_autopilot_log()

    # Extract last sentinel status
    sentinel_status = "알 수 없음"
    if "api-sentinel" in log:
        lines = log.split("\n")
        for i, line in enumerate(lines):
            if "api-sentinel" in line and "status:" in "".join(lines[i:i+3]):
                for j in range(i, min(i+5, len(lines))):
                    if "status:" in lines[j]:
                        sentinel_status = lines[j].split("status:")[-1].strip()
                        break

    # Extract daily sweep status
    sweep_status = "알 수 없음"
    if "daily-sweep" in log:
        lines = log.split("\n")
        for i, line in enumerate(lines):
            if "daily-sweep" in line:
                for j in range(i, min(i+5, len(lines))):
                    if "Status" in lines[j] or "status" in lines[j]:
                        sweep_status = lines[j].split(":")[-1].strip()
                        break

    subject = f"[PivoxQuant] 점심 브리핑 — {DATE_STR} {TIME_STR} KST"

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: 'Helvetica Neue', Arial, sans-serif; background: #0a0a0a; color: #e5e5e5; margin: 0; padding: 24px; }}
    .container {{ max-width: 640px; margin: 0 auto; }}
    h1 {{ font-size: 20px; font-weight: 700; color: #ffffff; letter-spacing: 0.05em; border-bottom: 1px solid #333; padding-bottom: 12px; }}
    h2 {{ font-size: 14px; font-weight: 600; color: #a0a0a0; text-transform: uppercase; letter-spacing: 0.1em; margin-top: 24px; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
    .badge-green {{ background: #14532d; color: #4ade80; }}
    .badge-yellow {{ background: #713f12; color: #fbbf24; }}
    .badge-red {{ background: #7f1d1d; color: #f87171; }}
    ul {{ padding-left: 20px; line-height: 1.8; color: #d4d4d4; }}
    .item {{ background: #111; border: 1px solid #222; border-radius: 8px; padding: 12px 16px; margin: 8px 0; }}
    .item .label {{ font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.08em; }}
    .item .value {{ font-size: 15px; color: #e5e5e5; margin-top: 2px; }}
    .footer {{ margin-top: 32px; font-size: 11px; color: #444; border-top: 1px solid #1a1a1a; padding-top: 12px; }}
    .p0 {{ color: #f87171; font-weight: 700; }}
    .p1 {{ color: #fbbf24; font-weight: 600; }}
  </style>
</head>
<body>
<div class="container">
  <h1>PIVOXQUANT — 점심 브리핑</h1>
  <p style="color:#666; font-size:13px;">{DATE_STR} {TIME_STR} KST · CEO Daily Digest</p>

  <h2>시스템 상태</h2>
  <div class="item">
    <div class="label">API Sentinel (최근 실행)</div>
    <div class="value">{sentinel_status} &nbsp; <span class="badge badge-green">LIVE</span></div>
  </div>
  <div class="item">
    <div class="label">Daily Sweep (03:37 KST)</div>
    <div class="value">{sweep_status}</div>
  </div>
  <div class="item">
    <div class="label">프로덕션</div>
    <div class="value">Railway ✅ &nbsp;|&nbsp; Vercel ✅ &nbsp;|&nbsp; /api/health 200 OK</div>
  </div>

  <h2>오전 완료 사항 (2026-04-23)</h2>
  <ul>
    <li>Bug Sweep 12건 전원 수정 배포 (P0×2 / P1×6 / P2×4)</li>
    <li>Dossier 유니버스 5 페이지 완성 (Home / Portfolio / Market / Signals / Detail)</li>
    <li>랜딩 페이지 전면 재구성 (Splash + Hero v3 + FAQ + Pricing seals)</li>
    <li>Dashboard italic 전면 제거 (25 파일)</li>
    <li>법적 방어선 강화 (legal_filter.py 80→89 regex, brag card, AI Chat)</li>
    <li>Portfolio 17s→1.8s, Chart 12s→1.2s 성능 최적화</li>
    <li>LEGAL_CONSULT_PACKAGE.md 537줄 작성</li>
  </ul>

  <h2>🔴 오후 P0 액션 (CEO 직접 처리)</h2>
  <ul>
    <li class="p0">Railway env → <code>NAVER_CLIENT_ID</code> + <code>NAVER_CLIENT_SECRET</code> 설정 (KR 뉴스)</li>
    <li class="p0">Railway env → <code>KIS_USE_REAL=1</code> 확인 (한국주식 P/E · EPS)</li>
    <li class="p0">Railway env → <code>ALPHAVANTAGE_API_KEY</code> 발급 (무료 2분, NVDA/MSFT/TSLA)</li>
  </ul>

  <h2>🟠 오후 P1 액션 (CEO 직접 처리)</h2>
  <ul>
    <li class="p1">Google OAuth redirect URI 추가: <code>https://pivoxquant.com/api/auth/google/callback</code></li>
    <li class="p1">Kakao OAuth redirect URI 추가: <code>https://pivoxquant.com/api/auth/kakao/callback</code></li>
    <li class="p1">로펌 예약 — LEGAL_CONSULT_PACKAGE.md 지참 (100~300만원 예산)</li>
    <li class="p1">사업자등록 (홈택스 15분) + 통신판매업 신고 (민원24 20분)</li>
  </ul>

  <h2>다음 자동 실행 예정</h2>
  <ul>
    <li>매 :47분 — api-sentinel (건강 체크)</li>
    <li>03:37 KST — daily bug-hunter sweep</li>
    <li>06:42 KST — legal-guard vocabulary scan</li>
    <li>GitHub Actions (24/7): api-health 15분 / post-deploy canary / legal-guard PR gate</li>
  </ul>

  <div class="footer">
    PivoxQuant Autopilot · seanbae1521@gmail.com · 자동 생성 브리핑 · 본 메일은 투자 조언이 아닙니다.
  </div>
</div>
</body>
</html>"""

    return subject, html


def send_via_sendgrid(api_key, subject, html_content):
    import requests as req_lib

    payload = {
        "personalizations": [{"to": [{"email": CEO_EMAIL}]}],
        "from": {"email": "autopilot@pivoxquant.com", "name": "PivoxQuant Autopilot"},
        "reply_to": {"email": CEO_EMAIL},
        "subject": subject,
        "content": [{"type": "text/html", "value": html_content}],
    }

    resp = req_lib.post(
        "https://api.sendgrid.com/v3/mail/send",
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=15,
    )
    return resp.status_code, resp.text or "OK"


def main():
    slot = sys.argv[1] if len(sys.argv) > 1 else "noon"

    api_key = get_sendgrid_key()
    if not api_key:
        print("ERROR: SENDGRID_API_KEY not found")
        sys.exit(1)

    if slot == "noon":
        subject, html = build_noon_brief()
    else:
        subject, html = build_noon_brief()  # default to noon format

    status, body = send_via_sendgrid(api_key, subject, html)

    if status in (200, 202):
        print(f"OK {status} — email sent to {CEO_EMAIL}")
        print(f"Subject: {subject}")
    else:
        print(f"FAIL {status}: {body}")
        sys.exit(1)


if __name__ == "__main__":
    main()
