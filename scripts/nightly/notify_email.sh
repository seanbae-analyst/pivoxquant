#!/usr/bin/env bash
# notify_email.sh — SendGrid 이메일 알림 (cron / production 장애용)
# Usage: notify_email.sh "<subject>" "<body>"
#
# Slack webhook 대체 (Slack 워크스페이스 없음). 이미 있는 SENDGRID_API_KEY 재사용.
# SENDGRID_API_KEY 우선순위: env > ~/.pivoxquant-env > repo .env
# 수신: ALERT_EMAIL (default seanbae1521@gmail.com)
# 발신: SENDGRID_FROM_EMAIL (default seanbae1521@gmail.com — SendGrid verified sender)
set -uo pipefail

SUBJECT="${1:-PivoxQuant alert}"
BODY="${2:-(no body)}"
TO="${ALERT_EMAIL:-seanbae1521@gmail.com}"
FROM="${SENDGRID_FROM_EMAIL:-${BRAG_CARD_FROM_EMAIL:-seanbae1521@gmail.com}}"
REPO="/Users/seanbae/Desktop/취준/pivoxquant"

KEY="${SENDGRID_API_KEY:-}"
[ -z "$KEY" ] && [ -f "${HOME}/.pivoxquant-env" ] && KEY=$(grep -E '^(export )?SENDGRID_API_KEY=' "${HOME}/.pivoxquant-env" 2>/dev/null | head -1 | sed -E 's/^(export )?SENDGRID_API_KEY=//' | tr -d '"'"'"'')
[ -z "$KEY" ] && KEY=$(grep -E '^SENDGRID_API_KEY=' "${REPO}/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'"'"'')

if [ -z "$KEY" ]; then
  echo "notify_email: no SENDGRID_API_KEY found — skip"
  exit 0
fi

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
