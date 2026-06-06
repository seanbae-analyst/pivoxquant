# Overnight Bug Hunt — 2026-06-07 (autonomous)

> CEO 지시: "자율모드로 버그 다잡고 모든 가능한 케이스들 다 확인해라 … 구조잡고 나자러가게"
> 방식: baseline 고정 → 7개 정적 헌터 병렬 (browser 불가 — CEO 세션 부재) → **lead 실측 재검증**
> (v58 교훈: verify 못 하는 agent 의 false-positive 차단) → 안전·비동결 버그만 fix+test+배포검증,
> 동결/머니매스/판단필요는 **패치까지 작성해 문서화**.

> 🔴 **2026-06-07 CEO 정정 (필독)**: "통화합산하지말라고 그냥 krw usd 냅두라고 몇번말하노". **KRW·USD 는
> 절대 합산·FX환산 금지 — 항상 따로.** 아래 LANE 1(통화) finding 들이 제안한 **"FX-convert" 권고는 전부 철회**.
> raw KRW+USD 분리는 **버그가 아니라 의도된 설계**. 정답은 언제나 "따로 분리"(통화별 버킷), 절대 "환산해서 합치기"가
> 아님. SoT: `DECISIONS.md` "통화 표시/집계" + `feedback_currency_separate`. 예외=양도세 export 만.
> ※ 커밋 `ec1752c9` 의 fix 3건(KOSDAQ/백테스터/로그아웃)은 통화 합산·환산 코드 **0줄** — 무관.

## 게이트 상태 (실측)
| 게이트 | baseline | fix 후 |
|---|---|---|
| pytest (full) | 3811 passed / 0 fail (13m) | 신규 7 test green + 타겟 회귀 green (아래) |
| frontend tsc | exit 0 | **exit 0** |
| frontend vitest | 541 passed | **541 passed** |
| frontend build | exit 0 | (변경 없음 — auth.tsx만, vitest+tsc 커버) |
| import smoke | — | **IMPORT OK** (순환참조 없음) |

베타게이트 유지. **push/배포 안 함** (CEO 검토용 커밋만 — 아래 "배포 결정" 참조).

---

## ✅ TIER A — FIXED tonight (검증 완료, 안전·비동결)

### A1. KOSDAQ 종목 잘못된 거래소 라우팅 (LANE 6 BUG-2) — P1, 데이터 정합성
- **증상**: `/api/lookup/<6자리>` 가 모든 바 6자리 코드에 `.KS` 를 무조건 붙임. KOSDAQ 종목
  (035760 CJ ENM, 293490 카카오게임즈, 247540 에코프로비엠 …)이 KOSPI(.KS)로 조회됨 →
  **다른 종목 가격이 반환되거나 데이터 없음**. prod curl 로 재현 확정 (`035760` → `035760.KS`).
- **근본원인**: [services/data/fetcher.py:321](services/data/fetcher.py) `ticker = ticker + ".KS"` 하드코딩.
  `normalize_ticker()` 는 KR 레지스트리 기반으로 `.KQ`/`.KS` 정확 분기함(실측: 035760→.KQ, 005930→.KS).
- **fix**: `quick_lookup` 6자리 분기를 `normalize_ticker(ticker)` 로 교체 + import 추가. 미등록 코드는
  기존대로 `.KS` fallback (회귀 없음).
- **test**: `tests/test_kosdaq_quick_lookup_routing.py` (3 test) — KOSDAQ→.KQ 라우팅 + 하드코딩 .KS 재발 가드.

### A2. Backtester 0-가격 바(KR 거래정지일) 나눗셈 가드 (LANE 5 F3/F4/F5)
- **증상**: KR 거래정지일은 종가 0.0 행으로 들어옴. 가드 없는 나눗셈이 (a) Python float `x/0.0` →
  ZeroDivisionError → 외곽 try/except 가 **백테스트 전체를 None 으로 무음 붕괴**, (b) numpy 경로는
  inf/NaN → 무효 JSON.
  - F4 `closes[bh_start]` (buy_hold_return/alpha/alpha_gross) — [backtester.py:421](services/quant/backtester.py)
  - F3 `closes[-20]` (KR mom20 점수) — [backtester.py:599](services/quant/backtester.py)
  - F5 `pv_arr[:-1]` (일별수익률→Sharpe/Sortino) — [backtester.py:471](services/quant/backtester.py)
- **fix**: 각 분모 `!= 0` 가드 + `np.isfinite()` 필터(F5). 수식 불변 — 0/비유한 입력에서만 동작(no-op on 정상).
  ※ backtester.py 는 hard_frozen 7파일 **아님**(frozen_files.yaml 실측). CLAUDE.md "신중수정+회귀테스트" 준수.
- **test**: `tests/test_backtester_zero_price_guard.py` (4 test) — 정상 시리즈 불변(회귀) + 0-바 inf/crash 무발생 +
  3 가드 소스 존재 락.

### A3. 로그아웃 시 SWR 인메모리 캐시 미삭제 → 공용기기 cross-user 노출 (LANE 7 FINDING-5) — P1, 프라이버시
- **증상**: 로그아웃이 `auth.me` 키만 mutate + SW HTTP 캐시만 clear. **SWR 인메모리 store(portfolio/
  watchlist/signals/risk 등 per-user 키)는 잔존**. OAuth 계정전환은 full reload 없음 → 같은 기기에서
  유저 B 가 첫 페인트에 유저 A 데이터를 볼 수 있음.
- **근본원인**: [frontend/src/lib/auth.tsx](frontend/src/lib/auth.tsx) logout — bound `mutate` 는 단일 키만 evict.
- **fix**: `useSWRConfig().mutate((key)=>key!==API.auth.me, undefined, {revalidate:false})` 로 그 외 전 키 evict.
  SWR 키 변경 없음(CLAUDE.md 준수) — clear 만 추가. tsc+vitest green.

---

## 🟠 TIER B — CEO 결정 필요 (패치 작성 완료, 자율 적용 안 함)

### B1. 🔴 동결 퀀트 파일 crash 버그 4건 (LANE 5) — Iron Rule §1 → CEO 승인 필요
frozen_files.yaml hard_frozen. numerical-guard 는 현 exception(Pattern 6/7/10)에 없음 → **자율 수정 금지**.
모두 KR 거래정지일(0-가격) 또는 flat-series 같은 **degenerate 입력에서만** 발생하나, 실 라우트 도달 가능.
승인 시 아래 1-line 가드(수식 불변) 적용 + 회귀테스트:

| # | 파일:line | 라우트 | 트리거 | 결과 | 제안 가드 |
|---|---|---|---|---|---|
| F1 | `services/quant/models.py:64` StatArb `estimate_ou_params` | `/api/quant/stat-arb` | flat spread → `np.std(x)=0` | NaN → `round(NaN)` ValueError | `if np.std(x)==0: return None` (caller 이미 None 처리) |
| F2 | `services/quant/engine.py:1073` `portfolio_analytics` | `/api/portfolio/analytics` | combined 에 NaN → `cum.cummax()=0` | NaN max_dd | `combined=combined.fillna(0)` 후 cumprod |
| F6 | `services/quant/signals.py:533` `AnchoringBias` | `/api/signals/<t>` | 0-가격 분모(`c[-21:-1]`) | NaN → cache write `allow_nan=False` ValueError(재계산 폭주) | `c=np.where(c==0,np.nan,c)` |
| F11 | `services/quant/risk_metrics.py:58` `GKYZVolatility` | `/api/risk/portfolio` | 0-가격 `np.log(0)` | inf → json.dumps ValueError | `np.maximum(o,1e-8)` 등 (이미 models.py:343/427 패턴 존재) |

추가(저위험, 동결): models.py:277 `range_width/closes[-1]`, models.py:1224 `log(closes[-20:])` 도 동일 0-가격
divide warning (헌트 중 backtester 0-test 가 노출). 동결이라 미적용 — 묶어서 승인 권장.

### B2. 🔴 AI Twin write-path KRW/USD 통화혼재 (LANE 1 F1) — money-math + DB write, LIVE-conditional
- **확정 사실**: `_scheduled_twin_decisions_kr/us` ([app.py:1779,1812](app.py))가 `RUN_SCHEDULER=1`(prod 추정)
  에서 `AITwinPortfolio.is_active=True` 트윈마다 daily 실행. `DISCOVER_POOL`([engine.py:49](services/quant/engine.py))에
  **KR 20종목(.KS) 포함**. twin ledger(`current_cash`)는 **USD 단일**(DEFAULT_STARTING_CASH=$10,000).
- **버그**: KR 매수/매도 시 [twin_runner.py:293-297(sell), 361-372(buy)](services/twin/twin_runner.py)가
  **KRW price 를 USD cash 에 raw 가감** → 활성 트윈이 KR 보유 시 ledger 손상(과거 Pattern-7 +52,281%/700배 사례).
- **노출도**: 활성 트윈 수에 의존. closed beta 라 0~소수일 수 있음(prod DB 조회 불가 — dev-login prod 차단됨).
  **CEO 가 활성 트윈 수 확인 필요** (있으면 즉시, 없으면 출시 전).
- **이전 세션 판단 존중**: v58 이 "money-math+DB write라 신중 fix 필요(추측 금지로 보류)"로 deferred. 동일 유지.
- **⚠️ FX-환산 금지** ([[feedback_currency_separate]] / DECISIONS "통화 표시/집계"): 통화를 환산해 합치는 fix 는
  CEO 지시 위반. 트윈 ledger 는 `current_cash` 단일 USD 구조라 KR 매매 시 KRW 가 USD 에 섞이는 게 문제. 해법은:
  - **(권장) KR 제외**: `_score_universe`/buy 에서 `.KS/.KQ` 후보 제외 → 트윈은 USD 전용. money-math 불변, 필터만.
  - (대안) 통화별 cash 분리(KRW cash / USD cash 따로 추적). 구조변경 → CEO 결정.
  - 둘 다 보류 시 **그대로 둠**(활성 트윈 0 이면 무영향). 어느 쪽이든 **FX-convert 로 합치지 말 것.**

### B3. 🟡 portfolio_analytics / twin_reporter 통화 raw 합산 (LANE 1 F5/F3) — **환산 아님, 분리**
- [routes/portfolio.py:1108](routes/portfolio.py) 이 네이티브 `market_value`(.KS=KRW)를 frozen
  `engine.portfolio_analytics`([engine.py:1040](services/quant/engine.py) `sum()`)에 raw 전달 → 혼합 포트면
  total_value 가 ₩+$ 섞인 무의미 수치. twin_reporter:66-77(mixed TradeHistory raw-sum)도 동류.
- **fix 방향 = FX-convert 아님** ([[feedback_currency_separate]]): 통화는 따로. 올바른 정답 패턴은
  **통화별 버킷 분리** — 이미 [routes/portfolio.py:279-291](routes/portfolio.py)의 `total_usd`/`total_krw`
  분리가 그것. 단일 통합 total 자체를 없애거나 통화별로 따로 내보낼 것. `API.portfolio.analytics` FE 직접 호출
  0건이라 노출도 낮음 → CEO 가 "분리 표시" 원하면 적용, 아니면 보류. **절대 환산해 합치지 말 것.**

---

## 🟡 TIER C — 문서화 (저위험/판단/외부의존)

- **LANE 6 BUG-4 (P? 잠재 misrep)**: 공개 market-snapshot 의 S&P500/Nasdaq 이 **SPY/QQQ ETF 가격**을
  지수값으로 표기(FMP $29 플랜이 `^GSPC` 402). 코드는 `proxy_ticker` 공개([market.py:1589](routes/market.py)).
  **프론트가 "VIA SPY" 디스클로저 칩을 렌더하는지 확인 필요** — 안 하면 표시광고법 오해소지.
- **LANE 6 SUSPECT-3 (billing)**: `/api/billing/cancel`·`/refund` 404(미구현). 전자상거래법 §17 즉시해지.
  billing 게이트(BUSINESS_REGISTRATION_PENDING)로 현재 비활성 → **결제 활성화 전 SHIP-BLOCKER**.
- **LANE 6 SUSPECT-1**: `/api/artifacts/brag-card/og.png` 404 — viral OG 이미지 미배포(allowlist 기재).
- **LANE 7 FINDING-1**: `frontend/.env.production` 의 V2 플래그 5개 `false` (문서상 prod=true와 모순).
  Vercel 대시보드 override 추정(=V2 라이브, CEO 가 V2 작업중이었음) → 동작상 문제 아니나 **footgun**:
  대시보드 var 삭제 시 V1(데모데이터 risk 페이지)로 fallback. 커밋파일을 intent(true)에 맞추는 cleanup 권장.
- **LANE 4 F5 (chat-stream)**: SSE 청크 경계로 금칙어 분할 시 per-chunk scrub 누락. `AI_CHAT_ENABLED=0`
  이라 현재 무surface. chat 활성화 전 sliding-window scrub 필요.
- **LANE 4 F2**: `/api/artifacts/generate` 에 route-level `@legal_scrub_response` 없음(서비스 self-scrub 으로
  완화). 방어심도 — 18 artifact 출력/테스트 perturbation 위험으로 자율 미적용. 결제 전 추가 권장.
- **LANE 4 F1**: NpsWidget "추천"(NPS=Net Promoter, 제품추천 문맥). 변호사 Q: §4⑧ 투자권유 범위 외 확인.
- **LANE 4 F6**: 공개 `/support` 페이지 DisclaimerBanner 미마운트(dashboard 그룹 밖). FAQ 성격이라 저위험.
- **LANE 7 FINDING-6**: `earnings-pre-brief-card.tsx:54` `fmtEps` 가 `$` 하드코딩 → KR 발행사 EPS `$` 표기.
  live 컴포넌트지만 KR EPS 는 보통 null(→"—")이라 저빈도. 통화를 ticker 에서 파생 권장.
- **LANE 7 V1 잔재(FINDING-2/3/4)**: dormant `_v1/` 페이지의 데모 상관행렬·naked .KS — V2 라이브면 무영향.
  FINDING-1 확인 후 V1 제거 시 동시 해소.

---

## ✅ CLEAN 으로 확인된 영역 (positive signal — 증거 기반)
- **LANE 2 캐시 cross-user (Pattern 6)**: 0건. 모든 per-user 캐시 user_id 스코프 확인. earnings_tone/
  risk_summary/SignalCache 선례 회귀 없음(498 hit triage).
- **LANE 3 인증/티어/접근제어**: 0건. IDOR(전 PK lookup 에 ownership assert), tier-gate(통합 dispatch
  `_ARTIFACT_MIN_TIER` 재강제), webhook 서명(Stripe/SendGrid), OAuth state HMAC, dev-login prod 차단,
  cron secret — 전부 hardened 확인.

---

## 배포 결정 (CEO)
TIER A 3건은 검증 완료 — 커밋은 feature 브랜치 `feat/data-storage-trust` 에만 남김(**push/배포 안 함**).
prod 반영하려면: ① TIER A 디프 리뷰 → ② `git push` (Vercel preview) 또는 main 머지(prod) → ③ TIER B
동결 4건 승인 여부 결정(승인 시 패치 즉시 적용 가능).
