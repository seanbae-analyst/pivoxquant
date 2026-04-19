# PivoxQuant -- Environment Variables

Last updated: 2026-04-09

---

## Railway (Backend) Environment Variables

Railway Dashboard > Project > Variables 에서 설정.

### REQUIRED -- 미설정 시 앱 장애

| Variable | Description | Example |
|---|---|---|
| `SECRET_KEY` | Flask 세션 암호화 키. 고정값 필수. `python -c "import secrets; print(secrets.token_hex(32))"` 로 생성 | `a1b2c3d4...64자hex` |
| `CSRF_SECRET` | CSRF 토큰 서명 키. 고정값 필수. SECRET_KEY와 다른 값 사용 권장 | `e5f6g7h8...64자hex` |
| `DATABASE_URL` | PostgreSQL 연결 URL. Railway Postgres 플러그인 추가 시 자동 생성 | `postgresql://user:pass@host:5432/dbname` |
| `FLASK_ENV` | `production` 고정. Secure 쿠키, HSTS 등 보안 설정 활성화 | `production` |
| `CORS_ORIGINS` | Vercel 프론트엔드 도메인. 쉼표 구분 가능 | `https://pivoxquant.vercel.app` |
| `FRONTEND_URL` | 프론트엔드 URL. OAuth 콜백, 리다이렉트에 사용 | `https://pivoxquant.vercel.app` |
| `ANTHROPIC_API_KEY` | Claude AI API 키 | `YOUR_ANTHROPIC_KEY` |
| `PORT` | Railway가 자동 주입. 수동 설정 불필요 | (자동) |

### REQUIRED -- 기능별 (해당 기능 미사용 시 빈 문자열 가능)

| Variable | Description | Feature |
|---|---|---|
| `ALPACA_API_KEY` | Alpaca 브로커 API 키 | US 자동매매, 실시간 가격 |
| `ALPACA_SECRET_KEY` | Alpaca 시크릿 키 | US 자동매매, 실시간 가격 |
| `KIS_APP_KEY` | 한국투자증권 앱 키 | KR 주식 데이터/매매 |
| `KIS_APP_SECRET` | 한국투자증권 앱 시크릿 | KR 주식 데이터/매매 |
| `GOOGLE_CLIENT_ID` | Google OAuth 클라이언트 ID | Google 소셜 로그인 |
| `GOOGLE_CLIENT_SECRET` | Google OAuth 시크릿 | Google 소셜 로그인 |

### OPTIONAL -- 미설정 시 해당 기능 비활성화

| Variable | Description | Feature |
|---|---|---|
| `SENTRY_DSN` | Sentry 에러 모니터링 DSN | 에러 추적 |
| `FMP_API_KEY` | Financial Modeling Prep API 키 | 추가 시장 데이터 |
| `SENDGRID_API_KEY` | SendGrid 이메일 API 키 | 이메일 알림 |
| `STRIPE_SECRET_KEY` | Stripe 결제 시크릿 키 | 구독 결제 |
| `STRIPE_WEBHOOK_SECRET` | Stripe 웹훅 서명 검증 | 결제 이벤트 |
| `STRIPE_PRICE_PRO` | Stripe Pro 플랜 가격 ID | 구독 생성 |
| `STRIPE_PRICE_ENTERPRISE` | Stripe Enterprise 플랜 가격 ID | 구독 생성 |
| `VAPID_PRIVATE_KEY` | Web Push VAPID 키 | 푸시 알림 |
| `VAPID_EMAIL` | VAPID 연락처 이메일 | 푸시 알림 |
| `RATELIMIT_STORAGE_URI` | Rate limiter 스토리지. 기본값: `memory://` | 멀티프로세스 환경 |
| `SESSION_COOKIE_DOMAIN` | 쿠키 도메인. 미설정 시 자동 감지 | 크로스도메인 세션 |

---

## Vercel (Frontend) Environment Variables

Vercel Dashboard > Project > Settings > Environment Variables 에서 설정.

| Variable | Description | Example |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Railway 백엔드 URL (프로토콜 포함, 후행 슬래시 없음) | `https://stockpilot-backend-production.up.railway.app` |

Note: `NEXT_PUBLIC_` 접두사가 있어야 클라이언트 사이드에서 접근 가능.
단, 이 값은 Next.js rewrites에서 서버사이드로만 사용되므로 클라이언트에 노출되지 않습니다.

---

## Local Development (.env)

로컬 개발 시 프로젝트 루트의 `.env` 파일 사용.
`.env`는 `.gitignore`에 포함되어 있으므로 Git에 커밋되지 않습니다.

```bash
# --- Core ---
SECRET_KEY=dev-secret-key-change-in-production
CSRF_SECRET=dev-csrf-secret-change-in-production
# DATABASE_URL 미설정 시 SQLite 자동 사용 (로컬 개발용)

# --- AI ---
ANTHROPIC_API_KEY=YOUR_ANTHROPIC_KEY

# --- Broker ---
ALPACA_API_KEY=YOUR_ALPACA_KEY
ALPACA_SECRET_KEY=YOUR_ALPACA_SECRET
KIS_APP_KEY=YOUR_KIS_APP_KEY
KIS_APP_SECRET=YOUR_KIS_APP_SECRET

# --- OAuth ---
GOOGLE_CLIENT_ID=YOUR_GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET=YOUR_GOOGLE_CLIENT_SECRET

# --- Monitoring ---
SENTRY_DSN=YOUR_SENTRY_DSN

# --- Data ---
FMP_API_KEY=YOUR_FMP_KEY

# --- Email ---
SENDGRID_API_KEY=YOUR_SENDGRID_KEY
```

---

## Security Notes

1. 모든 시크릿은 Railway/Vercel 시크릿 매니저에만 저장. 코드/로그에 절대 노출 금지.
2. SECRET_KEY, CSRF_SECRET는 반드시 고정값 사용. 서버 재시작 시 세션 무효화 방지.
3. CORS_ORIGINS에는 정확한 Vercel 도메인만 허용. 와일드카드(*) 사용 금지.
4. Google OAuth: Google Cloud Console에서 프로덕션 리다이렉트 URI 추가 필요.
   - `https://<railway-domain>/api/auth/google/callback`
5. .env 파일이 Git에 커밋된 적 있다면 모든 키 즉시 로테이션 필수.
