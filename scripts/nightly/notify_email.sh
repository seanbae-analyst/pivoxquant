#!/usr/bin/env bash
# notify_email.sh — 운영자 이메일 알림 (cron / production 장애용)
# Usage: notify_email.sh "<subject>" "<body>"
#
# Slack webhook 대체 (Slack 워크스페이스 없음).
# 2026-09-29: Brevo 를 먼저 시도한다 (BREVO_API_KEY 또는 레거시 SENDINBLUE_API_KEY
# 가 있을 때). prod 는 SendGrid 키가 죽었고 Brevo 가 1순위다(render.yaml
# BREVO_PROVIDER_PRIMARY) — 파이썬 쪽 순서는 services/email/system_mail.py 가
# 소유한다. Brevo 키가 없거나 Brevo 가 실패하면 예전처럼 SendGrid 로 보낸다.
# 키 우선순위: env > ~/.pivoxquant-env > repo .env
# 수신: ALERT_EMAIL (default seanbae1521@gmail.com)
# 발신: BREVO_FROM_EMAIL / SENDGRID_FROM_EMAIL (default noreply@pivoxquant.com)
set -uo pipefail

SUBJECT="${1:-PivoxQuant alert}"
BODY="${2:-(no body)}"
TO="${ALERT_EMAIL:-seanbae1521@gmail.com}"
REPO="/Users/seanbae/Desktop/취준/pivoxquant"

# lookup_key NAME — env, then ~/.pivoxquant-env, then repo .env
lookup_key() {
  local name="$1" val="${!1:-}"
  [ -z "$val" ] && [ -f "${HOME}/.pivoxquant-env" ] && val=$(grep -E "^(export )?${name}=" "${HOME}/.pivoxquant-env" 2>/dev/null | head -1 | sed -E "s/^(export )?${name}=//" | tr -d '"'"'"'')
  [ -z "$val" ] && val=$(grep -E "^${name}=" "${REPO}/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'"'"'')
  printf '%s' "$val"
}

# ── Brevo (first, when a key exists) ────────────────────────────────────
BREVO_KEY="$(lookup_key BREVO_API_KEY)"
[ -z "$BREVO_KEY" ] && BREVO_KEY="$(lookup_key SENDINBLUE_API_KEY)"
if [ -n "$BREVO_KEY" ]; then
  BREVO_FROM="${BREVO_FROM_EMAIL:-noreply@pivoxquant.com}"
  PAYLOAD=$(SUBJECT="$SUBJECT" BODY="$BODY" TO="$TO" FROM="$BREVO_FROM" python3 -c '
import json, os
print(json.dumps({
    "sender": {"email": os.environ["FROM"], "name": "PivoxQuant"},
    "to": [{"email": os.environ["TO"]}],
    "subject": os.environ["SUBJECT"],
    "textContent": os.environ["BODY"],
}))
')
  CODE=$(curl -sS --max-time 20 -X POST https://api.brevo.com/v3/smtp/email \
    -H "api-key: ${BREVO_KEY}" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json" \
    -d "$PAYLOAD" \
    -o /dev/null -w "%{http_code}" 2>/dev/null || echo "000")
  echo "notify_email: Brevo HTTP ${CODE} (201=queued OK)"
  [ "$CODE" = "201" ] && exit 0
  echo "notify_email: Brevo failed — trying SendGrid"
fi

# ── SendGrid ────────────────────────────────────────────────────────────
KEY="$(lookup_key SENDGRID_API_KEY)"
if [ -z "$KEY" ]; then
  echo "notify_email: no BREVO_API_KEY / SENDGRID_API_KEY found — skip"
  [ -n "$BREVO_KEY" ] && exit 1 || exit 0
fi

# pivoxquant.com SendGrid 도메인 인증 완료 (2026-05-20) → @pivoxquant.com 발신 + 받은편지함 직행
FROM="${SENDGRID_FROM_EMAIL:-noreply@pivoxquant.com}"

# JSON-escape subject/body via python3 (handles quotes/newlines/unicode)
PAYLOAD=$(SUBJECT="$SUBJECT" BODY="$BODY" TO="$TO" FROM="$FROM" python3 -c '
import json, os
print(json.dumps({
    "personalizations": [{"to": [{"email": os.environ["TO"]}]}],
    "from": {"email": os.environ["FROM"]},
    "subject": os.environ["SUBJECT"],
    "content": [{"type": "text/plain", "value": os.environ["BODY"]}],
}))
')

CODE=$(curl -fsS --max-time 20 -X POST https://api.sendgrid.com/v3/mail/send \
  -H "Authorization: Bearer ${KEY}" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  -o /dev/null -w "%{http_code}" 2>/dev/null || echo "000")

echo "notify_email: SendGrid HTTP ${CODE} (202=queued OK)"
[ "$CODE" = "202" ] && exit 0 || exit 1
