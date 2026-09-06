# PivoxQuant — 시스템 아키텍처 문서

> 최종 업데이트: 2026-04-17
> 문서 작성 기준: 실제 코드 파일 직접 분석 (추측 없음)

---

## 목차

1. [Overview](#1-overview)
2. [기술 스택 상세](#2-기술-스택-상세)
3. [백엔드 구조](#3-백엔드-구조)
4. [프론트엔드 구조](#4-프론트엔드-구조)
5. [데이터 흐름 상세](#5-데이터-흐름-상세)
6. [외부 통합](#6-외부-통합)
7. [배포 아키텍처](#7-배포-아키텍처)
8. [보안 구조](#8-보안-구조)

---

## 1. Overview

**한 줄 요약**: PivoxQuant는 AI + 퀀트 엔진 기반 개인 투자 분석 플랫폼으로, 미국·한국 주식을 지원하며 Flask REST API 백엔드와 Next.js 16 프론트엔드의 분리 배포 구조(Railway + Vercel)를 채택한다.

### 전체 시스템 다이어그램

```
┌────────────────────────────────────────────────────────────────────────┐
│                            User (Browser)                              │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ HTTPS
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│               Next.js 16 Frontend (Vercel)                             │
│   pivoxquant.vercel.app  /  pivoxquant.com                             │
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  App Router  │  middleware.ts  │  AuthProvider  │  SWR Hooks    │  │
│  └─────────────────────────┬───────────────────────────────────────┘  │
│                             │ /api/* rewrites                          │
└─────────────────────────────┼──────────────────────────────────────────┘
                              │ HTTP Proxy (next.config.ts rewrites)
                              │
┌─────────────────────────────┼──────────────────────────────────────────┐
│           Flask Backend (Railway)                                       │
│   <RAILWAY_BACKEND_URL>  :  PORT                        │
│                                                                         │
│  ┌──────────────┐  ┌──────────────────────────────────────────────┐   │
│  │  security.py  │  │  routes/ (23개 Blueprint + agent_worker)     │   │
│  │  CORS/CSRF/RL │  │  auth, portfolio, signals, ai, market, ...   │   │
│  └──────────────┘  └──────────────────┬──────────────────────────┘   │
│                                        │                               │
│  ┌─────────────────────────────────────▼──────────────────────────┐   │
│  │  services/ container.py                                         │   │
│  │  QuantEngine │ DataFetcher │ AIService │ AutoTrader │ ...       │   │
│  └──────────┬────────────────────────────────────────────────────┘   │
│             │                                                          │
│  ┌──────────▼──────────────────────────────────────────────────────┐  │
│  │  models/ (SQLAlchemy ORM)                                        │  │
│  │  User │ Position │ SignalCache │ Alert │ Watchlist │ ...         │  │
│  └──────────┬──────────────────────────────────────────────────────┘  │
└─────────────┼──────────────────────────────────────────────────────────┘
              │
    ┌─────────┼──────────────────────────────────────────────┐
    │         │  외부 서비스 / 인프라                           │
    │  ┌──────▼──────┐  ┌──────────────┐  ┌───────────────┐  │
    │  │  PostgreSQL  │  │  Claude API  │  │  FMP / Alpaca │  │
    │  │  (Railway)   │  │  (Anthropic) │  │  KIS / pykrx  │  │
    │  └─────────────┘  └──────────────┘  └───────────────┘  │
    │  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
    │  │  Stripe      │  │  Google OAuth│  │  Kakao OAuth  │  │
    │  │  (결제)      │  │              │  │               │  │
    │  └──────────────┘  └──────────────┘  └───────────────┘  │
    └────────────────────────────────────────────────────────┘
```

### 기술 스택 한눈에

| 계층 | 기술 | 버전 |
|------|------|------|
| Frontend | Next.js (App Router) | 16.x |
| Frontend 언어 | TypeScript | 5.x |
| Frontend 스타일 | Tailwind CSS | 4.x |
| Frontend 데이터 | SWR | 최신 |
| Backend Framework | Flask | 3.x |
| Backend 언어 | Python | 3.11 |
| ORM | SQLAlchemy + Flask-SQLAlchemy | 2.x |
| DB (개발) | SQLite | - |
| DB (프로덕션) | PostgreSQL (Railway) | 15.x |
| 인증 | Flask-Login + Authlib (OAuth) | - |
| 보안 미들웨어 | Flask-CORS, Flask-Limiter | - |
| AI | Anthropic Claude API | - |
| 스케줄러 | APScheduler | - |
| 에러 모니터링 | Sentry SDK | - |
| 앱 서버 | Gunicorn (gevent worker) | - |
| 컨테이너 | Docker (Python 3.11-slim) | - |

---

## 2. 기술 스택 상세

### 왜 이 스택을 선택했는가

| Layer | 기술 | 왜 선택 |
|-------|------|---------|
| Frontend | Next.js 16 App Router | SSR/SSG 지원, Vercel 무료 배포, `/api/*` rewrite 프록시로 CORS 우회 가능 |
| Frontend 데이터 페칭 | SWR | stale-while-revalidate 전략으로 실시간 감각 구현, 캐시 무효화 단순화 |
| Frontend 스타일 | Tailwind CSS 4 | 디자인 시스템 토큰(CSS 변수) 기반, 빠른 프로토타이핑 |
| Backend | Flask | 경량, Blueprint 모듈화 용이, Python AI/금융 생태계와 자연스러운 연동 |
| ORM | SQLAlchemy | PostgreSQL/SQLite 동시 지원, 마이그레이션 추상화 |
| DB (개발) | SQLite | 로컬 개발용 파일 DB, 설정 없이 즉시 시작 |
| DB (프로덕션) | PostgreSQL (Railway) | 트랜잭션 안정성, pg_advisory_lock으로 멀티워커 마이그레이션 경합 방지 |
| OAuth | Authlib | Google/Kakao 표준 OAuth2/OIDC 통합, state CSRF 방어 내장 |
| AI | Claude API (Anthropic) | SWOT, Chat 스트리밍, 시장 코멘터리, 모닝 브리핑 등 다목적 사용 |
| 스케줄러 | APScheduler | 퀀트 시그널 3분 주기 갱신, 모닝 브리핑 매일 06:00 KST 실행 |
| 에러 트래킹 | Sentry | 민감 헤더 필터링 (cookie, authorization, x-csrf-token) 적용, 노이즈 필터로 FMP 404 등 비액션 에러 제거 |
| 앱 서버 | Gunicorn (gevent) | 비동기 SSE(Server-Sent Events) 지원을 위한 gevent worker, 단일 워커로 스케줄러 중복 실행 방지 |

### 패키지 연결 구조 (백엔드)

```
app.py
 ├── config.py          — DATABASE_URL, SECRET_KEY, pool 설정
 ├── extensions.py      — db(SQLAlchemy), login_manager, migrate 싱글턴
 ├── security.py        — CORS, Limiter, CSRF, 세션 만료, 보안 헤더
 ├── routes/__init__.py — 23개 Blueprint 일괄 등록
 └── services/container.py — QuantEngine, DataFetcher, AIService 등 싱글턴
```

### Connection Pool 설정 (config.py, line 46-52)

프로덕션 PostgreSQL 기준:
- `pool_size=5`, `max_overflow=10` — 최대 15 동시 연결
- `pool_recycle=1800` — 30분마다 연결 재활용 (Railway idle timeout 방어)
- `pool_pre_ping=True` — 사용 전 연결 유효성 검증

---

## 3. 백엔드 구조

### App Factory 패턴 (app.py)

`create_app()` 함수가 Flask 앱 인스턴스를 생성하고 모든 확장, 보안 미들웨어, Blueprint를 등록한다. 이 패턴 덕분에 테스트 시 별도 설정으로 앱을 생성할 수 있다.

```
create_app()
 1. app.config.from_object(Config)
 2. init_security(app)          — CORS/RateLimit/CSRF/Session
 3. db.init_app(app)
 4. migrate.init_app(app, db)
 5. login_manager.init_app(app)
 6. register_blueprints(app)    — 23개 Blueprint
 7. init_oauth(app)             — Google + Kakao
 8. fx_service.init_async()     — 환율 비동기 초기화
 9. db.create_all() + _run_migrations(app)
10. Thread(cache-warmup)        — 시그널 캐시 예열 (daemon thread)
11. _init_scheduler(app)        — RUN_SCHEDULER=1 일 때만
```

### extensions.py — 공유 싱글턴 (line 1-8)

```python
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
```

세 싱글턴은 모듈 로드 시 생성되고, `init_app(app)` 호출로 Flask 앱과 바인딩된다. 순환 임포트 없이 여러 모듈에서 `from extensions import db`로 공유 가능하다.

### routes/ — Blueprint 매핑 (23개 파일)

| Blueprint | URL prefix | 주요 엔드포인트 |
|-----------|------------|----------------|
| `auth_bp` | `/api/auth` | register, login, logout, me, google, kakao, delete-account |
| `portfolio_bp` | `/api/portfolio` | GET/POST positions, analytics, history, buy/sell, capital, simulate/* |
| `signals_bp` | `/api` | /signals, /signals/\<ticker\>, /signals/refresh, /scan, short-interest, insider, disposition, ofi |
| `discover_bp` | `/api` | /discover |
| `market_bp` | `/api` | /search, /lookup/\<ticker\>, /market/overview, /market/status, /market/fx, /macro, /sectors, /chart/\<ticker\>, /prices, /earnings, /peers/\<ticker\>, /profile/\<ticker\>, /dividend/\<ticker\>, /news/\<ticker\> |
| `daytrade_bp` | `/api/daytrade` | status, scan, analyze/\<ticker\>, chart/\<ticker\>, prices, stream |
| `alerts_bp` | `/api/alerts` | GET list, POST read, DELETE clear, price-check |
| `trades_bp` | `/api/trades` | trade history |
| `autotrade_bp` | `/api/autotrade` | status, start, stop, sell-all, pending, approve/\<id\>, reject/\<id\> |
| `ai_bp` | `/api/ai` | status, swot, competitor, sector-trend, chat (SSE), commentary, morning-summary, coaching, earnings-tone, sector-regime, risk-summary |
| `watchlist_bp` | `/api/watchlist` | GET list, POST add, DELETE /\<id\> |
| `backtest_bp` | `/api` | /backtest/\<ticker\> |
| `quant_bp` | `/api` | /vix-strategy, /cross-asset, /stat-arb, /indicators/\<ticker\>, /screener/canslim/\<ticker\>, /regime/interest-rate, /risk/\*, /analytics/\*, /tools/\*, /performance/ledger |
| `realtime_bp` | `/api/realtime` | stream (SSE), portfolio-stream (SSE), price/\<ticker\>, status |
| `profile_bp` | `/api/profile` | GET/PUT profile, onboarding, questionnaire, capital |
| `broker_sync_bp` | `/api/broker` | sync, sync-kis, sync-status, connections |
| `billing_bp` | `/api/billing` | create-checkout, subscription, portal, webhook |
| `push_bp` | `/api/push` | subscribe, unsubscribe, status |
| `share_bp` | `/api/portfolio` | POST /share, GET /share/\<token\> |
| `simulate_bp` | `/api` | /simulate/counterfactual |
| `counterfactual_bp` | `/api` | counterfactual 관련 |
| `morning_brief_bp` | `/api` | /morning-brief, /brief/today, /brief/archive |
| `growth_bp` (agent_worker) | `/api/growth` | data, today, reflect, weekly |

**조건부 Blueprint** (환경변수 설정 시에만 등록):
- `command_center_bp` — `ENABLE_COMMAND_CENTER=1` 일 때만 (로컬 개발용, 인증 없음)
- `dev_auth_bp` — `DEV_LOGIN_SECRET` 설정 시 (E2E 테스트용, 프로덕션 절대 금지)

### services/ — 서비스 레이어 (13개 파일)

| 파일 | 역할 |
|------|------|
| `container.py` | 서비스 싱글턴 관리 — QuantEngine, DataFetcher, AIService, DayTradeService, RealtimeService, AutoTrader, BrokerSyncService |
| `cache_service.py` | SignalCache DB upsert, discover 캐시(TTL 10분), earnings tone 캐시(TTL 90일), 일별 Claude API 예산 제한(50회/일) |
| `fx_service.py` | USD/KRW 환율 관리 — KIS→FMP→exchangerate-api 폴백 체인, 5초 단기 캐시, 10분 stale 경고 |
| `alert_service.py` | 퀀트 시그널 기반 Alert 생성 조건 판단 |
| `serializers.py` | User, Position 등 ORM 모델 → JSON dict 직렬화 |
| `kr_stock_registry.py` | 한국 주식 종목 마스터 검색 (kr_stocks_data.json 기반, 상위 ~250개 KOSPI/KOSDAQ) |
| `us_stock_registry.py` | 미국 주식 종목 마스터 검색 (us_stocks_data.json 기반) |
| `market_status.py` | 시장 개장/폐장 상태 판단 |
| `morning_brief_service.py` | 매일 06:00 KST 모든 유저 모닝 브리핑 생성 (Claude Haiku 사용) |
| `broker_sync_service.py` | Alpaca/KIS 계좌 포지션 동기화 |
| `push_service.py` | Web Push 알림 발송 |
| `thesis_service.py` | 매수 thesis 주간 AI 유효성 체크 |
| `kr_stocks_data.json` / `us_stocks_data.json` | 종목 마스터 데이터 (정적 파일) |

### models/ — SQLAlchemy ORM (11개 모델)

| 모델 | 테이블 | 주요 컬럼 |
|------|--------|-----------|
| `User` | `users` | id, email, password_hash, oauth_provider, google_id, kakao_id, avatar_url, available_capital, available_capital_krw, risk_profile, subscription_tier, stripe_customer_id, stripe_subscription_id, onboarding_completed |
| `Position` | `positions` | id, user_id(FK), ticker, shares, avg_cost, buy_fx_rate, thesis, thesis_status, thesis_last_checked |
| `Alert` | `alerts` | id, user_id(FK), ticker, message, signal, score, rec_shares, rec_investment, is_read |
| `SignalCache` | `signal_cache` | ticker(PK), data_json(Text), updated_at |
| `TradeHistory` | `trade_history` | id, user_id(FK), ticker, action(BUY/SELL), shares, price_per_share, total_value, pnl, pnl_pct, currency |
| `Watchlist` | `watchlist` | id, user_id(FK), ticker, added_at |
| `InvestmentProfile` | `investment_profiles` | user_id(FK unique), profile_type(conservative/balanced/growth/aggressive), 온보딩 8문항, tech_weight/fund_weight/news_weight 등 퀀트 파라미터 |
| `BrokerConnection` | `broker_connections` | user_id(FK), broker(alpaca/kis), access_token, account_id, is_paper, is_active |
| `PushSubscription` | `push_subscriptions` | user_id(FK), endpoint, keys |
| `PortfolioShare` | `portfolio_shares` | token(PK), user_id(FK), 공유 설정 |
| `MorningBrief` | `morning_briefs` | user_id(FK)+brief_date(unique), content(JSON) |

### 배경 스케줄러 (app.py, line 271-329)

`RUN_SCHEDULER=1` 환경변수로 opt-in. Gunicorn 멀티워커 환경에서 중복 실행 방지 목적:

| 작업 | 주기 | 설명 |
|------|------|------|
| `_scheduled_refresh` | 3분 | 보유 종목 전체 퀀트 시그널 재분석, SignalCache 갱신, Alert 생성 |
| `_scheduled_morning_briefs` | 매일 06:00 KST | 전 유저 모닝 브리핑 생성 |
| `fx_rate_refresh` | 1분 | USD/KRW 환율 갱신 (FMP→exchangerate-api 폴백) |

---

## 4. 프론트엔드 구조

### Next.js App Router 구조

```
frontend/src/
├── app/
│   ├── layout.tsx                    # 루트 레이아웃 — Geist, IBM Plex Mono, Pretendard 폰트
│   ├── page.tsx                      # 루트 페이지 (랜딩 또는 홈 리다이렉트)
│   ├── globals.css                   # Vantablack Luxe 디자인 시스템 CSS 변수
│   ├── providers.tsx                 # AuthProvider, SWR Config 등 글로벌 컨텍스트
│   ├── manifest.ts                   # PWA manifest
│   ├── robots.ts / sitemap.ts        # SEO 자동 생성
│   ├── (auth)/
│   │   ├── login/page.tsx            # Google/Kakao OAuth + 이메일 로그인
│   │   ├── signup/page.tsx           # 회원가입
│   │   └── onboarding/page.tsx       # 온보딩 설문 (6문항 → 투자 프로필 결정)
│   ├── (dashboard)/                  # 로그인 필요 대시보드 영역
│   │   ├── home/page.tsx             # 메인 대시보드
│   │   ├── portfolio/page.tsx        # 포트폴리오 보기/관리
│   │   ├── market/page.tsx           # 시장 현황 (미국/한국)
│   │   ├── signals/page.tsx          # 퀀트 시그널 목록
│   │   ├── discover/page.tsx         # 종목 스캐너
│   │   ├── watchlist/page.tsx        # 관심 종목
│   │   ├── detail/[ticker]/page.tsx  # 종목 상세 분석
│   │   ├── alerts/page.tsx           # 알림 센터
│   │   ├── ai-chat/page.tsx          # AI 채팅 (SSE 스트리밍)
│   │   ├── ai/page.tsx               # AI 분석 도구 모음
│   │   ├── autotrade/page.tsx        # 자동매매 제어
│   │   ├── settings/page.tsx         # 계정 설정 / 브로커 연결
│   │   ├── risk/page.tsx             # 7-Layer Risk Defense
│   │   ├── morning-brief/page.tsx    # 모닝 브리핑
│   │   └── growth/page.tsx           # 성장 트래킹
│   ├── beta-gate/page.tsx            # 비공개 베타 비밀번호 입력 페이지
│   ├── simulator/what-if/page.tsx    # 가상 투자 시뮬레이터 (비로그인 접근 가능)
│   ├── pricing/page.tsx              # 구독 플랜 (Free/Pro/Premium)
│   ├── features/                     # 기능 소개 6개 페이지
│   ├── terms/page.tsx                # 이용약관
│   └── privacy/page.tsx             # 개인정보처리방침
├── middleware.ts                     # Edge Runtime — Beta 게이트, Locale, CSP
└── lib/
    ├── api.ts                        # apiFetch — CSRF 토큰 자동 주입, credentials
    ├── auth.tsx                      # AuthProvider + useAuth hook
    ├── endpoints.ts                  # 백엔드 API URL 상수 전체 (단일 진실 공급원)
    ├── hooks.ts                      # SWR 기반 데이터 페칭 훅 17개
    ├── types.ts                      # TypeScript 인터페이스 (백엔드 응답 타입)
    ├── format.ts                     # fmtUsd, fmtPct, fmtDate 등 포매터
    ├── realtime.tsx                  # SSE RealtimeProvider (EventSource 래퍼)
    ├── utils.ts                      # cn() (tailwind-merge)
    └── push.ts                       # Web Push 구독 관리
```

### Server Components vs Client Components

Next.js App Router에서 기본 모든 컴포넌트는 Server Component이다. PivoxQuant의 실제 사용 패턴:

- **`"use client"` 선언 필수**: `login/page.tsx` 등 useState/useEffect/useAuth를 사용하는 모든 페이지 컴포넌트
- **API 데이터 페칭**: 전적으로 클라이언트 SWR에 의존 — Server Component 내 `fetch()`는 사용하지 않음 (Flask 세션 쿠키 전달 제약)
- **AuthProvider** (`providers.tsx`): `"use client"` 래퍼로 전체 트리에 인증 컨텍스트 제공

### middleware.ts — Edge Runtime 처리 (2가지 역할)

1. **Locale 감지**: `sp_locale` 쿠키 → `Accept-Language` 헤더 순으로 `ko`/`en` 감지, 첫 방문 시 쿠키 설정.
2. **CSP 헤더 주입**: 요청마다 nonce 생성, 개발/프로덕션 환경별 `connect-src` 분기 적용.

### next.config.ts — API 프록시 (line 8-19)

```typescript
const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  (process.env.VERCEL ? process.env.NEXT_PUBLIC_API_URL : "http://localhost:5050");
// 주의: Vercel env에 NEXT_PUBLIC_API_URL=<RAILWAY_BACKEND_URL> 설정 필요

rewrites: [{ source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` }]
```

Vercel 배포 시 Railway 백엔드 URL로 하드코딩, 로컬은 `localhost:5050`. 이 프록시 덕분에 프론트엔드는 항상 동일 Origin으로 API를 호출하여 CORS 문제를 완전히 우회한다.

---

## 5. 데이터 흐름 상세

### 시나리오 A: 로그인 → 포트폴리오 조회

```
[사용자 - 로그인 버튼 클릭]
    │
    ▼
[login/page.tsx]
  useAuth().login(email, password) 호출
    │
    ▼
[lib/api.ts - apiFetch]
  1. GET /api/auth/me → csrf_token 쿠키 수신
  2. POST /api/auth/login
     Headers: X-CSRF-Token: <cookie 값>, Content-Type: application/json
     Body: { email, password }
     Credentials: include (Flask 세션 쿠키 전송)
    │
    ▼
[next.config.ts rewrite]
  /api/auth/login → https://railway.../api/auth/login
    │
    ▼
[Flask - routes/auth.py @auth_bp.route("/login")]
  @auth_rate_limit (5/분 제한)
  1. security.py before_request:
     - _enforce_session(): 비활성 타임아웃 체크 (2시간)
     - _csrf_protect(): POST → csrf_token 쿠키 vs X-CSRF-Token 헤더 비교 검증
  2. User.query.filter_by(email=...).first()
  3. user.chk_pw(password) — werkzeug pbkdf2:sha256 검증
  4. session.clear() — Session Fixation 방어
  5. login_user(user, remember=True)
  6. 응답: { ok: True, user: serialize_user(user) }
     Set-Cookie: session=...; SameSite=Lax; HttpOnly; Secure(prod)
    │
    ▼
[프론트엔드 AuthProvider]
  setUser(data.user)
  router.push("/home")
    │
    ▼
[home/page.tsx → SWR hooks.ts]
  usePortfolio() → GET /api/portfolio
    │
    ▼
[Flask - routes/portfolio.py @portfolio_bp.route("")]
  @api_auth (login_required)
  1. fx_service.refresh() — 환율 최신화
  2. Position.query.filter_by(user_id=current_user.id).all()
  3. 각 Position에 대해 SignalCache.query.get(ticker)
     - 캐시 있으면: cached.data_json에서 현재가 추출
     - 캐시 없으면: avg_cost를 현재가로 폴백
  4. 원화 환산 (buy_fx_rate 활용)
  5. JSON 응답 반환
    │
    ▼
[portfolio/page.tsx]
  포지션 목록 렌더링
```

---

### 시나리오 B: 종목 검색 → 상세 분석 (15팩터)

```
[사용자 - 검색창에 "AAPL" 입력]
    │
    ▼
[상단 검색 컴포넌트]
  GET /api/search?q=AAPL
    │
    ▼
[Flask - routes/market.py @market_bp.route("/search")]
  @api_auth
  1. kr_stock_registry.search("AAPL", limit=15) — 한국 종목 매칭 시도
  2. FMP /stable/search-symbol?query=AAPL API 호출 (US 주식, v3 deprecated 2025-08-31)
  3. 로컬 us_stock_registry 폴백 (FMP 실패 시)
  4. 중복 제거 후 통합 결과 반환
    │
    ▼
[사용자 - "AAPL" 선택]
  router.push("/detail/AAPL")
    │
    ▼
[detail/[ticker]/page.tsx]
  GET /api/signals/AAPL
    │
    ▼
[Flask - routes/signals.py @signals_bp.route("/signals/<ticker>")]
  @api_auth
  1. engine.analyze("AAPL", capital, capital_krw, fx_rate, profile_params)
     ┌── QuantEngine.analyze() 내부 ──────────────────────────────────┐
     │  DataFetcher.get_price_data(ticker)  ← Alpaca API (우선)       │
     │  DataFetcher.get_fundamentals(ticker) ← FMP API (폴백)         │
     │  15팩터 스코어링:                                               │
     │    - Technical (RSI, MACD, Bollinger, Momentum, Volume)        │
     │    - Fundamental (P/E, EPS Growth, ROE, FCF, Margin)          │
     │    - News Sentiment (FMP news sentiment)                       │
     │    - profile_params (InvestmentProfile tech/fund/news 가중치)  │
     │  종합 Score 0-100 계산                                         │
     │  Signal: POSITIVE / NEGATIVE / NEUTRAL (BUY/SELL 금지)        │
     │  Take Profit / Stop Loss 범위 계산 (profile_params 기반)       │
     └────────────────────────────────────────────────────────────────┘
  2. cache_service.save_signal("AAPL", result)  ← SignalCache DB upsert
  3. JSON 응답 반환 (price, signal, score, tp, sl, fundamentals, ...)
    │
    ▼
[detail/[ticker]/page.tsx]
  종목 상세 렌더링 (차트, 지표, 시그널, 섹터 등)
```

---

### 시나리오 C: AI Chat 요청 → Claude API

```
[사용자 - ai-chat 페이지에서 메시지 입력]
    │
    ▼
[ai-chat/page.tsx]
  POST /api/ai/chat
  Body: { message: "내 포트폴리오 리스크 분석해줘", history: [...] }
    │
    ▼
[Flask - routes/ai.py @ai_bp.route("/chat")]
  @ai_rate_limit (10/분 — Claude API 비용 제한)
  @api_auth
  1. Position.query.filter_by(user_id=...).all() — 보유 종목 목록
  2. SignalCache 조회 — 각 포지션의 최신 시그널 데이터
  3. DataFetcher.get_macro_data() — S&P500, VIX, 금리 등 매크로
  4. ai.build_portfolio_context(user, positions, sig_cache, macro)
     → 컨텍스트 문자열 조합
  5. ai.chat_stream(message, history, context) 호출
     ┌── AIService.chat_stream() 내부 ───────────────────────────────┐
     │  Anthropic Claude API 호출 (stream=True)                      │
     │  system: 포트폴리오 컨텍스트 + 법적 면책 조항 (투자조언 금지)  │
     │  messages: history + 현재 message                             │
     │  model: claude-3-5-haiku (비용 최적화)                        │
     │  max_tokens: 설정값                                            │
     └───────────────────────────────────────────────────────────────┘
  6. Generator → SSE(text/event-stream) 스트리밍 응답
     data: {"text": "안녕하세요..."}\n\n
     data: {"text": " 포트폴리오를..."}\n\n
     data: {"done": true}\n\n
    │
    ▼
[lib/realtime.tsx 또는 직접 fetch() EventSource]
  텍스트 청크 누적 → UI 실시간 렌더링
    │
    ▼
[ai-chat/page.tsx]
  스트리밍 완료 → 최종 응답 표시
```

**중요 법적 제약**: AI 응답 생성 시 system prompt에 투자 조언 금지 조항 포함. 시그널 레이블은 POSITIVE/NEGATIVE/NEUTRAL만 사용 (BUY/SELL/HOLD 절대 사용 금지 — 자본시장법 준수).

---

## 6. 외부 통합

### 통합 목록 (코드 확인 기준)

| 서비스 | 파일 | 용도 | 인증 방식 |
|--------|------|------|-----------|
| KIS (한국투자증권) | `kis_service.py`, `services/container.py` | 한국 주식 시세 조회, 계좌 포지션 동기화 (read-only, 주문 disabled) | KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO 환경변수 |
| Alpaca | `data_fetcher.py`, `services/container.py` | 미국 주식 시세/바 데이터 (paper_trading=True), 계좌 동기화 | ALPACA_API_KEY, ALPACA_SECRET_KEY |
| FMP (Financial Modeling Prep) | `fmp_service.py`, `data_fetcher.py` | 펀더멘털, 뉴스 센티먼트, 검색, 배당, 섹터 데이터 | FMP_API_KEY 환경변수, v4 Stable Starter 플랜 |
| Claude API (Anthropic) | `ai_service.py` | SWOT 분석, Chat 스트리밍, 시장 코멘터리, 모닝 브리핑, 코칭, 섹터 트렌드 | ANTHROPIC_API_KEY |
| Stripe | `routes/billing.py` | SaaS 구독 결제 (Pro ₩9,900/월, Premium ₩19,900/월), 고객 포털 | STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_PRO, STRIPE_PRICE_PREMIUM |
| Google OAuth | `routes/auth.py` → Authlib | 소셜 로그인 (OIDC) | GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET |
| Kakao OAuth | `routes/auth.py` → Authlib | 소셜 로그인 | KAKAO_CLIENT_ID, KAKAO_CLIENT_SECRET |
| Sentry | `app.py` line 63-66 | 에러 트래킹 (민감 헤더 필터링, 노이즈 제거) | SENTRY_DSN |
| exchangerate-api.com | `services/fx_service.py` | USD/KRW 환율 백업 소스 (FMP 실패 시) | 무료 플랜 |

### 데이터 우선순위 폴백 체인

```
미국 주식 시세:
  Alpaca Markets API
    ├─ 성공 → 반환
    └─ 실패 → FMP v4 /historical-price-full
               ├─ 성공 → 반환
               └─ 실패 → SignalCache 기존 데이터

USD/KRW 환율:
  KIS API (실시간)
    ├─ 성공 → 반환
    └─ 실패 → FMP /quote/USDKRW
               ├─ 성공 → 반환
               └─ 실패 → exchangerate-api.com
                          ├─ 성공 → 반환
                          └─ 실패 → 캐시된 마지막 값 (기본 1380.0)

종목 검색:
  1. kr_stock_registry (로컬 JSON, 한국 종목)
  2. FMP /v3/search
  3. us_stock_registry (로컬 JSON, 미국 종목)
```

### Stripe Webhook 보안

`routes/billing.py`에서 Stripe webhook은 `_CSRF_EXEMPT_PREFIXES` (`/api/billing/webhook`)에 등록되어 CSRF 검증에서 제외된다. 대신 Stripe의 자체 서명 검증 (`stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)`)으로 대체 보안을 제공한다.

---

## 7. 배포 아키텍처

### 현재 배포 상태

```
┌───────────────────────────────────────────────────────┐
│  pivoxquant.com / pivoxquant.vercel.app               │
│                                                       │
│  ┌──────────────────────────────────────────────┐    │
│  │  Vercel (프론트엔드)                           │    │
│  │  Next.js 16 — Edge Network CDN                │    │
│  │  자동 배포: GitHub seanbae-analyst/pivoxquant  │    │
│  │  커스텀 도메인: pivoxquant.com (가비아 DNS)    │    │
│  └──────────────────────────────────────────────┘    │
│                  │ /api/* rewrite                     │
│                  ▼                                    │
│  ┌──────────────────────────────────────────────┐    │
│  │  Railway (백엔드 + DB)          ⏸ 재시도 필요  │    │
│  │  <RAILWAY_BACKEND_URL>          │    │
│  │                                                │    │
│  │  [web dyno]                                   │    │
│  │  gunicorn app:app                             │    │
│  │    --worker-class gevent                      │    │
│  │    --workers 1                                │    │
│  │    --bind 0.0.0.0:$PORT                       │    │
│  │    --timeout 120                              │    │
│  │                                                │    │
│  │  [release phase]                              │    │
│  │  flask db upgrade || echo "skipped"           │    │
│  │                                                │    │
│  │  [PostgreSQL Add-on]                          │    │
│  │  Railway 내부 PostgreSQL 15                   │    │
│  └──────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────┘
```

### Dockerfile (실제 내용)

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5050
CMD ["sh", "-c", "gunicorn app:app --worker-class gevent --workers 1 --bind 0.0.0.0:${PORT:-5050} --timeout 120 --keep-alive 5 --log-level info"]
```

### 환경 변수 (실제 목록, 값 제외)

**Railway 백엔드 필수**:
| 변수명 | 설명 |
|--------|------|
| `SECRET_KEY` | Flask 세션 암호화 키 (고정값 필수 — 멀티워커 세션 유지) |
| `DATABASE_URL` | PostgreSQL 연결 문자열 (Railway 자동 제공) |
| `FLASK_ENV` | `production` |
| `CORS_ORIGINS` | `https://pivoxquant.vercel.app,https://pivoxquant.com` |
| `FRONTEND_URL` | `https://pivoxquant.com` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth |
| `KAKAO_CLIENT_ID` / `KAKAO_CLIENT_SECRET` | Kakao OAuth |
| `ANTHROPIC_API_KEY` | Claude API |
| `FMP_API_KEY` | Financial Modeling Prep |
| `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` | Alpaca Markets |
| `KIS_APP_KEY` / `KIS_APP_SECRET` / `KIS_ACCOUNT_NO` | 한국투자증권 |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` | Stripe |
| `STRIPE_PRICE_PRO` / `STRIPE_PRICE_PREMIUM` | Stripe 플랜 Price ID |
| `SENTRY_DSN` | 에러 트래킹 |
| `RUN_SCHEDULER` | `1` — 단일 워커에서만 스케줄러 실행 |
| `POPULATE_CACHE_ON_BOOT` | `1` — 부팅 시 시그널 캐시 예열 활성화 |

**Vercel 프론트엔드 필수**:
| 변수명 | 설명 |
|--------|------|
| `NEXT_PUBLIC_API_URL` | Railway 백엔드 URL |

### 마이그레이션 전략

Railway 배포 시 `release` phase (`flask db upgrade`)가 웹 dyno 시작 전 실행된다. 멀티워커 경합은 `pg_advisory_lock(hashtext('pivoxquant_migrate'))`으로 방지한다 (`app.py` line 163-171).

---

## 8. 보안 구조

### security.py — 5단계 미들웨어 스택

`init_security(app)` 함수가 모든 보안 레이어를 Flask 앱에 등록한다. Blueprint 등록 전에 반드시 호출해야 한다 (`app.py` line 77).

#### 1단계: CORS (Flask-CORS)

```python
CORS(app,
    origins=_get_cors_origins(),  # CORS_ORIGINS 환경변수 또는 localhost:3000
    supports_credentials=True,    # 세션 쿠키 포함 허용
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    max_age=600,
)
```

프로덕션에서 `CORS_ORIGINS` 미설정 시 빈 리스트로 모든 cross-origin 요청 차단.

#### 2단계: Rate Limiting (Flask-Limiter)

| 데코레이터 | 제한 | 적용 대상 |
|------------|------|-----------|
| 기본 | `100/분` | 모든 엔드포인트 |
| `@auth_rate_limit` | `5/분` | login, register (무차별 공격 방지) |
| `@ai_rate_limit` | `10/분` | AI 분석 엔드포인트 (Claude API 비용 제어) |
| `@trade_rate_limit` | `30/분` | 매매 관련 엔드포인트 |

스토리지: 기본 `memory://`, 멀티프로세스 프로덕션에서는 `RATELIMIT_STORAGE_URI=redis://...` 설정 권장.

#### 3단계: 세션 설정

```python
SESSION_COOKIE_HTTPONLY  = True
SESSION_COOKIE_SAMESITE  = "Lax"
SESSION_COOKIE_SECURE    = True (프로덕션만)
PERMANENT_SESSION_LIFETIME = 24시간
_INACTIVITY_TIMEOUT        = 2시간
```

비활성 2시간 초과 시 세션 자동 초기화 + 강제 로그아웃 (`_enforce_session` before_request hook).

#### 4단계: CSRF — Double Submit Cookie 패턴

구현 위치: `security.py` line 67-111.

```
토큰 구조:
  <random_hex_32>.HMAC-SHA256(<random_hex_32>:<session_id>)
```

- 서버는 모든 응답에 `csrf_token` 쿠키를 설정 (`httpOnly=False` — SPA에서 JS로 읽어야 함)
- 클라이언트(`lib/api.ts`)는 state-changing 요청마다 `X-CSRF-Token` 헤더에 쿠키 값을 그대로 복사
- 서버는 쿠키 값과 헤더 값이 일치하는지, HMAC 서명이 유효한지 2중 검증
- 토큰은 세션 ID에 바인딩되어 다른 세션의 토큰 재사용 불가

**면제 경로** (`_CSRF_EXEMPT_PREFIXES`):
- `/api/billing/webhook` — Stripe 서명 검증으로 대체
- `/api/auth/dev-login` — E2E 테스트용 (DEV_LOGIN_SECRET 설정 시에만 활성)

#### 5단계: 보안 헤더 (모든 응답)

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'self'; ...
Strict-Transport-Security: max-age=31536000; includeSubDomains (프로덕션만)
```

프론트엔드 `next.config.ts`도 동일한 보안 헤더 세트를 독립적으로 설정한다 (HSTS max-age=63072000 + preload).

### OAuth State CSRF 방어 (routes/auth.py)

Google/Kakao OAuth flow에서 CSRF 방어:

```python
# 로그인 시작 (google_login)
state = generate_token()               # Authlib 랜덤 토큰
session["oauth_state_google"] = state  # 세션에 저장
oauth.google.authorize_redirect(redirect_uri, state=state)

# 콜백 수신 (google_callback)
expected_state = session.pop("oauth_state_google", None)
received_state = request.args.get("state")
if not expected_state or expected_state != received_state:
    return redirect("/login?error=state_mismatch")  # 공격 차단
```

Kakao도 동일 패턴 적용 (`oauth_state_kakao`). Open Redirect 방어: `_safe_next()` 함수로 콜백 후 리다이렉트 URL을 상대경로로 강제 제한.

### Session Fixation 방어

로그인/OAuth 콜백 성공 시 `session.clear()` 호출 후 `login_user()` 실행 (auth.py line 85, 97, 176, 259). 기존 세션을 무효화하여 Session Fixation 공격 차단.

### 베타 게이트 — 폐기 (2026-09-04)

`/beta-gate`·`/api/beta-auth`·middleware 게이트 블록·비밀번호/서명 env 전부 삭제. 무료 공개 출시 결정(CEO). `/beta` 는 `/` 로 리다이렉트만 남김.

---

## Completion Checklist

- [x] 8개 섹션 모두: Overview, 기술 스택, 백엔드, 프론트엔드, 데이터 흐름, 외부 통합, 배포, 보안
- [x] 기술 스택 표 (Section 1, 2)
- [x] routes/ 23개 Blueprint 매핑 (Section 3)
- [x] services/ 13개 파일 매핑 (Section 3)
- [x] models/ 11개 모델 매핑 (Section 3)
- [x] 3가지 데이터 흐름 시나리오 (Section 5)
- [x] 외부 API 통합 9개 (KIS, Alpaca, FMP, Claude, Stripe, Google, Kakao, Sentry, exchangerate-api)
- [x] 배포 구조 (Section 7)
- [x] 보안 구조 (Section 8)
- [x] 3500+ 단어
- [x] 실제 코드 파일 직접 분석 (추측 없음)
