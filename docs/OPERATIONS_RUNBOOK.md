# PivoxQuant 운영 Runbook

> **목적**: 새벽 3시 장애 콜을 받아도 이 문서만으로 대응 가능.
> **작성**: 2026-04-17 / **버전**: 1.0
> **대상 인프라**: Railway(Flask+PostgreSQL) + Vercel(Next.js 16) + 도메인 pivoxquant.com

---

## 📋 목차

1. [배포 절차](#1-배포-절차)
2. [환경 변수 목록](#2-환경-변수-목록)
3. [모니터링](#3-모니터링)
4. [장애 대응 — 10대 시나리오](#4-장애-대응--10대-시나리오)
5. [백업 및 복원](#5-백업-및-복원)
6. [스케일 한계](#6-스케일-한계)
7. [비용 모니터링](#7-비용-모니터링)
8. [보안 이슈 대응](#8-보안-이슈-대응)
9. [일상 운영 체크리스트](#9-일상-운영-체크리스트)
10. [긴급 연락처 및 자원](#10-긴급-연락처-및-자원)

---

## 1. 배포 절차

### 1-1. 일반 배포 플로우 (자동)

PivoxQuant는 **GitOps 모델**로 운영된다. `main` 브랜치에 push하면 Railway(백엔드)와 Vercel(프론트) 양쪽이 **자동 감지**하여 배포한다.

```bash
# 로컬에서 변경사항 커밋 후
cd /Users/seanbae/Desktop/취준/pivoxquant
git add -A
git commit -m "feat: <변경 내용>"
git push origin main
# → Railway 자동 빌드 (약 3~5분)
# → Vercel 자동 빌드 (약 2~3분)
```

**Railway 빌드 과정** (`railway.json` 정의):
1. Nixpacks가 `requirements.txt` 기반 Python 3.11 이미지 빌드
2. `flask db upgrade || echo migration-skipped` — Alembic 마이그레이션 실행 (실패해도 non-fatal)
3. `gunicorn app:app --worker-class gevent --workers 1 --bind 0.0.0.0:$PORT --timeout 120 --keep-alive 5`
4. Healthcheck: `GET /api/auth/me` (120초 타임아웃)
5. 실패 시 최대 3회 재시도 (`restartPolicyType: ON_FAILURE`)

**Vercel 빌드 과정**:
1. `frontend/` 루트에서 `npm ci && npm run build`
2. Next.js 16 App Router 기준 정적 자산 + SSR 함수 배포
3. Production 도메인: `pivoxquant.com`, Preview: `pivoxquant-<branch>.vercel.app`

### 1-2. 배포 실패 시 진단

**Railway 실패**:
- Railway Dashboard → Project → Deployments → 실패 배포 클릭 → "View Logs"
- 자주 보이는 원인:
  - `ModuleNotFoundError` → `requirements.txt` 패키지 누락
  - `Alembic migration error` → `migrations/versions/` 충돌 (로컬에서 `flask db merge` 필요)
  - `Out of memory` → 빌드 중 메모리 초과 (대형 패키지 제거)

**Vercel 실패**:
- Vercel Dashboard → Deployments → Failed deployment → Build Logs
- 자주 보이는 원인:
  - TypeScript 오류 (strict mode) → 로컬에서 `npm run build` 재현
  - 환경 변수 누락 → `NEXT_PUBLIC_API_URL` 확인
  - `Module not found` → `package.json` + `package-lock.json` 동기화 확인

### 1-3. 수동 재배포

```bash
# Railway: 대시보드에서
# Deployments → 최신 배포 우측 "..." → "Redeploy"

# Vercel: 대시보드에서
# Deployments → 최신 배포 우측 "..." → "Redeploy"

# 또는 빈 커밋으로 트리거
git commit --allow-empty -m "chore: trigger redeploy"
git push origin main
```

### 1-4. 롤백 (5분 이내 복구)

**Vercel (즉시, DNS propagation 없음)**:
1. Vercel Dashboard → Deployments
2. 직전 성공 배포(green)의 "..." → **"Promote to Production"**
3. 즉시 적용 (< 30초)

**Railway (Redeploy)**:
1. Railway Dashboard → Deployments
2. 직전 성공 배포의 "..." → **"Redeploy"**
3. 약 2~3분 후 적용

**Git Revert (근본 롤백)**:
```bash
git log --oneline -5
git revert <bad-commit-sha>
git push origin main
# → 자동 재배포 트리거
```

---

## 2. 환경 변수 목록

### 2-1. 필수 (없으면 부팅 실패)

| 변수 | 위치 | 발급처 | 예시 | 주의사항 |
|------|------|--------|------|----------|
| `SECRET_KEY` | Railway | `python -c "import secrets; print(secrets.token_hex(32))"` | `a3f9...(64자 hex)` | **변경 시 모든 세션 무효화**. 한번 설정하면 절대 바꾸지 말 것 |
| `CSRF_SECRET` | Railway | 위 명령어로 재생성 | `b1c2...(64자 hex)` | SECRET_KEY와 **다른 값** 사용 |
| `DATABASE_URL` | Railway | Railway PostgreSQL 자동 주입 | `postgresql://user:pass@host:5432/railway` | **절대 수동 편집 금지**. Railway가 자동 관리. `sslmode=require` 강제 |
| `FLASK_ENV` | Railway | 수동 | `production` | `development`로 두면 debug toolbar 노출 — 보안 위반 |

### 2-2. 인증 (OAuth)

| 변수 | 발급처 | 형식 | 주의사항 |
|------|--------|------|----------|
| `GOOGLE_CLIENT_ID` | https://console.cloud.google.com/apis/credentials | `xxxx.apps.googleusercontent.com` | Authorized redirect URI: `${RAILWAY_BACKEND_URL}/api/auth/google/callback` 등록 필수 |
| `GOOGLE_CLIENT_SECRET` | 위와 동일 | `GOCSPX-...` | 유출 시 즉시 로테이션 |
| `KAKAO_CLIENT_ID` | https://developers.kakao.com | 10자리 숫자 | REST API 키 사용 (Native가 아님) |
| `KAKAO_CLIENT_SECRET` | 위와 동일 | 32자 hex | 카카오 콘솔에서 "보안 → Client Secret 사용" 활성화 필요 |

### 2-3. 외부 API

| 변수 | 발급처 | 플랜 | 주의사항 |
|------|--------|------|----------|
| `KIS_APP_KEY` | https://apiportal.koreainvestment.com | 무료 (계좌 필수) | 실전/모의 구분. 현재 read-only 모드 |
| `KIS_APP_SECRET` | 위와 동일 | 무료 | 24시간 token TTL — `kis_token_manager.py`가 자동 갱신 |
| `ALPACA_API_KEY` | https://alpaca.markets | Paper 무료 / Live 무료 | 현재 `paper=True` 고정 |
| `ALPACA_SECRET_KEY` | 위와 동일 | 무료 | |
| `FMP_API_KEY` | https://site.financialmodelingprep.com | **Starter $29/월 (유료 구독중)** | 월 한도 초과 시 402 에러 — 캐시로 완화 |
| `ANTHROPIC_API_KEY` | https://console.anthropic.com | 종량제 | 월 $50 한도 예상. 초과 시 alert 설정 권장 |
| `SENTRY_DSN` | https://sentry.io | 5K errors/월 무료 | 선택사항 (미설정 시 로깅만) |
| `SENDGRID_API_KEY` | https://sendgrid.com | 100 emails/day 무료 | 알림 이메일 발송 |

### 2-4. 결제 (Stripe — 미연결 상태, 유료 전환 시 설정)

| 변수 | 발급처 | 주의사항 |
|------|--------|----------|
| `STRIPE_SECRET_KEY` | https://dashboard.stripe.com/apikeys | `sk_live_...` (운영) / `sk_test_...` (테스트). **절대 커밋 금지** |
| `STRIPE_WEBHOOK_SECRET` | Stripe Dashboard → Webhooks | `whsec_...`. 각 webhook endpoint마다 별도 |
| `STRIPE_PRICE_ID_PRO` | Stripe Dashboard → Products | ₩9,900/월 상품 ID |
| `STRIPE_PRICE_ID_PREMIUM` | 위와 동일 | ₩19,900/월 상품 ID |

### 2-5. 기능 플래그 (Feature Flags)

| 변수 | 값 | 의미 |
|------|-----|------|
| `RUN_SCHEDULER` | `1` | APScheduler 백그라운드 작업 활성화 (production에서만 `1`) |
| `KIS_USE_REAL` | `0` or `1` | 한국 실전 계좌 사용 여부 (**현재 0 고정**) |
| `BETA_PASSWORD` | `***REDACTED — Railway env에서만 보유***` | 베타 게이트 비밀번호. 오픈 런칭 시 제거 |
| `DEV_LOGIN_SECRET` | `***REDACTED — Railway env에서만 보유***` | QA 전용 바이패스. **QA 종료 후 즉시 삭제** |
| `CORS_ORIGINS` | `https://pivoxquant.com,https://www.pivoxquant.com,https://pivoxquant.vercel.app` | 쉼표 구분. 후행 슬래시 없이 |
| `FRONTEND_URL` | `https://pivoxquant.com` | OAuth 콜백 후 리다이렉트 대상 |

### 2-6. 프론트엔드 (Vercel)

| 변수 | 값 | 주의사항 |
|------|-----|----------|
| `NEXT_PUBLIC_API_URL` | `<RAILWAY_BACKEND_URL>` (Vercel env로 등록) | **`NEXT_PUBLIC_` 접두사** 때문에 브라우저 노출됨. 비밀값 금지 |
| `BETA_PASSWORD` | `***REDACTED — Vercel env에서만 보유***` | middleware.ts 베타 게이트용 |
| `BETA_SIGNING_SECRET` | `4c492c93...(64자 hex)` | 베타 쿠키 서명. 변경 시 모든 베타 유저 재로그인 |

### 2-7. 변경 시 공통 주의사항

1. **Railway/Vercel 환경변수 변경 → 자동 재배포 트리거됨** (약 3~5분 다운타임 가능)
2. **비밀값은 절대 Git/로그/Slack/스크린샷에 노출 금지**
3. **유출 확인 시 즉시 로테이션**:
   - Google OAuth: Cloud Console에서 "Reset client secret"
   - Stripe: Dashboard → API keys → "Roll key"
   - Anthropic: Console → API keys → "Delete & create new"
4. **`.env.example`만 커밋**, `.env`는 `.gitignore`에 필수 포함

---

## 3. 모니터링

### 3-1. Railway 메트릭스

**접근**: Railway Dashboard → Project → Service → Metrics 탭

| 지표 | 정상 범위 | 경고 임계값 |
|------|-----------|-------------|
| CPU | < 40% | > 70% 지속 5분 |
| Memory | < 500MB | > 800MB (Hobby 플랜 1GB 한도) |
| Network Egress | < 50GB/월 | > 80GB/월 |
| Response Time (p95) | < 500ms | > 2000ms |
| Restart Count | 0/일 | ≥ 3/일 |

### 3-2. Vercel Analytics

**접근**: Vercel Dashboard → Project → Analytics (Hobby 플랜은 제한적)

| 지표 | 확인 방법 |
|------|-----------|
| Page load time | Web Vitals 탭 (LCP, FID, CLS) |
| Bandwidth 사용량 | Usage 탭 (100GB/월 Hobby 한도) |
| Function Invocations | 100K/월 Hobby 한도 |
| Build minutes | 6000분/월 Hobby 한도 |

### 3-3. 에러 로그 확인

**Railway Logs**:
```bash
# Railway CLI 설치 후
railway logs --service <RAILWAY_SERVICE_NAME>
# 또는 대시보드에서 Service → Logs 탭 (실시간 스트림)
```

**Vercel Logs**:
```bash
vercel logs https://pivoxquant.com --follow
# 또는 대시보드 Deployments → 최신 → Functions 탭
```

**주요 에러 패턴 검색**:
- `500 Internal Server Error` → 백엔드 예외
- `CORS` → 도메인 허용 설정 문제
- `ECONNREFUSED` → 외부 API 장애
- `sqlalchemy.exc.OperationalError` → DB 연결 끊김

### 3-4. Claude API 사용량

**접근**: https://console.anthropic.com → Usage
- **일일 확인**: 현재 월 누적 $
- **알림 설정**: Settings → Usage limits → Soft limit $30, Hard limit $80
- 비정상 급증 시: `ai_service.py`의 cache hit rate 확인

### 3-5. Stripe 결제 모니터링 (유료 전환 후)

**접근**: https://dashboard.stripe.com
- Payments 탭: 실패/성공 현황
- Webhooks 탭: delivery 실패 체크 (실패 3회 이상이면 endpoint 문제)
- Radar: 사기성 결제 자동 차단 설정

### 3-6. 외부 API 헬스체크

매일 오전 확인:
```bash
# FMP
curl "https://financialmodelingprep.com/stable/quote?symbol=AAPL&apikey=$FMP_API_KEY"
# Alpaca
curl -H "APCA-API-KEY-ID: $ALPACA_API_KEY" -H "APCA-API-SECRET-KEY: $ALPACA_SECRET_KEY" https://paper-api.alpaca.markets/v2/account
# KIS (토큰 유효성)
curl "${RAILWAY_BACKEND_URL}/api/market/fx"
```

---

## 4. 장애 대응 — 10대 시나리오

### 시나리오 1: 사이트 500 에러 (전체 다운)

**증상**: `pivoxquant.com` 접속 시 500 또는 502.

**진단 순서**:
1. Vercel Dashboard → 최신 배포 상태 green인지
2. Railway Dashboard → 서비스 상태 "Active"인지
3. `curl ${RAILWAY_BACKEND_URL}/api/auth/me` — 200/401 응답인지
4. Railway Logs에서 `Exception` / `Traceback` 검색

**해결 순서**:
1. **Railway가 죽었다면**: Dashboard → Deployments → Redeploy 이전 성공본
2. **Vercel이 죽었다면**: Promote 직전 성공 배포
3. **DB 연결 문제면**: Railway PostgreSQL 서비스 재시작 (Database → Settings → Restart)
4. **원인 불명**: 최근 커밋 `git revert` 후 push

**예방**: PR 단위로 Preview 배포 검증 후 merge. Railway healthcheck 120초 timeout 유지.

---

### 시나리오 2: 로그인 안 됨 (OAuth 리다이렉트 실패)

**증상**: Google/Kakao 로그인 버튼 클릭 → `redirect_uri_mismatch` 또는 빈 페이지.

**진단 순서**:
1. 브라우저 DevTools → Network → OAuth 요청 response 확인
2. Railway 환경변수 `GOOGLE_CLIENT_ID` / `KAKAO_CLIENT_ID` 존재?
3. Google Cloud Console → Credentials → Authorized redirect URIs에 `${RAILWAY_BACKEND_URL}/api/auth/google/callback` 있는지
4. Kakao Developers → 내 애플리케이션 → 카카오 로그인 → Redirect URI 확인

**해결 순서**:
1. Authorized URI 누락이면 Console에서 추가 (전파 약 5분)
2. CLIENT_SECRET이 만료/회수되었으면 재발급 후 Railway 환경변수 갱신
3. `CORS_ORIGINS`에 `pivoxquant.com` 포함되어 있는지 확인

**예방**: 도메인 변경 시 OAuth provider 양쪽 모두 업데이트 체크리스트 운영.

---

### 시나리오 3: 포트폴리오 저장 안 됨 (DB 에러)

**증상**: "Add Position" 버튼 클릭 → 토스트 뜨지만 목록 갱신 안 됨, 새로고침해야 보임.

**진단 순서**:
1. DevTools Network → `POST /api/portfolio/position` 상태 코드
2. Railway Logs에서 `sqlalchemy.exc` 검색
3. `SELECT COUNT(*) FROM positions;` (Railway DB shell)

**해결 순서**:
1. **200인데 UI 미갱신**: 프론트 `mutate()` 누락 (HANDOVER.md B3 버그) — `portfolio/page.tsx:1478` 확인
2. **500 에러**: DB 스키마 불일치 — `flask db upgrade` 수동 실행
3. **Cold start**: Railway Hobby 플랜은 15분 idle 시 sleep — Pro 전환 고려

**예방**: `portfolio.py`의 background thread + `mutate()` 후 100ms revalidate.

---

### 시나리오 4: 실시간 가격 0.00 표시

**증상**: `/detail/AAPL` 가격 $0.00, `/detail/005930` ₩0.

**진단 순서**:
1. Network → `/api/realtime/quote/AAPL` 응답 확인
2. Railway Logs → FMP/Alpaca 응답 에러
3. FMP 쿼터: `curl "https://financialmodelingprep.com/stable/quote?symbol=AAPL&apikey=$FMP_API_KEY"` → `{"Error Message": "Limit Reach"}`인지

**해결 순서**:
1. **FMP 402 (한도 초과)**: Starter → Premium 플랜 업그레이드 또는 TTL cache 확대
2. **한국 종목 0원**: `detail/[ticker]/page.tsx:175-180` `.KS` 자동 접미 로직 확인
3. **Alpaca down**: `data_fetcher.py` FMP fallback 경로 확인

**예방**: `fmp_service.py` budget enforcement + 10분 TTL cache. Quote 이중 소스(Alpaca → FMP).

---

### 시나리오 5: 한국 종목 검색 안 됨

**증상**: "삼성전자" / "005930" 검색 → 빈 결과.

**진단 순서**:
1. `/api/market/search?q=삼성` 응답
2. KIS token 만료 여부 (`kis_token_manager.py` 로그)
3. `KIS_APP_KEY` 환경변수 존재

**해결 순서**:
1. KIS token 만료: `kis_token_manager.py`가 자동 재발급 — Railway 재시작으로 강제
2. 종목 DB 누락: `scripts/seed_kr_stocks.py` 실행
3. FMP KR 종목 지원 안 됨 → KIS 단일 소스 확인

**예방**: KIS token 23시간마다 선제 갱신 스케줄러.

---

### 시나리오 6: Claude AI 응답 없음

**증상**: AI Chat에서 질문 입력 → 무한 로딩.

**진단 순서**:
1. Network → `/api/ai/chat` SSE 스트림 확인
2. Anthropic Console → Usage → 한도 초과?
3. Railway Logs → `anthropic.APIError`

**해결 순서**:
1. **API 한도 초과**: Console에서 credit 추가 또는 한도 인상
2. **API 키 invalid**: `ANTHROPIC_API_KEY` 재발급 후 Railway 갱신
3. **Timeout**: gunicorn `--timeout 120` 유지. 긴 스트림 120초 초과 시 chunk 전송 확인

**예방**: Sonnet 4.5 모델 고정, 프롬프트 캐싱 활용, rate limit retry 로직.

---

### 시나리오 7: Stripe 결제 실패

**증상**: 결제 버튼 클릭 → Stripe checkout 열리지만 결제 후 "실패" 토스트.

**진단 순서**:
1. Stripe Dashboard → Payments → 실패 건 상세
2. Webhooks 탭 → `checkout.session.completed` delivery 상태
3. Railway Logs → `stripe.error` 검색

**해결 순서**:
1. **Webhook secret 불일치**: Stripe Dashboard에서 secret 재발급 → Railway `STRIPE_WEBHOOK_SECRET` 갱신
2. **Price ID 오류**: `STRIPE_PRICE_ID_PRO/PREMIUM` 환경변수와 대시보드 Product ID 일치 확인
3. **테스트 모드 혼용**: `sk_test_` vs `sk_live_` 확인

**예방**: Stripe CLI로 webhook 로컬 테스트 (`stripe listen`). Test mode 먼저 검증 후 Live 전환.

---

### 시나리오 8: Railway 배포 실패

**증상**: Git push 후 Railway Deployments 탭에서 빨간색 "Failed".

**진단 순서**:
1. 실패 배포 클릭 → Build Logs / Deploy Logs
2. 자주 보이는 패턴:
   - `ERROR: Could not find a version that satisfies the requirement`
   - `alembic.util.exc.CommandError: Can't locate revision`
   - `gunicorn: command not found`

**해결 순서**:
1. **pip 패키지 누락**: `requirements.txt`에 추가 후 커밋
2. **Alembic 충돌**: 로컬 `flask db merge heads` 후 푸시
3. **gunicorn 누락**: `requirements.txt`에 `gunicorn==21.2.0`, `gevent==24.2.1` 확인
4. **Out of memory**: Hobby → Pro 플랜 고려

**예방**: 로컬 `docker build .` 로 Dockerfile 사전 검증.

---

### 시나리오 9: Vercel 프론트 404

**증상**: `pivoxquant.com/portfolio` 접속 시 Vercel 404 페이지.

**진단 순서**:
1. Vercel Dashboard → Deployments → 최신 Production 배포 상태
2. Build Logs에서 해당 라우트 경로 빌드 확인
3. `frontend/src/app/(dashboard)/portfolio/page.tsx` 존재 확인

**해결 순서**:
1. **Next.js route group `(dashboard)`**: 괄호 포함 디렉토리명 주의 — Git에서 실제 커밋됐는지 확인
2. **Root Directory 설정**: Vercel Project Settings → Root Directory = `frontend`
3. **DNS 캐시**: `dig pivoxquant.com` → Vercel IP 확인. Cloudflare 프록시 있으면 purge

**예방**: Preview 배포에서 모든 페이지 smoke test.

---

### 시나리오 10: 데이터베이스 연결 끊김

**증상**: 간헐적 500 에러, Railway Logs에 `sqlalchemy.exc.OperationalError: server closed the connection`.

**진단 순서**:
1. Railway Dashboard → PostgreSQL 서비스 → Metrics (CPU/Connections)
2. `SELECT count(*) FROM pg_stat_activity;` — 활성 연결 수
3. `DATABASE_URL` 환경변수 변경 여부

**해결 순서**:
1. **Connection pool 고갈**: `config.py`의 `pool_size=5, max_overflow=10, pool_pre_ping=True` 확인
2. **PostgreSQL 재시작 필요**: Railway → Database → Settings → Restart Database
3. **SSL 문제**: `DATABASE_URL` 끝에 `?sslmode=require` 확인

**예방**: `pool_pre_ping=True`로 dead connection 자동 감지. PgBouncer 도입 검토 (유저 증가 시).

---

## 5. 백업 및 복원

### 5-1. Railway PostgreSQL 자동 백업

**확인**: Railway Dashboard → Database → **Backups** 탭
- **Hobby 플랜**: 일일 자동 백업 (7일 보관)
- **Pro 플랜**: 시간별 백업 (30일 보관)

**즉시 활성화 권장 사항**:
1. Backups 탭 → "Enable daily backups" 토글 ON
2. 매주 월요일 백업 복원 테스트 (스테이징 DB 환경에서)

### 5-2. 수동 dump (로컬 백업)

```bash
# DATABASE_URL을 Railway 대시보드에서 복사 (Connect → External Connection URL)
export DB_URL="postgresql://postgres:xxx@monorail.proxy.rlwy.net:5432/railway"

# 전체 덤프
pg_dump $DB_URL > pivoxquant_$(date +%Y%m%d_%H%M%S).sql

# 압축
pg_dump $DB_URL | gzip > pivoxquant_$(date +%Y%m%d).sql.gz

# 스키마만
pg_dump --schema-only $DB_URL > schema.sql

# 데이터만
pg_dump --data-only $DB_URL > data.sql
```

**저장 위치 권장**:
- 로컬 `~/backups/pivoxquant/`
- iCloud Drive 또는 Google Drive 동기화
- 월 1회 외장 SSD 복사

### 5-3. 복원 절차

```bash
# 새 Railway DB 생성 후 DATABASE_URL 획득
export NEW_DB_URL="postgresql://postgres:yyy@..."

# 복원
psql $NEW_DB_URL < pivoxquant_20260417_030000.sql
# 또는 압축 파일
gunzip -c pivoxquant_20260417.sql.gz | psql $NEW_DB_URL

# Railway 환경변수 DATABASE_URL 갱신 → 자동 재배포
```

**재난 복구 시간 목표 (RTO)**: 30분 이내. **데이터 손실 목표 (RPO)**: 24시간 이내.

---

## 6. 스케일 한계

### 6-1. 현재 용량 추정 (Railway Hobby + Vercel Hobby)

| 리소스 | 한도 | 예상 동시 유저 |
|--------|------|----------------|
| Railway 1GB RAM / 1 vCPU (gunicorn workers=1) | 동시 연결 ~100 | DAU 500명 |
| PostgreSQL Hobby (1GB storage) | 100K rows | 유저 1000명 × 포지션 평균 10개 |
| Vercel 100GB bandwidth/월 | 페이지뷰 ~500K/월 | DAU 2000명 |
| FMP Starter (300 calls/분) | 가격 조회 캐시 있음 | DAU 500~1000명 |
| Claude API ($50/월 예산) | 채팅 1500~3000회/월 | DAU 100~200명 (활성 채팅) |

**결론**: 현재 설정은 **DAU 500명 / 전체 유저 2000명**까지 무리 없음.

### 6-2. 병목 지점

1. **gunicorn workers=1 + gevent**: SSE 장기 연결 때문에 workers 증설 시 메모리 폭발. workers=1 유지하며 greenlet 수천 개 처리.
2. **FMP Starter 300 calls/분**: 유저 폭증 시 즉시 한도 도달. Premium $79/월 전환 지점 = DAU 1000명.
3. **Claude API 비용**: 유저당 월 $0.30~0.50 예상. DAU 1000명 = 월 $300~500.
4. **PostgreSQL 1GB**: positions + signals + chat 로그 합산 기준 유저 5000명 경계.

### 6-3. Scale-up 트리거 및 조치

| 트리거 | 조치 | 예상 비용 증가 |
|--------|------|----------------|
| Railway CPU > 70% (5분) | Hobby → Pro ($20/월) | +$15 |
| DB storage > 800MB | PostgreSQL Pro | +$10 |
| Vercel bandwidth > 80GB | Hobby → Pro ($20/월) | +$20 |
| FMP 402 에러 반복 | Starter → Premium | +$50 |
| Claude 사용량 > $100/월 | 프롬프트 캐싱 확대 + 응답 길이 제한 | $0 (최적화) |
| DAU > 1000 | gunicorn workers=2 + Redis 세션 | +$5 (Redis) |

---

## 7. 비용 모니터링

### 7-1. 월간 고정 비용 (2026-04 기준)

| 서비스 | 플랜 | 월 비용 (KRW) | 비고 |
|--------|------|----------------|------|
| Railway | Hobby $5 credit | 7,000원 | Flask + PostgreSQL 통합 |
| Vercel | Hobby | 0원 | 100GB bandwidth 무료 |
| FMP | Starter $29 | 40,000원 | 유료 구독중 |
| 도메인 pivoxquant.com | 가비아 | 1,650원 | 연 19,800원 / 12 |
| Anthropic Claude | 종량제 | ~50,000원 (변동) | 유저수 따라 |
| Sentry | Developer 무료 | 0원 | 5K errors |
| SendGrid | Essentials 무료 | 0원 | 100 emails/day |
| **합계** | | **약 98,650원/월** | |

### 7-2. 유저 증가에 따른 비용 추이

| DAU | 예상 월비용 | 주요 증가 요인 |
|-----|-------------|----------------|
| 10 (친구 베타) | 100,000원 | 현재 |
| 100 | 150,000원 | Claude API 증가 |
| 500 | 300,000원 | Claude + Railway Pro |
| 1000 | 600,000원 | FMP Premium + Vercel Pro |
| 5000 | 2,000,000원 | 모든 플랜 업그레이드 |

### 7-3. 비용 알림 설정

1. **Anthropic**: Console → Usage limits → Email alert at $30, $50, $80
2. **Railway**: Dashboard → Usage → Set monthly budget $20 → Email alert at 80%
3. **Vercel**: Settings → Billing → Spend limit $25
4. **Stripe** (수익): Dashboard → Billing → Monthly statement

### 7-4. 예산 초과 시 긴급 조치

1. `RUN_SCHEDULER=0` 설정 → 백그라운드 작업 중단
2. Claude 모델 Sonnet → Haiku 스위치 (비용 1/5)
3. FMP TTL cache 10분 → 60분 확대
4. SSE 스트리밍 비활성화 (polling 전환)

---

## 8. 보안 이슈 대응

### 8-1. SECRET 노출 시 (API 키/토큰 커밋됨)

**즉시 (< 15분)**:
1. **Git 히스토리 확인**: `git log --all -p | grep -i "api_key\|secret"`
2. **모든 관련 키 로테이션**:
   - Anthropic Console → 기존 키 Delete → 신규 발급
   - Google Cloud → OAuth Client Secret Reset
   - Stripe → Dashboard → Roll API key
   - FMP → Dashboard → Regenerate API key
   - Railway/Vercel 환경변수 즉시 갱신
3. **Git 히스토리 정리**: `git filter-repo --path .env --invert-paths` (신중히)
4. **Force push** (팀원 있으면 합의 필수): `git push origin main --force`

**사후 (24시간 내)**:
- Anthropic/Stripe 사용 로그 확인 — 비정상 호출 있는지
- 비용 이상 급증 확인

### 8-2. 유저 데이터 유출 시

**법적 의무 (GDPR + PIPA)**:
- **GDPR 대상 유저**: 72시간 이내 감독기관(EU) 및 영향받은 유저에게 통지 의무
- **PIPA (한국 개인정보보호법)**: 72시간 이내 개인정보보호위원회 신고 (유출 1천명 이상) + 즉시 유저 통지
- **신고 채널**: https://privacy.go.kr (개인정보침해 신고센터 국번없이 182)

**기술적 조치**:
1. **즉시 유출 경로 차단** (API endpoint disable, 세션 전부 무효화)
2. `SECRET_KEY` 로테이션 → 모든 세션 강제 로그아웃
3. 유저 비밀번호 reset (OAuth-only라서 해당 없음, 향후 email 가입 시 대비)
4. 포렌식: Railway Logs 30일치 다운로드 보관

**커뮤니케이션**:
- 이메일 공지 템플릿 사전 준비 (법무 자문 받은 문안)
- 홈페이지 공지 배너

### 8-3. DDoS 공격 시

**증상**: 비정상적 트래픽 급증, Railway CPU/bandwidth 폭증, 사이트 느려짐.

**조치**:
1. **Vercel DDoS 보호**: 자동 활성화됨 (Anycast + rate limiting)
2. **Cloudflare 프록시 앞단 배치** 고려 (무료 플랜으로 시작):
   - DNS를 Cloudflare로 이전 → Cloudflare에서 Vercel/Railway 프록시
   - "Under Attack Mode" 활성화 (5분 JS 챌린지)
3. **Railway rate limit 강화**: `security.py`의 `Flask-Limiter` 임계값 축소
4. **IP 차단**: Cloudflare Firewall Rules로 악성 IP 대역 차단

### 8-4. 권장 보안 업데이트 주기

| 항목 | 주기 |
|------|------|
| `pip-audit` / `npm audit` | 매주 월요일 |
| Dependabot alerts | 실시간 (GitHub 자동) |
| SECRET 로테이션 (정기) | 분기 1회 (강제 사고 없이도) |
| `apt-get upgrade` (Dockerfile base image) | 월 1회 `python:3.11-slim` 최신 태그 재빌드 |
| 보안 헤더 점검 (https://securityheaders.com) | 월 1회 |
| SSL/TLS 등급 (https://ssllabs.com) | 분기 1회, A 등급 유지 |

---

## 9. 일상 운영 체크리스트

### 매일 (09:00 KST, 5분)

- [ ] Railway Dashboard → 서비스 Active, 에러 로그 0건
- [ ] Vercel Dashboard → 최신 배포 green
- [ ] `curl https://pivoxquant.com` → 200 응답
- [ ] Sentry (활성 시) → 신규 에러 0건
- [ ] Claude API 일일 사용량 < $3

### 매주 (월요일 10:00, 30분)

- [ ] Railway + Vercel 비용 누적 확인 (월 예산 대비 %)
- [ ] 유저 수 집계 (회원가입, DAU, 이탈률)
- [ ] 고객 피드백 (이메일, DM) 리뷰
- [ ] `pip-audit` / `npm audit` 실행 → 취약점 패치
- [ ] DB 백업 파일 존재 확인 (Railway Backups 탭)

### 매월 (1일 14:00, 2시간)

- [ ] Dockerfile base image 재빌드 + 배포 (보안 패치)
- [ ] SECRET 정기 로테이션 여부 판단
- [ ] 백업 복원 테스트 (스테이징 DB로)
- [ ] 외부 API 키 만료일 확인 (KIS 연 1회, 나머지 무기한)
- [ ] 비용 분석 리포트 작성 (finance_budget.md 업데이트)
- [ ] 법적 문서 업데이트 검토 (terms, privacy)

---

## 10. 긴급 연락처 및 자원

### 10-1. 플랫폼 지원

| 서비스 | 지원 채널 | SLA |
|--------|-----------|-----|
| Railway | https://railway.com/help, Discord https://discord.gg/railway | Hobby 무보장, Pro 24시간 |
| Vercel | https://vercel.com/help, support@vercel.com | Hobby 커뮤니티, Pro 24시간 |
| Anthropic | https://support.anthropic.com | 영업일 24시간 |
| Stripe | https://support.stripe.com, 24/7 채팅 | 긴급건 1시간 이내 |
| 가비아 (도메인) | 1544-4370, 평일 09~18 | 4시간 이내 |
| FMP | support@financialmodelingprep.com | 영업일 48시간 |
| KIS | 1544-5000 (한국투자증권) | 영업시간 |

### 10-2. 커뮤니티 / 이슈 트래커

- **GitHub Issues**: https://github.com/seanbae-analyst/pivoxquant/issues
- **Railway Discord**: 빠른 커뮤니티 답변 (#general, #help)
- **Next.js Discord**: https://nextjs.org/discord
- **Flask Discord**: https://discord.gg/pallets

### 10-3. 법무/규제

- **개인정보보호위원회**: 국번없이 182, https://privacy.go.kr
- **금융감독원 민원**: 1332
- **금융위원회 유사투자자문업**: 02-2100-2500
- **사이버수사대**: 국번없이 112 (해킹/DDoS 대응)

### 10-4. 유용한 링크

- **Railway Status**: https://status.railway.com
- **Vercel Status**: https://www.vercel-status.com
- **Anthropic Status**: https://status.anthropic.com
- **Stripe Status**: https://status.stripe.com
- **FMP Status**: https://status.financialmodelingprep.com
- **Let's Encrypt (SSL)**: https://letsencrypt.org
- **Security Headers 검사**: https://securityheaders.com/?q=pivoxquant.com
- **SSL Labs 검사**: https://ssllabs.com/ssltest/analyze.html?d=pivoxquant.com

### 10-5. 운영자 본인

- **이메일**: seanbae1521@gmail.com
- **휴대폰**: (개인 연락처, 로그에 기록 금지)
- **GitHub**: https://github.com/seanbae-analyst

---

## 📌 부록: 빠른 명령어 치트시트

```bash
# 로컬 재현
cd /Users/seanbae/Desktop/취준/pivoxquant && python3 run.py  # backend
cd /Users/seanbae/Desktop/취준/pivoxquant/frontend && npm run dev  # frontend

# Railway CLI
railway login
railway link
railway logs --service <RAILWAY_SERVICE_NAME>
railway run python3 -c "from app import create_app; app=create_app(); print(app.config['SQLALCHEMY_DATABASE_URI'])"

# Vercel CLI
vercel login
vercel logs https://pivoxquant.com --follow
vercel env ls

# DB 접속
railway connect postgres  # Railway CLI로 psql 접속
# 또는
psql $DATABASE_URL

# 긴급 롤백
git revert HEAD && git push origin main

# 헬스체크
curl ${RAILWAY_BACKEND_URL}/api/auth/me
curl https://pivoxquant.com/api/market/fx
```

---

**문서 버전**: 1.0 (2026-04-17)
**다음 리뷰**: 2026-05-17 (월 1회)
**작성자**: DevOps (PivoxQuant SRE)

> **원칙**: Hope is not a strategy. 자동화되지 않은 것은 언젠가 실패한다.
> 이 Runbook이 오래돼 보이면 즉시 업데이트하라 — Stale docs are worse than no docs.
