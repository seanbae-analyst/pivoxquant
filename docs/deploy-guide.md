# PivoxQuant -- Production Deployment Guide

Last updated: 2026-04-09

---

## Prerequisites

- GitHub 계정 + 코드가 push된 repository
- Railway 계정 (https://railway.com)
- Vercel 계정 (https://vercel.com)
- 환경변수 준비 완료 (docs/env-setup.md 참고)

---

## Step 1: GitHub Repository 준비

```bash
# 프로젝트 루트에서
cd /path/to/stockpilot

# .env가 .gitignore에 포함되어 있는지 확인
grep ".env" .gitignore
# 출력: .env

# 커밋 & 푸시
git add -A
git commit -m "Add deployment configuration"
git push origin main
```

IMPORTANT: `.env` 파일이 절대 커밋되지 않았는지 확인.
```bash
git log --all --diff-filter=A -- .env
# 출력이 있으면 .env가 과거에 커밋된 적 있음 -- 모든 키 로테이션 필수
```

---

## Step 2: Railway Backend 배포

### 2-1. 프로젝트 생성

1. https://railway.com 로그인
2. "New Project" 클릭
3. "Deploy from GitHub Repo" 선택
4. pivoxquant 리포지토리 연결
5. Root Directory 설정: `/` (프로젝트 루트, frontend가 아님)

### 2-2. PostgreSQL 추가

1. Railway 프로젝트 대시보드에서 "New" > "Database" > "PostgreSQL" 추가
2. `DATABASE_URL` 환경변수가 자동으로 주입됨
3. 별도 설정 불필요 -- config.py가 자동 감지

### 2-3. 환경변수 설정

Railway Dashboard > Service > Variables 탭에서 아래 변수를 모두 추가:

```
SECRET_KEY=<python -c "import secrets; print(secrets.token_hex(32))" 로 생성>
CSRF_SECRET=<별도 생성>
FLASK_ENV=production
CORS_ORIGINS=https://<your-vercel-domain>.vercel.app
FRONTEND_URL=https://<your-vercel-domain>.vercel.app
ANTHROPIC_API_KEY=<your-key>
ALPACA_API_KEY=<your-key>
ALPACA_SECRET_KEY=<your-key>
KIS_APP_KEY=<your-key>
KIS_APP_SECRET=<your-key>
GOOGLE_CLIENT_ID=<your-id>
GOOGLE_CLIENT_SECRET=<your-secret>
SENTRY_DSN=<your-dsn>
FMP_API_KEY=<your-key>
SENDGRID_API_KEY=<your-key>
```

### 2-4. 배포 확인

1. Railway가 자동으로 빌드 & 배포 시작
2. Deploy Logs에서 에러 없는지 확인
3. Railway이 부여한 도메인 확인 (예: `pivoxquant-production.up.railway.app`)
4. 브라우저에서 `https://<railway-domain>/api/auth/me` 접속하여 JSON 응답 확인

### 2-5. Custom Domain (선택사항)

1. Settings > Domains > "Custom Domain" 추가
2. DNS에서 CNAME 레코드 설정
3. CORS_ORIGINS, FRONTEND_URL 환경변수도 업데이트

---

## Step 3: Vercel Frontend 배포

### 3-1. 프로젝트 생성

1. https://vercel.com 로그인
2. "Add New Project" > GitHub 리포지토리 연결
3. Root Directory: `frontend` (반드시 frontend 폴더 지정)
4. Framework Preset: Next.js (자동 감지)
5. Build Command: `npm run build` (기본값)
6. Output Directory: `.next` (기본값)

### 3-2. 환경변수 설정

Vercel Dashboard > Project > Settings > Environment Variables:

```
NEXT_PUBLIC_API_URL=https://<railway-domain>.up.railway.app
```

Environment: Production, Preview, Development 모두 체크.
단, Development에는 `http://localhost:5050`을 사용할 수도 있음.

### 3-3. 배포 확인

1. Vercel이 자동으로 빌드 & 배포
2. 부여된 도메인 확인 (예: `pivoxquant.vercel.app`)
3. 브라우저에서 접속하여 로그인 페이지 확인

---

## Step 4: Cross-Service 연결 확인

### 4-1. Railway 환경변수 업데이트

Vercel 도메인이 확정되면 Railway 환경변수를 업데이트:

```
CORS_ORIGINS=https://pivoxquant.vercel.app
FRONTEND_URL=https://pivoxquant.vercel.app
```

여러 도메인 허용 시 쉼표 구분:
```
CORS_ORIGINS=https://pivoxquant.vercel.app,https://custom-domain.com
```

### 4-2. Google OAuth 리다이렉트 URI 추가

1. Google Cloud Console > APIs & Services > Credentials
2. OAuth 2.0 Client ID 선택
3. "Authorized redirect URIs"에 추가:
   - `https://<railway-domain>/api/auth/google/callback`
4. "Authorized JavaScript origins"에 추가:
   - `https://<vercel-domain>.vercel.app`

### 4-3. End-to-End 검증 체크리스트

```
[ ] 프론트엔드 로딩 -- Vercel 도메인 접속
[ ] 회원가입 -- /login 페이지에서 이메일 가입
[ ] 로그인 -- 가입한 계정으로 로그인
[ ] Google OAuth -- Google 소셜 로그인
[ ] 포트폴리오 -- 종목 추가 (POST /api/portfolio/position)
[ ] 시그널 -- 종목 분석 결과 로딩
[ ] AI 채팅 -- Claude API 호출 (SSE 스트리밍)
[ ] 실시간 -- 가격 스트리밍 (SSE)
[ ] 세션 유지 -- 새로고침 후 로그인 상태 유지
```

---

## Step 5: Rollback Procedure

### Railway 롤백
1. Railway Dashboard > Deployments 탭
2. 이전 성공 배포의 "..." 메뉴 > "Redeploy" 클릭
3. 또는 Git에서 revert 후 push

### Vercel 롤백
1. Vercel Dashboard > Deployments 탭
2. 이전 성공 배포의 "..." 메뉴 > "Promote to Production" 클릭
3. 즉시 적용 (DNS propagation 불필요)

---

## Troubleshooting

### "CORS blocked" 에러
- Railway의 `CORS_ORIGINS`에 Vercel 도메인이 정확히 설정되었는지 확인
- 프로토콜(`https://`) 포함, 후행 슬래시 없이

### "502 Bad Gateway" on Railway
- Deploy Logs 확인
- `gunicorn` / `gevent`가 requirements.txt에 포함되었는지 확인
- PORT 환경변수가 Railway에서 자동 주입되고 있는지 확인

### "Session expired" 반복
- `SECRET_KEY`가 고정값인지 확인 (배포할 때마다 변경되면 세션 무효화)
- `SESSION_COOKIE_SECURE=True`이므로 HTTPS 필수

### Google OAuth "redirect_uri_mismatch"
- Google Cloud Console에서 Railway 도메인의 콜백 URL이 정확히 등록되었는지 확인
- URL 끝에 슬래시(/) 유무 확인

### SSE 스트리밍 끊김
- gunicorn worker class가 `gevent`인지 확인 (Procfile)
- `--timeout 120` 설정 확인
- Vercel/Cloudflare 프록시의 타임아웃 확인

### DB 마이그레이션 에러
- Railway PostgreSQL이 정상 연결되는지 확인
- app.py의 `_run_migrations()`가 ALTER TABLE IF NOT EXISTS 패턴 사용 중
- 심각한 스키마 변경 시 `scripts/migrate_to_postgres.py` 사용

---

## Architecture (Production)

```
[User Browser]
     |
     v
[Vercel CDN] -- Next.js SSR + Static Assets
     |
     | rewrites /api/* -->
     v
[Railway] -- Flask + Gunicorn (gevent workers)
     |
     v
[Railway PostgreSQL] -- primary database
     |
     +-- [Alpaca API] -- US stock data + trading
     +-- [KIS API] -- KR stock data + trading
     +-- [Claude API] -- AI analysis
     +-- [Sentry] -- error monitoring
     +-- [SendGrid] -- email notifications
     +-- [Stripe] -- billing
```

---

## Cost Estimation (Monthly)

| Service | Free Tier | Paid Tier (if exceeded) |
|---|---|---|
| Railway | $5 credit/month | Usage-based |
| Railway PostgreSQL | Included in $5 credit | Usage-based |
| Vercel | 100GB bandwidth | $20/month Pro |
| Anthropic API | None (pay-per-use) | ~$5-50/month |
| Alpaca | Free (paper + live) | Free |
| Sentry | 5K errors/month | $26/month |
| SendGrid | 100 emails/day | $19.95/month |
