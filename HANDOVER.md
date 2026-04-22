# PivoxQuant — 인수인계서 (2026-04-22 세션 종료)

## 🎯 이 세션 핵심 성과

**Commit chain**: `3e5d629 → a74ee76 → 1e602ce → d831c72 → 2490a99 → 7aefb68 → 08885b2 → 2f3a5e8 → 2914467`

1. **PDF 18종 Goldman IC v2 완성** — Playfair Display + EB Garamond, 6-page editorial, 28mm 마진, hand-crafted SVG 전수, legal_filter PASS
2. **Dashboard 전면 재구축** — 11 페이지 Vantablack Terminal 테마, 실 백엔드 SWR 연결, 32 endpoints 실동작
3. **실시간 극한 축소** — FMP quote 5s, SignalCache 30s, SSE 5s (market open) / SWR market-aware `liveRefresh(5s, 60s)`
4. **법무부 감사 CONDITIONAL APPROVED** — 자본시장법 §6/§17/§50 위반 0, 유사투자자문업 신고만 남음
5. **PWA 전면 강화** — 설치가능 + 오프라인 + 푸시알림 + 아이콘 / shortcuts / standalone safe-area
6. **Micro-detail 폴리시** — Chart hover crosshair, PriceWithTimestamp, italic 절제, editorial primitives
7. **Dead code 전수 정리** — 총 44+ 파일 + ~400 CSS 라인 삭제

---

## ✅ 완료 항목

### 📄 PDF 시스템 (18/18)
- `services/artifacts/templates/` — 모든 PDF Goldman IC v2 editorial
- 공용: `_brand_mark.html` (wordmark/monogram) + `_report_css.html` + `_disclaimer.html` + `_embedded_fonts.html`
- 폰트 base64 embed: Source Serif 4 + Playfair Display + EB Garamond + Geist + JetBrains Mono
- 18 PDF 모두 `frontend/public/samples/*.pdf` + `/Users/seanbae/Desktop/취준/Pivoxquant report/*.pdf` 배포
- `_PROHIBITED_PATTERNS` = 0 전수 확인
- **⚠ 사용자 언급**: "PDF 디자인은 나중에 다시 손볼 꺼임" — 세부 조정 보류

### 🎨 랜딩 페이지
- AIDA funnel + Hero cinematic + silver-matte + Bronze Q
- **Pricing KRW**: Observer (0 KRW) / **Operator (9,900 KRW "Most chosen")** / Partner (19,900 KRW)
- Sample Reports 마케팅 게이팅: 3 open (weekly_memo / sp500_backtest / risk_board) + 3 locked preview
- Archetype (20문항 8 유형) / The Engine (58 quant + 7 risk + Claude) / Feature Explorer (17 artifacts)
- `/pricing` 페이지 랜딩과 1:1 sync + FAQ 4 + ConsentModal (금소법 §19)

### 🖥 Dashboard (11 페이지 + 공용)
- Full-screen Vantablack ink + 240px TerminalSidebar (13 메뉴) + TopBar (Search/Bell/Profile)
- **실 백엔드 연결**:
  - `/home` — PORTFOLIO_SUMMARY + POSITIONS + RISK + ALERTS + history + brief
  - `/portfolio` — 4-stat + 9-col table + Add/Buy/Sell/Edit 4 modals + Recent + Sector
  - `/watchlist` — AddSymbol + 7-col + remove + FMP search 자동완성
  - `/risk` — 4 KPI + 7-Layer ladder + 10×10 heatmap + 30-day VaR + **demo fallback (401/empty)**
  - `/discover` — 5 섹션 (Overview/US/KR Movers/Sectors/Screeners) + mock fallback
  - `/market` — US/KR tabs + IndexCard + FX + Earnings Calendar + Market Pulse
  - `/signals` — 3-column POS/NEU/NEG + expandable drawer (4-pillar breakdown)
  - `/ai-chat` — Claude streaming + 4 suggestions + bronze bubbles + disclaimer bottom
  - `/autotrade` — Kill Switch + Paper banner + "What is Autotrade?" explainer + 5 circuit breakers + pending log + FAQ
  - `/alerts` — 4-stat + 3 filter tabs + table + mark-all-as-read
  - `/detail/[ticker]` — Price hero + Chart (1M/3M/6M/1Y/2Y) + Fundamentals + 4-pillar + News + Insider (US) + Related artifacts
  - `/morning-brief` — "Good morning." hero + 3-up overnight + 5-tile macro + earnings calendar
  - `/reports` — 17 artifact grid + tier gate
  - `/settings` + `/settings/profile` — Profile / Brokers / Preferences / Subscription / Danger zone

### 🔌 Broker 연동
- **KIS** (한국투자증권): read-only, `buy_order/sell_order/_place_order` 전부 disabled. 계좌 `XXXXXXXX-01` 연결 준비됨
- **Alpaca**: paper mode only. `AlpacaCard` + `AlpacaConnectModal` 신규. `routes: /api/broker/alpaca/connect|status|disconnect|sync`

### ⚡ 실시간 데이터 파이프라인

**Backend cache TTL (market-aware)**:
| 리소스 | Open | Closed |
|---|---|---|
| FMP quote | 5s | 30s |
| SignalCache | 30s | 120s |
| Market indices | 15s | 300s |
| FX | 5s | 30s |
| SSE | 5s | 30s |

**Frontend SWR (`liveRefresh()` lambda)**:
- /home /portfolio /watchlist / /market /detail: 5s open / 60s closed
- /risk /signals: 10s open / 60s closed
- /discover: 60s open / 5min closed

**UI 인디케이터**:
- `<PriceWithTimestamp>` — 1s tick + traffic-light dot (🟢 live / 🟡 stale / 🟤 cached) + "3s ago"
- 헤더 배너 "Live · 3s ago" / "Closed · 17m ago" (home/portfolio/watchlist/market)
- IndexCard 녹색 pulse dot

**핵심 신규 파일**:
- `services/price_overlay.py` — realtime → cache → fallback chain
- `services/cache_ttl.py` — market-aware TTL helpers
- `frontend/src/lib/market-hours.ts` — 클라이언트 장 시간 감지
- `frontend/src/components/ui/price-with-timestamp.tsx`
- `frontend/src/components/charts/interactive-line-chart.tsx` — crosshair + tooltip
- `frontend/src/components/charts/interactive-bar-chart.tsx`

### 📱 PWA
- `manifest.ts`: shortcuts (Portfolio/Market/Risk/Watchlist), ko-KR, Vantablack theme, 7 icons
- `public/sw.js` v3: per-route cache (network-only for auth/realtime, SWR for observatory, cache-first static)
- `components/pwa/install-prompt.tsx` editorial dismissible (7일)
- `components/pwa/push-permission.tsx` (14일)
- `offline.html` editorial Vantablack
- Standalone mode CSS (safe-area insets for iOS notch)

### 🛡 법적 방어선 (CONDITIONAL APPROVED)
- `services/legal_filter.py` 74 replacement patterns + 6 prohibited patterns
- `ai_service.py` system prompt FORBIDDEN vocabulary (한/영)
- `_compliance_filter()` + `scrub_response()` 3-layer gate
- **UI 13/13 DisclaimerBanner** + **PDF 18/18 _disclaimer.html**
- KIS buy/sell/place_order disabled, Alpaca `paper=True` 하드코딩
- POSITIVE/NEGATIVE/NEUTRAL signal 라벨만 (BUY/SELL/HOLD 0)
- 회원가입 3 필수 + 1 선택 동의
- `/pricing` ConsentModal (금소법 §19 + 전자상거래법 §22의2)
- 14일 환불 명시
- **privacy-ko.md DPO 섹션** (PIPA §31) + **국외이전 표** (Stripe/Anthropic/Railway/Vercel/Google/Kakao)

### 🔔 Notifications
- `services/alert.py`: `check_52w_highs_lows()` + `check_concentration_alerts()` + 24h/12h dedup
- `scripts/check_price_alerts.py` (cron driver, executable)
- NotificationDropdown 60s refresh + badge + mark-all-as-read
- 7 kinds: price_52w_high/low, concentration_alert, macro_event, artifact_ready, account_sync, watchlist_event

### 🎭 Editorial 디테일
- 신규 공용: `components/ui/editorial.tsx` (Fleuron / RuledKicker / DeckLine / Caption / NumDisplay / FootSignature)
- `globals.css`: .pq-ink-* 유틸 264+ 라인 (card / kicker / num / table / pill / btn / tabs / input / empty)
- Typography: small-caps kickers (font-variant-caps), ss01 stylistic set, lining tabular figures
- Buttons: -0.5px hover lift + Bronze glow (primary), underline slide (ghost)
- Cards: hairline brighten + 0.5px lift hover
- Table rows: 2px Bronze inset + tint hover
- A11y: 전역 focus-visible Bronze outline, reduced-motion aware
- Scrollbar: 서브틀 ink + Bronze hover
- **Italic 절제**: 페이지당 H1 1개 + deck 1개 + pull-quote 만 italic 유지 (~100 instances 제거)

### 🧹 Dead Code 정리
- Round 1: 16 파일 + 110 CSS 라인
- Round 2: price-color.ts + hooks.ts 3개 + CSS 28 라인
- Round 3 (italic 정리 중 추가): editorial.tsx DeckLine/Caption refactor
- 총: ~44 파일 / ~400 CSS 라인 삭제

### 🚨 에러 / SEO
- `not-found.tsx` / `error.tsx` / `global-error.tsx` / `loading.tsx` — Vantablack editorial
- `sitemap.ts` + `robots.ts` (auth + dashboard 크롤 금지)
- layout metadata: canonical / OG / twitter / googleBot / apple-touch-icon / manifest
- 모바일 반응형 5 fix + 6 헤더 responsive size

---

## 🔴 다음 세션 최우선 P0

### 1. CEO 외부 작업 (Claude 못 함)
| # | 작업 | 소요 |
|---|---|---|
| A | **금감원 유사투자자문업 신고** — 유료 런칭 전 필수 (무료 베타는 OK) | 1시간 + 2-4주 대기 |
| B | 사업자등록 (홈택스) | 15분 |
| C | 통신판매업 신고 (민원24) | 20분 |
| D | Google OAuth redirect URI 등록: `https://pivoxquant.com/api/auth/google/callback` | 5분 |
| E | Kakao Developers redirect URI 등록 | 5분 |
| F | **Stripe Product 2개 생성** (Pro 9,900 / Premium 19,900) + API Keys + Webhook Secret → Railway env | 30분 |
| G | Gmail 앱 비번 (myaccount.google.com/apppasswords) → Railway env | 5분 |
| H | Naver Developers API 키 (Search) | 10분 |
| I | DART API 키 (선택) | 10분 |
| J | 변호사 검토 (terms-ko / privacy-ko / LegalConsentModal) 3-5시간 ~100만 원 | 외부 |

### 2. Claude 처리 가능 (다음 세션 실행)

**품질 검증**:
- [ ] **실 OAuth 로그인 E2E 테스트** (Google + Kakao) — CEO 가 D/E 완료 후
- [ ] **Stripe test mode 결제 flow E2E** — CEO F 완료 후
- [ ] **KIS 실 계정 sync** (XXXXXXXX-01) — 실제 포지션 표시 확인
- [ ] **Realtime SSE 실 테스트** — 장중 실 price push 체감 검증
- [ ] **Lighthouse 점수 측정** (FCP < 1.8s, LCP < 2.5s 목표)
- [ ] **모바일 반응형 실 디바이스 검증** (iPhone / Android)
- [ ] **Chrome MCP 으로 주요 user flow 자동 테스트**

**추가 기능**:
- [ ] APScheduler / Railway cron 에 `check_price_alerts.py` 등록 (15min price + daily concentration)
- [ ] Web Push VAPID key 발급 + 실 발송 테스트
- [ ] AI Chat 대화 persistence (DB 저장)
- [ ] Onboarding tutorial overlay (신규 유저 첫 경험)
- [ ] 한글 i18n (랜딩 KR 버전, 선택)
- [ ] `/growth` 페이지 tier progression badges 추가 (선택)

### 3. PDF 디자인 (사용자 직접 손볼 예정)
- "나중에 다시 손볼 꺼임" — 현 18 PDF Goldman IC v2 baseline 유지
- 디자인 기준 변경 시 `services/artifacts/templates/*.html` 수정 후 `python3 scripts/render_artifact_samples.py` 재렌더

---

## 📁 주요 파일 위치

### PDF 시스템
- `services/artifacts/templates/*.html` — 18 PDF 템플릿
- `services/artifacts/templates/_brand_mark.html` (wordmark/monogram)
- `services/artifacts/templates/_report_css.html` (공용 스타일, 1725 lines)
- `services/artifacts/templates/_disclaimer.html` (verbatim legal)
- `services/artifacts/templates/_embedded_fonts.html` (base64)
- `services/artifacts/assets/fonts/*.woff2` (Playfair/EBGaramond/SourceSerif/Geist/JBM)
- `services/artifacts/sample_data.py` (모든 sample_*() 함수)
- `scripts/render_artifact_samples.py` (렌더 엔트리)
- `samples/pdf/*.pdf` (소스 PDF)
- `frontend/public/samples/*.pdf` (18 PDF 공개)

### Dashboard
- `frontend/src/components/layout/dashboard-layout.tsx` — full-screen ink shell
- `frontend/src/components/layout/terminal-sidebar.tsx` — 13 items
- `frontend/src/components/layout/top-bar.tsx` — Search/Bell/Profile
- `frontend/src/app/(dashboard)/*/page.tsx` — 11 페이지
- `frontend/src/components/ui/editorial.tsx` — 공용 editorial primitives
- `frontend/src/components/ui/price-with-timestamp.tsx`
- `frontend/src/components/ui/disclaimer-banner.tsx` (dark theme 지원)
- `frontend/src/components/charts/interactive-line-chart.tsx`

### 실시간
- `services/price_overlay.py`
- `services/cache_ttl.py`
- `services/alert.py` (check_52w, check_concentration)
- `routes/realtime.py` (SSE 5s/30s)
- `frontend/src/lib/market-hours.ts`

### 법적
- `services/legal_filter.py` (74 patterns)
- `services/artifacts/templates/_disclaimer.html`
- `ai_service.py` (SYSTEM_PROMPT FORBIDDEN)
- `kis_service.py` (buy/sell/_place disabled)
- `frontend/src/content/terms-ko.md` + `privacy-ko.md`
- `frontend/src/components/ui/disclaimer-banner.tsx`
- `frontend/src/components/ui/legal-consent-modal.tsx`
- `frontend/src/app/pricing/page.tsx` (ConsentModal)

---

## 📊 최종 상태 서머리

### ✅ 완성
- 18 PDF Goldman IC v2 (~870KB avg, 6p)
- 랜딩 AIDA funnel + Pricing KRW + PDF marketing gating
- /pricing 싱크 + FAQ + Consent
- 11 Dashboard 페이지 + 32 backend endpoints + 실 SWR
- TerminalSidebar + TopBar + Vantablack ink
- 실시간 market-aware refresh (FMP 5s / SSE 5s)
- PriceWithTimestamp + Interactive chart hover
- PWA (manifest + SW + offline + push + install prompt)
- KIS (read-only) + Alpaca (paper only) 브로커 UI
- 법적 방어선 (legal_filter + DisclaimerBanner 13/13 + PDF 18/18 + DPO + 국외이전)
- Error pages + SEO + robots + sitemap
- /admin + /docs + /settings/profile
- Italic 절제 + Editorial primitives + globals.css polish
- Dead code 44+ 파일 제거
- Commit chain 9개 push 완료

### ⏳ CEO 외부 작업 대기
- 사업자/통판/유사투자자문업 신고
- OAuth redirect URI 등록 확인
- API 키 (Naver/DART/Gmail SMTP)
- Stripe Product + keys
- 변호사 검토

### 🔄 다음 세션 TODO (우선순위)
1. **OAuth 통과 후 실 로그인 E2E** — 대시보드 실 데이터 검증
2. **Stripe test mode 결제 flow**
3. **KIS 실 계정 sync** (XXXXXXXX-01)
4. **Lighthouse 측정 + 최적화**
5. **Railway cron 등록** (check_price_alerts 15min/daily)
6. **Realtime SSE 실 테스트** (장중)
7. **모바일 실 디바이스 QA**
8. **Web Push 실 발송**
9. **AI Chat persistence**

---

## 🛠 다음 세션 시작 가이드

### 1. 먼저 확인할 상태
```bash
cd /Users/seanbae/Desktop/취준/stockpilot
git log --oneline -10    # 최신 커밋 확인
git status               # working tree clean
cd frontend && npm run build && cd ..
python3 run.py &         # 백엔드 기동 테스트
curl -s http://localhost:5050/api/health
```

### 2. CEO 외부 작업 완료 여부 점검
- Google/Kakao OAuth callback URL 등록됨?
- Railway env 에 GOOGLE_CLIENT_ID / KAKAO_CLIENT_ID / STRIPE_SECRET_KEY / GMAIL_APP_PASSWORD 설정됨?
- Stripe Dashboard 에 Pro ₩9,900 / Premium ₩19,900 Product 생성됨?

### 3. 우선순위 따라 처리
- CEO 외부 작업 완료 → E2E 테스트 (Agent: user-tester + Claude in Chrome MCP)
- 미완 → 내부 개발 작업 (Agent: frontend-dev / backend-dev / performance)

### 4. 리소스 규칙 (이번 세션 학습)
- **동시 Agent 3-4개 병렬 허용** (CEO 승인 — 이번 세션에서 컴 안정 확인됨)
- 각 agent 스코프 작게 (25분 타임박스 이내)
- 공용 파일 (globals.css / dashboard-layout / endpoints.ts) 은 한 agent 만 수정
- 파일 경계 엄격 분리 — merge conflict 방지

---

## 🎯 다음 세션 시작 프롬프트

```
HANDOVER.md 읽고 이어서.

**먼저 CEO 외부 작업 상태 체크**:
- [ ] Google/Kakao OAuth redirect URI 등록 완료?
- [ ] Stripe Product + Keys 완료?
- [ ] Railway env 설정 완료?

**완료 시 우선순위**:
1. 실 OAuth 로그인 E2E → 대시보드 실 데이터 렌더 검증
2. Stripe test mode 결제 flow
3. KIS 실 계정 sync (XXXXXXXX-01)
4. Lighthouse 측정 + 최적화
5. Realtime SSE 실 테스트 (장중 시간)

**미완 시**:
6. Railway cron 등록 (check_price_alerts.py)
7. Web Push VAPID + 실 발송
8. AI Chat 대화 DB persistence
9. 모바일 실 디바이스 QA
10. (선택) 랜딩 한글 i18n / Growth tier badges / Onboarding tutorial

**사용자 이미 언급**:
- PDF 디자인은 직접 손볼 예정 (건드리지 말 것)
- 변호사 검토는 CEO 영역

**리소스 규칙**:
- 동시 Agent 3-4개 병렬 허용
- 각 스코프 25분 타임박스
- 공용 파일은 1 agent 만 수정
```

---

**작성**: 2026-04-22 (세션 종료)
**이전 버전**: 2026-04-21 v3 (archived)
**최신 commit**: `2914467`
**프로덕션**: https://pivoxquant.com (베타 비번: `***REDACTED***`)
**GitHub**: https://github.com/seanbae-analyst/pivoxquant
