# PivoxQuant — Incident Response Runbook

> **작성**: 2026-05-28 / **대상**: CEO 1인 운영 / **출시 시점**: D-day 임박
> **범위**: 결제 활성화 이후 첫 7일 최우선 5 시나리오
> **전제**: 0원 툴셋 전용 (Sentry free / Slack free / UptimeRobot free)

---

## 우선순위 정의

| 등급 | 기준 | 대응 SLA |
|------|------|----------|
| P0 | 결제 영향 / 데이터 유출 / 전면 다운 | 즉시 (CEO 직접) |
| P1 | UI 버그 / 성능 저하 / 부분 기능 불능 | 24h 내 |
| P2 | Cosmetic / 잔존 drift | 주간 회고 |

---

## 시나리오 1 — 결제 실패 / 중복 결제 / Stripe webhook 누락 [P0]

### 탐지

- Sentry: `billing/` 네임스페이스 error spike
- Stripe Dashboard: Events 탭 → `charge.failed` / `payment_intent.payment_failed` / webhook `failed_attempts > 0`
- 유저 문의: 이메일 수신 (`seanbae1521@gmail.com`) 또는 챗봇 상담접수

### 즉시 액션 (30분 이내)

1. **Stripe Dashboard** → Customers 검색 → Payments 탭 → Refund (사유: `duplicate` 또는 `fraudulent`)
2. 유저에게 아래 **통신 템플릿 1** 발송 (Gmail)
3. DB 정합성 점검:

```sql
-- 중복 결제 확인
SELECT user_id, COUNT(*), SUM(amount)
FROM payments
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY user_id
HAVING COUNT(*) > 1;

-- subscription tier vs payments 불일치
SELECT u.email, s.tier, s.status, p.amount, p.status
FROM subscriptions s
JOIN users u ON u.id = s.user_id
LEFT JOIN payments p ON p.user_id = s.user_id
WHERE s.status = 'active'
  AND (p.status IS NULL OR p.status = 'failed')
ORDER BY s.updated_at DESC
LIMIT 20;
```

### 근본 조사

- Stripe CLI로 webhook 재발송: `stripe events resend evt_XXXXXXXXX`
- `services/billing/` 로그: Railway 대시보드 → Logs → `webhook` 키워드 필터
- stale fallback 패턴 (feedback_bug_fix_patterns #1): `subscriptions.current_period_end` vs 실제 Stripe 상태 확인

### 복구 옵션

- webhook 재발송으로 자동 tier 복구 가능 (idempotency key 보호 확인)
- 자동 복구 불가 시: DB 직접 `UPDATE subscriptions SET tier='pro', status='active' WHERE user_id=...`
- 재발 방지: `stripe listen --forward-to localhost:5050/api/billing/webhook` 로 로컬 재현 후 패치

---

## 시나리오 2 — OAuth 로그인 전면 불능 (v46 재현) [P0]

> 참고: 2026-05-20 v46 사고 — Railway PG `FATAL: sorry, too many clients` → 22h 다운

### 탐지

- Sentry: `oauth/google/callback` error spike 또는 `500` 비율 급등
- 가입 폼 conversion 0% (Google Analytics / Vercel Analytics)
- 헬스체크: `curl https://web-production-7b484b.up.railway.app/health` → 비응답 또는 500

### 즉시 액션 (15분 이내)

1. **PG 커넥션 사용량 확인** (Railway → Postgres → Data → Query):

```sql
SELECT count(*), state
FROM pg_stat_activity
WHERE datname = current_database()
GROUP BY state;
```

2. **pool 포화 확인**: max_connections 초과 시 Postgres 서비스 재시작 (Railway → Postgres → Restart)
3. **최근 deploy 상태 확인**: Railway 대시보드 → Deployments → 실패한 deploy 있으면 이전 성공 버전으로 Rollback
4. `config.py` pool 설정 확인: `pool_size=3, max_overflow=2, pool_recycle=300` (v46 fix 값)

### 근본 조사

- `_do_migrations` self-heal 7개 가드 동작 확인: `services/db.py` 또는 `app.py` 내 `_do_migrations` 로그 검색
- 컬럼 누락 여부: `deletion_requested_at`, `deleted_at` — ORM vs prod 스키마 diff
- 참고: `project_prod_schema_selfheal` — prod는 `db.create_all()` + `_do_migrations()` self-heal, alembic 런타임 미실행

### 복구 옵션

| 상황 | 조치 |
|------|------|
| PG 커넥션 고갈 | Railway Postgres 재시작 |
| 코드 배포 실패 | `railway up --service 8687c9ac` (CEO 직접 — 브라우저 OAuth 필요) |
| 스키마 불일치 | `_do_migrations` self-heal 재실행 (서버 재시작으로 트리거) |

---

## 시나리오 3 — AI 산출물 §101 위반 의심 [P0]

> 자본시장법 §101: 불특정 다수 투자자 대상 투자조언 금지

### 탐지

- `legal-kr-fintech` agent 정기 스캔 (법규 스캔 크론) 결과
- 유저 신고: "이 AI가 OO 주식 사라고 했다"
- 규제기관 문의 (이메일 / 공문)

### 즉시 액션 (1시간 이내)

1. **해당 artifact 즉시 비공개**:

```sql
UPDATE artifacts
SET is_public = false, updated_at = NOW()
WHERE id = '<artifact_id>';
```

2. `services/legal/filter.py` 로 해당 텍스트 재검증:

```python
# 로컬 확인
from services.legal.filter import LegalFilter
f = LegalFilter()
result = f.scan("<artifact 텍스트>")
print(result.violations)
```

3. `services/legal/engine.py` 에서 해당 패턴이 누락됐으면 즉시 패치 후 배포
4. 동일 템플릿으로 생성된 다른 artifact 전수 확인:

```sql
SELECT id, user_id, artifact_type, created_at
FROM artifacts
WHERE template_id = '<template_id>'
  AND created_at > NOW() - INTERVAL '7 days';
```

### 근본 조사

자본시장법 §101 4요건 체크:

| 요건 | 확인 사항 |
|------|----------|
| 불특정 다수 | 1명 유저 전용인지, 공개 공유됐는지 |
| 투자조언 | "매수/매도" 명시 여부 (case-sensitive, 의도적 설계) |
| 특정성 | 특정 종목 + 수익률 예측 동시 존재 |
| 대가성 | 유료 구독 내 포함 여부 |

- `legal_decision_no_advisory` 참조: §101 면제 트랙 유지 조건 재확인
- take-profit / stop-loss 패턴 포함 여부 (v44.9 법규 fix 사례)

### 복구 옵션

- artifact 비공개 처리 (즉시)
- 동일 패턴 생성 차단 (engine.py 패치 + 배포)
- 영구 차단이 필요한 경우 template 삭제 또는 disabled 처리
- 변호사 무료 재상담 대상으로 Q-S4 항목에 추가

---

## 시나리오 4 — PIPA 사고 (데이터 유출 / 권한 우회 / cross-user 누수) [P0]

> PIPA §34: 72시간 내 KISA 신고 의무 / §28-8: 10% 과징금 상한

### 탐지

- Sentry: `403` → `200` 전환 이상 패턴 (권한 우회)
- 유저 신고: "다른 사람 데이터가 보인다"
- 보안 audit: cross-user 캐시 키 충돌 (`SignalCache`, `EarningsCache`)

### 즉시 액션 (6시간 이내)

1. **영향 범위 확정**:

```sql
-- 의심 구간 액세스 로그
SELECT user_id, endpoint, accessed_at, response_code
FROM access_logs
WHERE accessed_at BETWEEN '<사고 시작>' AND '<발견 시점>'
  AND response_code = 200
  AND endpoint LIKE '%/api/signals%'
ORDER BY accessed_at;

-- cross-user 데이터 노출 확인
SELECT DISTINCT user_id, data_owner_id
FROM signal_cache
WHERE user_id != data_owner_id;
```

2. **해당 endpoint 즉시 차단** (nginx / Railway 환경변수 `FEATURE_FLAG_SIGNALS_ENABLED=false` 또는 maintenance 모드)
3. **72h 내 KISA 신고** (개인정보보호위원회):
   - 신고 URL: https://privacy.go.kr (개인정보침해신고센터)
   - 신고 필요 정보: 유출 일시, 유출 항목, 영향받은 사용자 수, 조치 내역
4. **영향받은 사용자 개별 통보** (이메일, 유출 사실 + 조치 내역)

### 근본 조사

v44.9 SignalCache cross-user 사례 패턴:

- 캐시 키에 `user_id` 포함 여부 확인: `cache_key = f"signals:{user_id}:{ticker}"`
- `@api_auth` 데코레이터 누락 endpoint 전수 확인
- cookie tampering: `session['user_id']` 검증 로직 확인

참조: `feedback_bug_fix_patterns` 패턴 5 (cross-user leak) / 패턴 6 (data integrity) / 패턴 7 (SWR dedup)

### 복구 옵션

- 오염된 캐시 flush: `redis-cli FLUSHDB` 또는 Railway 캐시 재시작
- DB에 직접 저장된 cross-user 데이터: 해당 row 격리 (`quarantined=true`)
- 법적 책임 한도: Q11 (변호사 답변 수령 후 약관 손해배상 한도 반영)

---

## 시나리오 5 — Railway / Vercel / DNS 다운 [P0 or P1]

### 탐지

- UptimeRobot 알림 (free tier — 50 모니터, 5분 인터벌)
  - 모니터 대상: `https://pivoxquant.com` + `https://web-production-7b484b.up.railway.app/health`
- 자체 크론: `*/5 * * * * curl -s https://pivoxquant.com/health || notify`
- Railway 자동배포 실패 알림 (GitHub 연동)

### 즉시 액션 (10분 이내)

1. **플랫폼 상태 확인**:
   - Railway: https://status.railway.app
   - Vercel: https://www.vercel-status.com
   - Cloudflare: https://www.cloudflarestatus.com (DNS CDN 경유 시)

2. **상태 정상 → 자체 코드 문제**:
   - Railway 대시보드 → 최근 deploy Rollback (이전 성공 버전)
   - Vercel 대시보드 → Deployments → Rollback

3. **플랫폼 다운 → 사용자 공지** (아래 **통신 템플릿 2** 발송)

4. **DNS 전파 문제** (가비아 변경 후 24~48h 전파 지연):
   - 확인: `dig pivoxquant.com @8.8.8.8`
   - 임시: 유저에게 직접 IP 또는 Railway URL 안내

### 근본 조사

- Railway 자동배포 실패 원인: GitHub Actions 빌드 로그 확인
- Vercel 빌드 실패: tsc 에러 / 환경변수 누락 확인
- `.railwayignore` leading-slash 확인: `/frontend`, `/venv`, `/.git` (unanchored 시 `services/artifacts/` 오매칭)

### 복구 옵션

| 상황 | 조치 |
|------|------|
| Railway 다운 | 대기 (SLA 99.9% — 월 43분 이내) / 상태 페이지 확인 후 공지 |
| 코드 배포 실패 | `railway up --service 8687c9ac` (CEO 직접) |
| Vercel 다운 | 대기 또는 Railway에서 Next.js standalone 임시 서빙 |
| DNS 전파 지연 | 가비아 TTL 300초 단축 후 24h 대기 |

---

## 공통 통신 템플릿

### 템플릿 1 — 결제 문제 사과 + 환불 안내

```
제목: [PivoxQuant] 결제 관련 불편을 드려 죄송합니다

안녕하세요, PivoxQuant 팀입니다.

고객님의 결제 과정에서 예기치 않은 오류가 발생하여 불편을 드렸습니다.
확인 결과 [중복 결제 / 결제 실패]가 발생하였으며, 해당 금액은
영업일 기준 3~5일 이내 원래 결제 수단으로 전액 환불 처리될 예정입니다.

환불 처리 번호: [Stripe 환불 ID]
환불 예정일: [날짜]

이용에 불편을 드려 진심으로 사과드립니다.
추가 문의사항은 이 이메일로 회신해 주시면 빠르게 도움드리겠습니다.

PivoxQuant 드림
```

### 템플릿 2 — 서비스 다운 공지

```
제목: [PivoxQuant] 서비스 일시 점검 안내

안녕하세요, PivoxQuant 팀입니다.

현재 인프라 점검으로 인해 서비스 이용이 일시적으로 제한될 수 있습니다.
빠른 복구를 위해 최선을 다하고 있으며, 복구 완료 즉시 별도 안내드리겠습니다.
이용에 불편을 드려 죄송합니다.

PivoxQuant 드림
```

---

## Observability 통합 — Sentry + Slack + Brevo (0원)

T6에서 박은 0원 통합 스택. **추가 비용 0원** 유지:
SendGrid 100/day + Brevo 300/day + Sentry 5k events/mo + Slack webhook free.

### Sentry alert rule (Sentry 콘솔 UI에서 CEO 직접 생성)

`SENTRY_DSN` 은 `app.py:97`에서 init 완료 (`traces_sample_rate=0.2`,
`send_default_pii=False`, `before_send=_sentry_filter` 노이즈 필터 박혀있음).
명시 capture 사용처: `services/billing_followup.py` x2 / `services/billing_notifications.py` x3 /
`services/observability/alerts.py` (cron failure SoT).

권장 alert rule 3개 (Sentry → Alerts → Create Alert Rule):

| 등급 | Rule 이름 | 조건 | 액션 | Why |
|------|----------|------|------|-----|
| **P0** | `5xx error rate > 5%` | `event.type:error AND http.status_code:>=500` count > 5%/5min window | Slack `#pivox-alerts` + CEO 이메일 | 전면 다운 / 마이그레이션 누락 (v46 OAuth 사고 재발 방지) |
| **P1** | `KIS 429 burst` | message contains `429` AND tag `module:kis_service` count > 3/10min | Slack `#pivox-alerts` | KIS 토큰 / rate limit 초과 — 한국 시세 끊김 |
| **P2** | `Cron job failure` | tag `cron_job_id:*` (alerts.emit_failure 가 set) count >= 1 | Slack only | 26 APScheduler 잡 실패 — 3회 연속이면 alerts.py 자체 auto-pause |

⚠ **CEO 액션**: Sentry 콘솔에서만 생성 가능 (코드 변경 X).
DSN 확인 명령: `railway variables -s 8687c9ac | grep SENTRY_DSN`.

### Slack 채널 권장 구조 (단일 채널 시작 — noise 적음)

| 채널 | webhook env | 용도 | 단계 |
|------|------------|------|------|
| `#pivox-alerts` | `SLACK_WEBHOOK_URL` (단일) | P0~P2 통합 — Sentry / billing / cron / api-health | **출시 시점 (지금)** |
| `#pivox-billing` | `SLACK_WEBHOOK_BILLING` (미래) | Stripe 결제 실패 / dispute / past_due 전용 분리 | MRR > ₩100만 후 |
| `#pivox-legal` | `SLACK_WEBHOOK_LEGAL` (미래) | §101 위반 의심 / PIPA 사고 전용 분리 | 변호사 의견서 도착 후 |

⚠ **현재 코드는 단일 `SLACK_WEBHOOK_URL` 만 사용** — 분리하려면
`services/observability/alerts.py:_slack_post` 분기 추가 필요 (미래 작업).

### Brevo fallback 활성화 절차 (5 step, 0원)

코드는 이미 박혀있음 (`services/email/sender.py:374~470` cascade
+ `services/email/brevo_provider.py` 433줄). `BREVO_API_KEY` env만 비어있는
상태 → 현재 SendGrid 100/day 초과 시 SMTP로만 fallback (= 사실상 dev-mode
로그만, prod SMTP 미설정).

1. https://www.brevo.com/ 가입 (이메일 인증, 5분)
2. **SMTP & API → API Keys** → "Create a new API key" (v3 transactional 권한)
3. **Senders, Domains & Dedicated IPs** → `pivoxquant.com` 도메인 추가 →
   가비아 DNS에 Brevo가 안내하는 DKIM (`mail._domainkey`) + SPF include 추가
   (기존 SendGrid `v=spf1` 레코드와 공존 가능, `include:spf.brevo.com` 추가만)
4. Railway env에 등록:
   ```
   railway variables -s 8687c9ac --set "BREVO_API_KEY=<생성한키>"
   railway variables -s 8687c9ac --set "BREVO_FROM_EMAIL=reports@pivoxquant.com"
   railway variables -s 8687c9ac --set "BREVO_FROM_NAME=PivoxQuant Research"
   ```
5. 자동 재배포 후 `tests/test_sendgrid_quota.py::test_*brevo*` 패턴
   라이브 검증 (또는 SendGrid 키 잠깐 unset 후 1통 발송으로 cascade 발동 확인)

**SendGrid 100/day 한도 도달 시 자동 cascade 시나리오:**
- SendGrid SDK 가 429 → `SendGridRateLimitExceeded` raise →
  `sender.py:449` for-loop 다음 tier (Brevo) 진입 → Brevo 300/day 소진까지 OK
- Brevo 도 429 → SMTP (미설정 → False return + log) → 발송 실패 + Slack 알림

### Alert 받았을 때 CEO 첫 30분 체크리스트

P0 Sentry alert 또는 Slack `:rotating_light:` 메시지 수신 시:

- [ ] **1분**: Sentry 이벤트 → stack trace → 어느 endpoint / cron / module
- [ ] **5분**: `railway logs -s 8687c9ac | tail -100` — 최근 ERROR 확인
- [ ] **10분**: `curl https://web-production-7b484b.up.railway.app/health` →
  200 + `{"status":"ok"}` 확인 (전면 다운인지 확인)
- [ ] **15분**: Stripe 결제면 → [시나리오 1](#시나리오-1) /
  OAuth면 → [시나리오 2](#시나리오-2) / §101 의심이면 → [시나리오 3](#시나리오-3)
- [ ] **30분**: cron 3회 연속 실패면 `alerts.py` 가 이미 auto-pause —
  Railway 로그에서 `cron AUTO-PAUSE` 메시지 grep → 원인 fix 후 재배포 (=resume)

---

## 모니터링 체크리스트 (D+1 ~ D+7)

### 설정 (출시 당일 완료)

- [ ] **Sentry** (free: 5,000 events/월): `SENTRY_DSN` Railway + Vercel env 확인
  - 알림 채널: Slack webhook 또는 이메일
  - 알림 조건: 위 "Observability 통합" 섹션 alert rule 3개 적용
- [ ] **UptimeRobot** (free: 50 모니터, 5분 인터벌):
  - 모니터 1: `https://pivoxquant.com` (HTTP 200)
  - 모니터 2: `https://web-production-7b484b.up.railway.app/health`
  - 알림: `seanbae1521@gmail.com`
- [ ] **Slack webhook** (free): `#pivox-alerts` 채널 → Sentry + UptimeRobot 알림 수신
  - env: `SLACK_WEBHOOK_URL` (Railway + 로컬 `.env`)
- [ ] **Brevo fallback** (free 300/day): `BREVO_API_KEY` Railway env 등록
  - 위 "Brevo fallback 활성화 절차" 5 step 따라
- [ ] **GitHub Actions** 결과 (무료 2,000분/월): pytest / vitest 실패 시 이메일 알림

### 매일 09:00 KST (장 개장 30분 전)

- [ ] `curl https://web-production-7b484b.up.railway.app/health` → `{"status":"ok"}` 확인
- [ ] Railway Logs: `ERROR` 키워드 grep (최근 12h)
- [ ] Sentry: 새 이슈 / error spike 확인
- [ ] KIS 토큰 갱신 잡 정상 실행 여부 (토큰 24h 만료 — 새벽 갱신 크론)

### 매일 22:30 KST (US 시장 개장 직전)

- [ ] Stripe Dashboard: 지난 24h 내 `charge.failed` 이벤트 확인
- [ ] DB 커넥션 수: `pg_stat_activity` count < 5 확인
- [ ] 신규 유저 문의 확인 (`seanbae1521@gmail.com`)

### 주간 (매주 월요일)

- [ ] GitHub Actions 분 사용량 확인 (무료 한도 2,000분 대비)
- [ ] Sentry events 사용량 (5,000/월 대비)
- [ ] Railway 비용 확인 (HOBBY plan 한도)
- [ ] P2 이슈 회고 및 우선순위 재평가

---

## 에스컬레이션 트리거

| 등급 | 조건 | 즉각 액션 |
|------|------|----------|
| P0 | 결제 관련 오류 / PIPA 유출 의심 / 전면 다운 | CEO 즉시 대응, 해당 기능 차단 우선 |
| P0 | §101 위반 의심 artifact 존재 | 해당 artifact 즉시 비공개 |
| P1 | 특정 기능 500 에러 / 성능 p95 > 5s | 24h 내 패치 배포 |
| P1 | 유저 문의 미응답 24h 초과 | 즉시 회신 |
| P2 | UI 오탈자 / 색상 불일치 | 주간 회고에서 일괄 처리 |

---

## 참조 문서

| 문서 | 경로 |
|------|------|
| 일반 운영 Runbook | `docs/OPERATIONS_RUNBOOK.md` |
| 배포 메커니즘 | `HANDOVER.md` (Railway `railway up` 절차) |
| Stripe 연동 | `services/billing/` |
| 법규 필터 | `services/legal/filter.py`, `engine.py` |
| PG pool 설정 | `config.py` (pool_size=3, max_overflow=2) |
| self-heal 가드 | `_do_migrations()` in app.py / db.py |
| PIPA 신고 | https://privacy.go.kr (합리적 추정 — CEO가 실측 확인 필요) |
| Railway status | https://status.railway.app |
| Vercel status | https://www.vercel-status.com |

---

*최종 갱신: 2026-05-28 | 다음 검토: D+7 또는 첫 인시던트 발생 시*
