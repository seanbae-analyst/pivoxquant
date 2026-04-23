# PivoxQuant — 인수인계서 (2026-04-23 세션 종료 · v3)

## 🎯 이번 세션 핵심 성과 (30+ 커밋)

**Commit chain (2026-04-23)**: `e0bcd38 → 6bb81ab` (총 30커밋 배포)

### 1. Dossier 유니버스 완성 (5 페이지)
- `/home` "This morning." 3-paper stack ([9ac0720](https://github.com/seanbae-analyst/pivoxquant/commit/9ac0720))
- `/portfolio` "Ledger Binder" ([d348d0f](https://github.com/seanbae-analyst/pivoxquant/commit/d348d0f))
- `/market` "Morning Papers" US/KR 탭 ([ef95f43](https://github.com/seanbae-analyst/pivoxquant/commit/ef95f43))
- `/signals` "Clip Board" 3 clipboards ([663247f](https://github.com/seanbae-analyst/pivoxquant/commit/663247f))
- `/detail/[ticker]` Goldman IC editorial (전 세션 66ee6e4)

### 2. 랜딩 전면 재구성
- **Splash Page 0** — Vantablack + "PIVOXQUANT" 상단 헤더 정자 폰트 ([c2abe7a](https://github.com/seanbae-analyst/pivoxquant/commit/c2abe7a))
- **Hero v3 cinematic** — market ticker + CFO glow + 3D flip deck (전 세션 fd1a2fb)
- **FlipLandingShell 제거 → 네이티브 스무스 스크롤** + 섹션 재배치 (features 위로) ([c66373c](https://github.com/seanbae-analyst/pivoxquant/commit/c66373c))
- **FAQ 신설** (4 item accordion, 금소법 §19 + 14일 환불)
- Pricing 티어 seals I/II/III bronze disc

### 3. 대시보드 Italic 전면 제거 ([6bb81ab](https://github.com/seanbae-analyst/pivoxquant/commit/6bb81ab))
- 로그인 후 보이는 모든 페이지에서 italic 제거 (25 파일)
- 랜딩 Hero / Splash / disclaimer 는 유지 (editorial 톤)

### 4. Bug Sweep 12건 전원 fix
bug-hunter agent → P0×2 / P1×6 / P2×4 발견, **12/12 전수 배포**:
- P0: AI Chat raw 에러 누출 / Discover 2024 mock
- P1: Sector FX / KOSDAQ `₩1,` truncate / BRK-B chart / ABTC price / Risk demo / KR 52W
- P2: 모달 흰배경 / Samsung UNKNOWN sector / CountUp $0 / ticker SPY truncate

### 5. Backend Wave 2 hardening
- Risk API 500 → 200 demo fallback + staged diagnostics ([307de11](https://github.com/seanbae-analyst/pivoxquant/commit/307de11))
- SSE 포트폴리오 스트림 12회→1회 루프 해결
- Portfolio `/api/portfolio` 17s → 1.8s (-89%)
- Chart `/api/chart/<ticker>` 12s → 1.2s (-90%)
- FMP null-cache bust (NVDA/MSFT/TSLA P/E EPS 재시도)
- KR fundamentals via KIS `inquire-price` ([0921dcb](https://github.com/seanbae-analyst/pivoxquant/commit/0921dcb))
- Alpha Vantage OVERVIEW fallback **코드 레디** (key 대기) ([561036f](https://github.com/seanbae-analyst/pivoxquant/commit/561036f))
- KIS 지수 일봉 fallback (KOSPI/KOSDAQ 52W + sparkline) ([74ca14e](https://github.com/seanbae-analyst/pivoxquant/commit/74ca14e))
- BRK-B 클래스 주 티커 정규화 ([06f2191](https://github.com/seanbae-analyst/pivoxquant/commit/06f2191))
- KRW/USD 통화 분기 (sector + ledger)

### 6. 법적 방어선 강화
- `legal_filter.py` 80 → 89 regex (EN advisory verbs 9개 추가)
- `alert_service.py` scrub 적용 (`Consider reducing 50%` → `indicator change observed`)
- Portfolio aria-label `Buy more` / `Sell` → `Record additional buy / sale`
- `brag_card_email.html` disclaimer 강화 (매수·매도 권유 부정 명시)
- AI Chat exception `str(e)` 제거 (request_id / credit balance 누출 방지)
- `/discover` 2024 mock fallback 제거 (시세 오표시 법적 리스크)

### 7. 자동 운영 시스템 (Tier A+B+C 3-layer)
- **Tier A — GitHub Actions** (laptop off 에서도): api-health 15분 / legal-guard PR 게이트 / post-deploy canary (전 세션 4d0fa6b)
- **Tier B — Railway Cron**: (설정 대기)
- **Tier C — Claude Scheduled Tasks** (MacBook 열림 시): api-sentinel 47분 / bug-hunter-daily 03:37 / legal-guard 06:42 KST
- `~/.claude/.../memory/autopilot_log.md` 누적

### 8. 코드 정리
- 미사용 shadcn 컴포넌트 3개 삭제 (bb4fd61)
- ruff F401/F841 autofix 45+ 파일
- Orphan mock constants 제거
- 총 ~700 line 삭제

### 9. LEGAL_CONSULT_PACKAGE.md (537줄)
로펌 변호사에게 직접 들고 갈 자문 요청서 — §1.1~§1.15 질문 + 증거 파일 목록 + 비용/일정 + CEO 사전 준비 체크리스트

---

## 🚧 다음 세션 TODO (우선순위)

### 🔴 P0 CEO 외부 (1시간 이내)
1. Railway env **`NAVER_CLIENT_ID` + `NAVER_CLIENT_SECRET`** → 한국주식 뉴스 살아남 (**네 말로는 기존 키 있음**)
2. Railway env **`KIS_USE_REAL=1`** → 한국주식 P/E + EPS 살아남 (삼성/네이버/카카오)
3. Railway env **`ALPHAVANTAGE_API_KEY`** ([무료 2분 발급](https://www.alphavantage.co/support/#api-key)) → NVDA/MSFT/TSLA P/E + EPS

### 🟠 P1 CEO 외부 (반나절)
4. Google OAuth redirect URI: `https://pivoxquant.com/api/auth/google/callback`
5. Kakao OAuth redirect URI: `https://pivoxquant.com/api/auth/kakao/callback`
6. 로펌 약속 잡기 → `LEGAL_CONSULT_PACKAGE.md` 지참 (100~300만원)
7. 사업자등록 (홈택스) 15분
8. 통신판매업 신고 (민원24) 20분
9. PivoxQuant 상표 유사상표 검색 (키프리스)

### 🟠 P1 CEO 외부 (유료 출시 전)
10. Stripe Product 2개 (Pro 9,900 / Premium 19,900) + Keys + Webhook → Railway env
11. 유사투자자문업 신고 (금감원, 로펌 조언 후) — 수리 2~4주
12. 변호사 검토 완료 → `privacy-ko.md` "변호사 검토 대기 중" 문구 제거
13. terms-ko.md 변호사 검수 반영

### 🟡 P1 내가 할 수 있는 것 (CEO 시키면)
14. **실시간 SSE 장중 실측** (네 장중 시간에)
15. Chrome MCP 전 플로우 자동 E2E (로그인→온보딩→홈→CRUD→AI→로그아웃)
16. bug-hunter 검증 못 한 것:
    - NVDA/TSLA/SMCI/035720.KS/068270.KS detail
    - Portfolio Buy/Sell/Edit modal 실 저장
    - Autotrade Kill Switch 토글
    - 검색 Cmd+K 자동완성
    - /morning-brief cross-asset
17. Lighthouse 측정 + LCP/CLS 최적화
18. 모바일 375px 실기기 QA

### 🟢 P2 내가 할 수 있는 것 (랜딩 후반)
19. Feature Explorer 에 **sticky-scrub 실제 적용** (helper 준비됨: `sticky-scrub-section.tsx`)
20. **ParallaxLayer 활성화** (준비됨, 미연결)
21. 섹션 fade-up stagger 강화
22. Hero 3D flip deck 타이밍 재조정
23. Pricing 카드 fan-out 3D on scroll

### 🟢 P2 내가 할 수 있는 것 (기능 추가)
24. Railway cron 에 `check_price_alerts.py` 등록 (15분 주기)
25. Web Push VAPID key 발급 + 실 발송
26. AI Chat 대화 DB persistence
27. Onboarding tutorial overlay
28. 한글 i18n 랜딩 (선택)

### 🔵 P3 (성능/품질 보강)
29. Sentry 연결 실 에러 수집
30. FMP 24h cache 자동 refresh (Railway restart 불필요화)
31. 모든 라우트 `@legal_scrub_response` 강제 (신규 라우트 빠짐 방지)
32. `tests/test_legal_filter.py` 확장
33. bug-hunter 의 관찰 중 자동 재검증

---

## 🛡 법적 방어선 현황

| 항목 | 상태 |
|---|---|
| DisclaimerBanner | 13/13 대시보드 페이지 ✅ |
| PDF `_disclaimer.html` | 18/18 리포트 + email 1건 (inline, 강화됨) |
| `legal_filter.py` | **89 regex** (base 74+6 → 89) ✅ 확장 |
| AI Chat exception 누출 | 제거됨 (request_id / credit balance) ✅ |
| KIS 주문 | 비활성 유지 (read-only) ✅ |
| Alpaca `paper=True` | 하드코딩 유지 ✅ |
| Signal 라벨 | POSITIVE/NEGATIVE/NEUTRAL 만 ✅ |
| ConsentModal (금소법 §19) | 유지 ✅ |
| 회원가입 3 필수 + 1 선택 | 유지 ✅ |
| PIPA §31 DPO | 유지 (Draft 문구 잔존 — 변호사 검토 후 제거) |
| 국외이전 표 (Stripe/Anthropic/Railway/Vercel/Google/Kakao) | 유지 ✅ |
| `/discover` 2024 mock 노출 | 제거됨 ✅ (자본시장법 misrepresentation 리스크 해제) |

---

## 📁 주요 파일 위치

### Dossier 신규
- `frontend/src/components/home/{dossier-desk,paper-document,this-morning-paper,positions-ledger-paper,signal-paper}.tsx`
- `frontend/src/components/portfolio/{ledger-book-paper,sector-paper,activity-paper}.tsx`
- `frontend/src/components/market/{overview-paper,indices-detail-paper,calendar-news-paper}.tsx`
- `frontend/src/components/signals/{clipboard-paper,signal-memo-strip}.tsx`
- `frontend/src/components/ui/{count-up,tick-number}.tsx`

### Landing
- `frontend/src/components/landing/splash-page.tsx` — PIVOXQUANT 정자 워드마크
- `frontend/src/components/landing/hero.tsx` — Hero v3 cinematic
- `frontend/src/components/landing/landing-page.tsx` — 3927 line, 14 PAGE 섹션 linear scroll
- `frontend/src/components/landing/market-ticker.tsx` — Hero 상단 live ticker
- `frontend/src/components/landing/report-flip-deck.tsx` — Hero 우측 3D PDF 넘김

### Landing Opt-in (미연결, 준비만 됨)
- `frontend/src/components/landing/sticky-scrub-section.tsx`
- `frontend/src/components/landing/parallax-layer.tsx`
- `frontend/src/components/landing/fade-up.tsx`
- `frontend/src/components/landing/flip-landing-shell.tsx` (dead)
- `frontend/src/components/landing/flip-page.tsx` (dead)

### Backend
- `services/data/alpha_vantage_fundamentals.py` — 신규 (AV fallback, key 대기)
- `services/data/kr_fundamentals.py` — KIS inquire-price (KIS_USE_REAL=1 대기)
- `fmp_service.py` — null-cache bust + AV routing + KR routing
- `routes/risk.py` — try/except + staged logging + honest zeros
- `routes/market.py` — ETF proxy + KIS index daily chart + 'Unknown' sector fix
- `services/legal_filter.py` — 89 regex
- `services/alert_service.py` — safe_scrub applied

### 문서
- **`HANDOVER.md`** — 이 파일 (세션별 인수인계)
- **`LEGAL_CONSULT_PACKAGE.md`** (537줄) — 로펌 자문 요청서
- **`BUG_SWEEP_2026-04-23.md`** — 12건 버그 리포트 (이번 세션 전수 fix 됨)
- `~/.claude/projects/-Users-seanbae-Desktop---/memory/autopilot_log.md` — 자동 운영 로그
- `~/.claude/projects/-Users-seanbae-Desktop---/memory/MEMORY.md` — 프로젝트 지식 인덱스

---

## 🎨 디자인 방향 현황

### 확정
- **Vantablack #050505 + Bronze ~#B8956A + Ivory #F5F0E8** 팔레트 고정
- Goldman IC editorial 톤 (Playfair Display + Source Serif 4 + JetBrains Mono)
- Dossier 컨셉 (종이 문서 다발 3D perspective)
- 랜딩: Revolut + Apple 혼합 (네이티브 스크롤, features 위로)
- 대시보드: italic 전면 제거 (정자)

### 네 피드백 (이번 세션 수집)
- 3D flip 방식 "너무 과함" → 네이티브 스크롤로 변경 ✅
- Splash "PIVOXQUANT 정자 + 또렷" 요청 → 반영 ✅
- "남들 대시보드 같다" → Dossier 컨셉 도입 ✅
- "기능이 망가지면 안 됨" → Phase-5 체크리스트 강화 ✅
- "법적 리스크 항상 지키기" → legal_filter regex +9, commit 마다 grep ✅

### 네가 고민 중인 것
- 스크롤 넘김 UX (Apple vs Revolut vs 3D vs 네이티브) — 현재 네이티브 smooth scroll, 피드백 대기
- 랜딩 후속 폴리시 (sticky-scrub, parallax) — helper 준비 완료, 네 OK 시 활성화

---

## 🔧 기술 결정 (세션 중 확정)

- **Three.js / Spline 도입 보류** — 번들 +250~500KB 부담 vs motion/react CSS 3D 로 80% 재현 가능
- **Alpha Vantage OVERVIEW** 을 FMP fundamental 대체로 채택 (무료 tier 25/day 커버)
- **KIS inquire-price** 를 KR fundamental 소스로 채택 (pyKRX 는 법적 회색이라 제외)
- **FlipLandingShell 제거** — wheel hijack UX 불만 발생
- **섹션 순서**: Splash → Hero → Features → Feature Explorer → Engine → Sample Reports → … (Revolut 패턴)

---

## 🚨 알려진 한계

1. **NVDA/MSFT/TSLA P/E null** — AV key 대기 중
2. **KR fundamentals null** — KIS_USE_REAL=1 대기 중
3. **한국주식 뉴스 빈 배열** — Naver keys 대기 중
4. **`/risk` demo fallback** 여전히 가능 — 프로덕션 Railway 로그에서 실패 stage 확인 후 pinpoint fix (진단 로그 이미 배포됨 `stage=`)
5. **BRK-B chart** — FMP/Alpaca 정규화 배포됨, 실제 성공 여부 검증 필요
6. **모바일 실기기 QA** — 미검증
7. **Lighthouse 측정** — 미측정

---

## 📊 최종 상태

- **30개 커밋 이번 세션 배포** (c2abe7a 전 ~30 + 후 수)
- **Build**: 0 TS errors, 42 pages, Python syntax OK
- **Prod**: https://pivoxquant.com (베타 비번 `***REDACTED***`, 최초 1회)
- **GitHub Actions Autopilot**: 15분 주기 health + PR legal guard + post-deploy canary 활성
- **법적 방어선**: CONDITIONAL APPROVED 유지 + P0 AI 에러 누출 / 2024 mock 제거 → **강화**

---

## 🎯 다음 세션 시작 프롬프트

```
HANDOVER.md 읽고 이어서.

1. CEO 외부 env 진행 상태 (Naver / KIS_USE_REAL / AV / OAuth / Stripe)
2. 완료된 env 있으면 → 해당 기능 실측 검증 (한국주식 뉴스 / P/E / 로그인 E2E / 결제 test)
3. 미완이면 내가 할 수 있는 범위:
   - 랜딩 sticky-scrub + parallax 활성화
   - Lighthouse 측정 + 최적화
   - 모바일 375px QA
   - /risk 프로덕션 로그 분석 후 pinpoint fix
   - bug-hunter 재돌림 (회귀 검증)
```

---

**작성**: 2026-04-23 (세션 종료)
**이전 버전**: 2026-04-22 v2 (archived in HANDOVER.md 하단)
**최신 commit**: `6bb81ab`
**프로덕션**: https://pivoxquant.com (베타 비번: `***REDACTED***`)
**GitHub**: https://github.com/seanbae-analyst/pivoxquant
