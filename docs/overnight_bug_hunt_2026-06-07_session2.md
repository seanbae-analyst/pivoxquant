# Overnight Bug Hunt — 2026-06-07 Session 2 (CEO live, post-onboarding fixes)

> CEO 라이브 사용 중 두 버그 신고 → fix → "자율모드로 밤새 버그헌팅, 모든 케이스, 버그 없게".
> 방법: baseline green 고정 → 병렬 헌터 4 lane(백그라운드) + lead 직접 헌트 → **lead 가 모든 finding 실측
> 재검증**(v58 verify-gap 교훈) → 안전·비동결만 fix, **통화/동결/머니매스/판단은 문서화**(v59 패턴).
> 이전 세션(v59) 의 `docs/overnight_bug_hunt_2026-06-07.md` 와 별개.

---

## PART 1 — 적용·커밋된 fix (검증 완료)

커밋 `64546d4a` (feature 브랜치 `feat/data-storage-trust`, **push 안 함**):

### Fix 1 — 온보딩 broker 스텝 데스크탑 레이아웃 붕괴 (CEO 첫 신고)
- **증상**: `/onboarding/broker` 데스크탑에서 카드 2개가 ~180px 로 찌부 + 헤더 텍스트 단어별 줄바꿈 +
  "한국투자증권" 글자별 세로 + status 뱃지 겹침.
- **근본원인**: `frontend/src/app/(auth)/layout.tsx` 가 **모든** 자식을 `max-w-sm`(384px) 중앙 폼 셸로 감쌌다.
  온보딩 페이지(`/onboarding` 위저드 + `/onboarding/broker`)는 **자체 풀폭 앱셸**(sticky header/footer,
  `max-w-3xl`/`max-w-lg` 컨텐츠)을 가지는데, md+ 뷰포트에서 `md:grid-cols-2` 가 384px 박스 안에서 발동 → 찌부.
- **fix**: 좁은 폼 셸을 `login/layout.tsx` + `signup/layout.tsx` 로 이동. `(auth)/layout.tsx` 는 풀스크린
  ink 배경 passthrough 로만. 온보딩은 풀폭 렌더.
- **검증(실측)**: vw=1024 격리 렌더 → `gridCols=376px 376px`, 카드 2개 376px, 헤더 textDiv=185px,
  뱃지=129px 옆 안착, "한국투자증권" h3 높이=28px(한 줄). 스크린샷 확보. login V2/signup V2(prod-active)는
  `pq-auth-shell` `position:fixed` full-bleed 라 max-w-sm 무시 → **회귀 없음**(브라우저 렌더 + 콘솔 0 에러 확인).

### Fix 2 — 저품질 동전던지기 질문(Q14) 제거 (CEO 둘째 신고 "이딴 질문 퀄리티 뭐냐 빼라")
- 20→19 문항. category C(리스크 심리)는 시나리오 3문항으로 충분 커버.
- 크로스-스택: 프론트 data(질문+slice 인덱스 19→18) / 프론트 프리뷰 scoring(risk 나눗수 5.5→4.5) /
  백엔드 def+C4 scoring(risk 나눗수 4.0→3.0; `loss_aversion_score` 출력은 risk_normalized 에서 파생해
  **출력 스키마 불변** — 소비처 0건이지만 안전제일) / 테스트 fixture 2개.
- **검증**: 백엔드 persona/profile/onboarding 489+27 passed, 프론트 vitest 545 passed, tsc 0.
- **배포 경계 안전**: `step` 항상 0 초기화(answers 만 draft 복원, 질문ID 키) → 옛 20문항 frontend 로 시작한
  유저도 안 깨짐. 백엔드 `submit_onboarding` 은 카운트 검증 없이 legal_confirmations 키만 게이트 → 옛 frontend
  의 coinflip 키 제출도 무시. `isLegalStep`/`isResultScreen`/`currentQuestion` 전부 live 상수 파생.

### Fix 3 (사소) — stale 주석
- `onboarding/page.tsx:27` `// 19 wizard` → `// 18 wizard` (TOTAL_STEPS 은 computed, 런타임 무관).

### Fix 4 — 아티팩트/상세 `$nan`·`+nan%` 방어 (Lane E A1+B2, P1 latent) ✅
- **근본원인**: `_safe_price()` 가 `float(hist["Close"].iloc[-1])` 를 NaN 가드 없이 반환 → 소비자
  `_safe_price(...) or avg_cost` 의 `or` fallback 이 **defeated**(`bool(nan) is True` → `nan or x = nan`).
  NaN 이 totals/weight 오염 → `_money`/`_pct` 가 `(TypeError,ValueError)` 만 잡아 통과 → 유료 PDF 에
  `$nan`/`+nan%` 노출(표시광고법 false-display 리스크). KIS 경로는 0.0 으로 coerce 돼 fallback 정상이라
  **latent**, 단 FMP-EOD 마지막행 null 이면 US 종목에서 발화 가능.
- **fix (소스 가드)**: 7개 함수(`kpi_dashboard`/`monthly_finance`/`quarterly_self_report`/`risk_board`
  ×2(`_safe_price`+`get_current_vix`)/`year_end_letter`/`weekly_memo._ticker_last_price`/
  `portfolio_segment._safe_price_at`)가 non-finite → `None` 반환. 소비자 불변(`None or avg_cost` 정상).
  `import math` 5파일 추가. **B2**: `services/data/fetcher.py` 상세 스냅샷 zero-guard 2곳에 `cur != cur`
  (NaN) 추가 — strictly-additive(유효가격 경로 불변).
- **검증**: py_compile OK / 아티팩트 198 passed / 데이터·fetcher 166 passed / NaN→avg_cost fallback +
  0.0·valid 동작 보존 semantic repro 확인.

---

## PART 2 — 버그헌팅 lane 결과

### ✅ CLEAN (증거 기반)
| Lane | 범위 | 결과 |
|------|------|------|
| 온보딩 회귀 (lead 직접) | slice/카운트 정합, 카테고리 메타, draft step 복원, 백엔드 제출, 정규화 | **CLEAN** — 위 Fix 2 검증 참조 |
| Auth/session/OAuth (agent) | middleware 베타게이트/CSP nonce/matcher, login·signup V1·V2, lib/auth.tsx 로그아웃 캐시 evict, OAuth state HMAC/콜백/session fixation, /login↔/onboarding↔/home 리다이렉트 체인 | **CLEAN** — P0/P1 0건. 리다이렉트 비순환. 로그아웃 cross-user evict 정상 |
| Cache Pattern 6 (agent) | services/ai·data·agents·profile·artifacts·twin 캐시 키 user_id scoping | **CLEAN** — 전 user-specific 캐시 scoped, 커밋 캐시쓰기 0, earnings_tone/risk_summary precedent 유지 |
| 법적 라벨 (lead 직접) | BUY/SELL/HOLD 금지, 추천/조언/AI Coach 금지, 시그널 라벨 SoT | **CLEAN** — "HOLD" 는 "never render" 주석뿐, "recommendation" 은 전부 부정형 디스클레이머, 라벨=POSITIVE/NEGATIVE/NEUTRAL |
| 아티팩트(18종)+데이터 (agent) | 엣지 데이터 크래시 / 0.00·NaN·null / 티어게이팅 / KR 티커 | **대부분 CLEAN** — 티어게이팅(Pro6/Prem9/free3) ✓, 크래시 격리(per-user try/except+rollback) ✓, FX(silent 1.0 없음·fallback 1380·staleness 관측가능) ✓, KR 티커(2,770 엔트리 normalize_ticker 정상) ✓, hardcoded sample 가드 ✓, div-by-zero 가드 ✓. **발견: A1 `$nan`(→Fix 4 적용)**. P2 잔여 아래 |
| 실시간 SSE + PWA (agent) — 2차 wave | SSE cross-user/auth/cleanup/reconnect/app-context, SW 캐시 무효화·per-user·offline, push consent | **CLEAN (P0/P1 0)** — cross-user SSE 누락 0(payload=ticker+price, PII無), 스트림 `@api_auth` ✓, EventSource teardown(abort+timer clear) ✓, reconnect MAX 7+backoff+jitter+visibility-gate ✓, generator app-context capture+`db.session.remove` ✓, SW `NETWORK_ONLY`(auth/ai/realtime/broker) + login·logout `CLEAR_API_CACHE` ✓, offline 2xx만 캐시·`/api/auth/*` network-only ✓, push 14d dismiss+ownership 409 ✓. **gevent monkey-patch 확인**(`time.sleep` SSE 비차단). sw.js 미커밋 = benign(cache-version bump, prebuild가 SHA로 덮어씀). LOW 2건 아래 |
| 대시보드 코어 read 경로 (agent) — 2차 wave | home/market/signals/watchlist/discover/portfolio, 신규 0-position 유저 크래시/500/None-산술/empty-state | **CLEAN (크래시 0)** — **실측 스모크: 신규 empty-book 유저로 29개 코어 read 엔드포인트 → 29/29 `<500`**(FMP kill 최악조건). 빈 포트폴리오 분기가 first-branch 로 의도적 엔지니어링(`{} if tickers else {}`, `sum([])=0`, 모든 나눗셈 `>0` 가드, risk `state is None`→honest zeros, signals no-cache→NEUTRAL placeholder). discover 503 = FMP 불가 시 의도적 fail-fast(mock 금지·프론트 retry-state 처리). FE: ErrorBoundary + 카드별 null-safe + `Array.isArray`/`?? []`/`Number.isFinite`. 392 passed |

### 🟡 P2 문서화 (자율 미적용 — 저영향/cosmetic/도달불가)
- **A2** `capital_allocation`/`portfolio_segment` 포매터·비율 게이트 NaN-fragile — **현재 도달불가**(`_stats_single` 가 `first/last<=0` 선가드). 방어 노트.
- **B1** 매크로 위젯 commodity/DXY/BTC `_safe` 가 NaN→`0` 으로 floor → "Gold $0.00" 가능(KR 지수 sanity-drop 처럼 키별 drop 없음). market-summary 위젯(유저 보유 아님) → P2.
- **B3** `realtime.py:436` KOSDAQ live-quote **표시 라벨**이 `.KS` 하드코딩 — **가격은 정확**(6자리 코드 `"J"` 시장코드로 exchange-agnostic 조회), 라벨만 불일치(registry `get_name` 이 `.KS↔.KQ` 토글로 이름은 해결). cosmetic.
- **PWA #3 (LOW)** `install-prompt.tsx:67-74` 배포 후 auto-reload 가 `controllerchange` 만 의존 + 리스너를 `controller` 동기 스냅샷 안에서만 등록 → `clients.claim()` 가 effect 등록보다 빠르면 열린 탭이 **옛 번들 유지(Cmd+Shift+R 필요)**. 권고 fix: `registration.onupdatefound → installing.statechange==='activated'` 도 청취. **자율 미적용**(SW 라이프사이클 — 오적용 시 reload 루프 위험, 배포 실측 필요 → pwa-cache-validator 로 신중 적용 권장).
- **PWA #4 (LOW, by-design)** `auth.tsx` `CLEAR_API_CACHE` 가 배포 직후 1 nav 동안 옛 SW 로 전달 — benign(새 SW activate 가 non-current 캐시 전부 purge; 신규설치는 누출할 prior-user 캐시 없음). fix 불요.

---

## PART 3 — 🟠 CEO 결정 필요 (자동수정 금지 — 통화 정책)

> **전부 PRE-EXISTING** (커밋 `64546d4a` 무관 — 통화 합산 코드 0줄 변경). 통화 처리는 CEO 전속 결정
> ([[feedback_currency_separate]] — "krw usd 냅두라 몇번말하노"). **절대 FX-환산해 합치지 말 것**;
> 정답 패턴 = 통화별 버킷 분리 or KR 제외. 아래는 **실측 재검증 완료**.

### 기존 known (v59 doc 에 이미 문서화)
- **F3 = B2**: `routes/twin.py:115-116` 트윈 snapshot `market_value += shares*price_now`(native raw mix) →
  혼합 트윈의 total_value/return% 왜곡. 트윈 통화제약 없음(혼합 가능) 확인. (twin_runner write-path = 기존 B2)
- **F4/P1 = B3**: `routes/quant_helpers.py` 중앙 risk 로더 FX-merge → risk_quant 10 엔드포인트 +
  portfolio.py `total_value_all_krw`/`totalNav` 병합 표시. (= 기존 B3 "통화별 버킷 분리" 항목)

### 신규 열거 (기존 set 에 추가 — 같은 클래스)
- **F1 (신규) — `routes/simulate.py:60,68`** `_load_user_positions`: `mv = price*shares`(native) `total += mv`
  raw 혼합. **5개 엔드포인트**(`/simulate/hrp,trp,mdp,erc,min-variance`)의 `current_weights` 분모 + 표시
  `portfolio_value`. 혼합 종목이면 가중치 왜곡(₩70,000 vs $150 단위 혼재) → optimizer 입력·표시 둘 다 오염. **재검증 REAL.**
- **F2 (신규) — `services/artifacts/credit_rating_service.py:302-310,284-299`**: `_positions_mv` raw 합산
  + `_cash_buffer_score` 가 cash 를 `cash_usd if >0 else cash_krw` 임의 선택 후 raw 혼합 total 로 나눔 →
  혼합 유저 cash-buffer 비율 무의미 → credit-rating 아티팩트 점수 오염. **재검증 REAL.**

### P1 FX-merge 세트 (class b — 환산-병합, CEO 룰상 이것도 지양)
`performance_quant.py`(turnover/cost), `twin.py:240-280`(트윈 perf), 아티팩트 14종(kpi_dashboard /
weekly_memo / monthly_finance / portfolio_segment / year_end_letter / quarterly_self_report / risk_board /
monthly_brag / brag_card / dividend_income / burn_rate) — 전부 USD→KRW 환산 후 단일 헤드라인 합산.
**비율(turnover%, cost%, weight)은 base 가 상쇄돼 risk-math 허용**; 절대 금액 표시만 class-b 위반.
→ **방향 결정(통화별 버킷으로 전환 vs 보류) = CEO**. breadth 큼.

**권고**: F1/F2(신규 raw-mix)는 라이브 혼합통화 유저에게 지금 깨진 숫자 노출 → B1~B3 와 함께 CEO 통화-정책
일괄 결정 안건에 포함. 자율 적용 안 함.

---

## PART 4 — 진행 메타
- **baseline GREEN 확정**: vitest 545 ✅ / tsc 0 ✅ / **풀 pytest 3833 passed, 20 skipped, 171 xfailed, 0 failed** ✅.
- fix 후 재검: 아티팩트 198 passed / 데이터·fetcher 166 passed / py_compile OK.
- 커밋: `64546d4a`(fix 1·2·3) + 후속 커밋(Fix 4 = A1/B2 NaN 가드) — feature 브랜치 `feat/data-storage-trust`, **push 안 함**.
- 미적용(의도): 통화 PART 3 전부(CEO 결정), A2·B1·B3(P2 cosmetic/도달불가), oauth-finalize 420→384 clamp(회귀 아님·커밋 전 동일).
