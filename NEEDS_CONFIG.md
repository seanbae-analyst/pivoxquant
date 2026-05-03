# PivoxQuant — 출시 전 사용자(CEO) 액션 체크리스트

> 코드로 해결 불가능, **CEO만 가능한** 작업 모음. Master Fix Plan Phase 9.
> 작성일: 2026-05-03 · 마지막 업데이트: (직접 항목 체크하면서 갱신)

---

## 🔴 P0 — 출시 차단 (이거 안 하면 시작 자체가 안 됨)

### 1. 누락 환경 변수 28개 채우기 (B1)

**상황**: 로컬 `.env`는 17개 키만 채워져 있음. `.env.example`은 45개 정의. 차이 28개가 비어있음.
**대응**: 로컬은 `.env`에 직접, prod는 Railway/Vercel 환경 변수에 직접 추가.

#### 카테고리별 (우선순위 순)

**A. 결제 — 가장 시급** (Stripe Live mode 전환 필요. 사업자등록 후)
- [ ] `STRIPE_SECRET_KEY` — Stripe Dashboard → Developers → API keys (Live)
- [ ] `STRIPE_WEBHOOK_SECRET` — Webhook endpoint 생성 후 signing secret
- [ ] `STRIPE_PRICE_PRO` — Pro 티어 Price ID (Stripe Products)
- [ ] `STRIPE_PRICE_PREMIUM` — Premium 티어 Price ID

**B. 보안 시크릿 — 즉시 (50자+ 랜덤)**
- [ ] `CSRF_SECRET` — `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`
- [ ] `PIVOX_BROKER_ENCRYPTION_KEY` — Fernet 키. `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- [ ] `BETA_PASSWORD` — 베타 게이트 비밀번호 (현재 메모리: `***REDACTED***`. 출시 전 rotate)

**C. 인프라 URL**
- [ ] `DATABASE_URL` — Railway PostgreSQL connection string (prod). 로컬은 SQLite 자동
- [ ] `FRONTEND_URL` — `https://pivoxquant.com` (prod) / `http://localhost:3000` (local)
- [ ] `CORS_ORIGINS` — `https://pivoxquant.com,https://www.pivoxquant.com`
- [ ] `SESSION_COOKIE_DOMAIN` — `.pivoxquant.com` (prod only; 비워두면 자동)
- [ ] `RATELIMIT_STORAGE_URI` — Redis URL (Railway Redis addon). 비우면 메모리(재시작 시 리셋)
- [ ] `FLASK_ENV` — `production` (prod) / `development` (local)

**D. 운영 토글**
- [ ] `RUN_SCHEDULER` — `1` (한 인스턴스만; 여러 인스턴스면 cron worker 분리)
- [ ] `POPULATE_CACHE_ON_BOOT` — `0` (false) 권장. 대량 호출 회피
- [ ] `ENABLE_COMMAND_CENTER` — `0` (admin 도구; 운영자만 `1`)

**E. 발신자 이메일** (도메인 등록 + SendGrid sender authentication 후)
- [ ] `WEEKLY_MEMO_FROM_EMAIL` — `reports@pivoxquant.com`
- [ ] `EARNINGS_PREBRIEF_FROM_EMAIL` — `prebrief@pivoxquant.com` 또는 동일 reports@
- [ ] `EARNINGS_PREBRIEF_LEAD_MINUTES` — `30` (기본값)
- [ ] `BRAG_CARD_FROM_EMAIL` — `brag@pivoxquant.com` 또는 동일
- [ ] `BRAG_CARD_SHARE_BASE_URL` — `https://pivoxquant.com/share/brag`
- [ ] `MONTHLY_BRAG_SHARE_DOMAIN` — `pivoxquant.com`

**F. 외부 API (선택)**
- [ ] `ALPHAVANTAGE_API_KEY` — 무료 5/min 충분. https://www.alphavantage.co/support/#api-key
- [ ] `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` — 네이버 OAuth (안 쓸 거면 비워둠)
- [ ] `ADMIN_EMAILS` — 본인 이메일 (`seanbae1521@gmail.com`)

**G. Web Push (출시 후 가능)**
- [ ] `VAPID_PRIVATE_KEY` — `npx web-push generate-vapid-keys`
- [ ] `VAPID_EMAIL` — `mailto:seanbae1521@gmail.com`

### 2. Anthropic API credit 충전 (B2)

- [ ] https://console.anthropic.com → Billing → 최소 **$50** 충전 권장
- 사용처: SWOT 생성, AI Chat, Sector 분석, Coaching, Pre-Brief expected questions

### 3. 도메인 + SendGrid sender authentication (B6 / E6)

- [ ] **가비아 도메인 결제 갱신 확인** — `pivoxquant.com` 1년 갱신 (메모: 19,800원)
- [ ] **Vercel DNS 연결 확인** — A/CNAME 레코드, SSL 자동 발급
- [ ] **SendGrid sender authentication**:
  - SendGrid → Settings → Sender Authentication → Authenticate Your Domain
  - Domain: `pivoxquant.com`
  - DNS records (CNAME 3개) 추가 → 가비아 또는 Vercel DNS
  - **SPF / DKIM / DMARC** 자동 설정됨 — 미인증 시 Gmail 스팸함 직행
- [ ] **DMARC policy** 직접 추가 (가비아 DNS):
  ```
  Type: TXT
  Name: _dmarc
  Value: v=DMARC1; p=quarantine; rua=mailto:seanbae1521@gmail.com
  ```

### 4. OAuth Redirect URI 등록

- [ ] **Google Cloud Console** → APIs & Services → Credentials → OAuth 2.0 Client → Authorized redirect URIs에 추가:
  - `http://localhost:3000/api/auth/google/callback`
  - `https://pivoxquant.com/api/auth/google/callback`
- [ ] **Kakao Developers** → 내 애플리케이션 → 카카오 로그인 → Redirect URI에 동일 2개 등록
- [ ] (선택) Naver Developers — 안 쓸 거면 환경 변수 비워두기

---

## 🟠 P1 — 출시 직전

### 5. Stripe Live mode 전환

- [ ] **사업자등록 완료 후** Stripe → Activate Account
- [ ] Bank account 연결 (정산 계좌)
- [ ] 사업자등록증 + 신분증 제출
- [ ] Test mode → Live mode 전환 후 Webhook signing secret 재발급 → `STRIPE_WEBHOOK_SECRET` 갱신
- [ ] 실제 카드로 ₩100 결제 → 환불 시나리오 1회 테스트

### 6. FMP plan 업그레이드 (유료 사용자 100명 도달 시)

- [ ] FMP Starter $29/mo → Standard $99/mo 검토
- [ ] 현재: Premium $29 (750 req/min, soft daily cap 10k) — `fmp_service.py` budget enforcement 작동 중
- [ ] 업그레이드 시점: 일일 사용량 70%+ 도달 시 (Railway logs로 모니터)

### 7. 변호사 1회 검토

- [ ] `LEGAL_CONSULT_PACKAGE.md` 변호사에게 송부 (₩200~500만원 예산)
- [ ] 핵심 검토 항목:
  - 투자자문업/일임업 회피 검증 (autotrader 비활성 + read-only KIS)
  - 이용약관 / 개인정보처리방침 한국어 버전
  - 면책 고지 문구 (DisclaimerBanner)
  - 결제 약관 (Stripe → 한국 사업자등록 호환성)

### 8. HANDOVER.md 갱신

- [ ] 마지막 업데이트: 2026-04-27
- [ ] 5/3 세션 결과 반영: PR #28 + #35 머지, Phase 1/2/4 진행 상황

---

## 🟡 P2 — 베타 후

### 9. git fsck dangling 정리 (B12 / B15)

- [ ] `git fsck --full` 출력에 dangling commits/blobs/trees 다수
- [ ] 출처 확인: 야간 자율 세션 worktree 잔재 가능성
- [ ] 정리: `git reflog expire --expire=now --all && git gc --prune=now --aggressive`
- [ ] **주의**: 작업 중인 worktree 폐기 후에 실행

### 10. alembic heads 다중 가능성 모니터

- [ ] 현재: `019_ai_twin (head)` 단일 — OK
- [ ] Phase 2 PR 머지 후 `020_email_opt_out`이 추가됨 → `020_email_opt_out (head)`로 단일 유지 확인
- [ ] 분기 발생 시 `alembic merge` 사용

---

## 📋 매핑 — Master Fix Plan 잔여 작업

| 항목 | 상태 | 비고 |
|---|---|---|
| Phase 0 Pre-flight | ✅ | 1469 baseline 확인 |
| PR #28 (Phase 3/5/6/8 대부분) | ✅ MERGED 2026-05-03 | secondary bug sweep 17 commits |
| PR #35 SEC-005 IDOR | ✅ MERGED 2026-05-03 | growth_reflections 격리 |
| Phase 1 Quick Wins (E3+E5+E8) | ✅ PR #36 OPEN | 머지 대기 |
| Phase 2 Email Compliance (E1+E2) | 🔄 IN PROGRESS | backend-dev agent 작업 중 |
| Phase 4 UX Critical 5 | 🔄 IN PROGRESS | frontend-dev agent 작업 중 |
| Phase 7 Email Refactor (E9~E13) | ⏸️ BLOCKED on Phase 2 | EmailSender 추출 |
| Phase 9 (이 문서) | ✅ | 너가 보고 있는 그것 |

리팩토링 PR (#29, #31~#34)은 코드 정리이며 버그 아님 → 별도 결정.

---

## 🚦 Smoke Test 권장 순서 (Phase 1+2+4 머지 후)

1. `pytest -q` — 1469+ baseline 확인
2. 로컬 backend 기동 → `curl localhost:5050/api/health` → 200
3. `cd frontend && npm run typecheck && npm run lint`
4. 브라우저: 로그인 → 온보딩 → 홈 → Portfolio → Watchlist → Search → Risk → Discover
5. Settings → 이메일 수신거부 토글 → off → 다음 cron 실행 시 발송 안 됨 확인
6. 발송된 이메일 footer의 unsubscribe 링크 클릭 → 토큰 검증 → "수신거부 완료" 페이지

---

**Last updated**: 2026-05-03 by Master Fix Plan Phase 9
