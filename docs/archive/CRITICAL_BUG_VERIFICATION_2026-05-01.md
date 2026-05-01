# PivoxQuant — CRITICAL Bug Verification & Fix Prompts (2026-05-01)

> **목적**: CLAUDE.md(2026-04-14)의 CRITICAL 버그 5건을 Claude Code에 위임해 **실 클릭 검증 + 진짜 깨진 부분만 수정**하기 위한 작업 지시문 모음.
>
> **컨텍스트 발견**: 5개 버그 모두 **코드/페이지는 이미 존재**. HANDOVER.md(2026-05-01)에서도 "코드는 있고 응답코드도 정상이지만 실 클릭/실 동작 미검증"으로 분류. 따라서 이 작업은 **rebuild가 아니라 verify+repair**.

---

## 사용 방법

1. 각 프롬프트는 자기완결적 — Claude Code에 통째로 붙여넣으면 됨.
2. **반드시 한 번에 하나씩** 돌리기. 끝나면 `git diff` 확인 후 다음 진행.
3. 추천 순서: **#2 → #3 → #1 → #4 → #5** (의존성 순).
4. Claude in Chrome MCP가 활성화돼 있어야 실 클릭 검증 가능.
5. 백엔드(port 5050) + 프론트(port 3000)는 사용자가 미리 띄워두기:
   ```bash
   # Terminal 1
   cd /Users/seanbae/Desktop/취준/pivoxquant && python3 run.py
   # Terminal 2
   cd /Users/seanbae/Desktop/취준/pivoxquant/frontend && npm run dev
   ```

---

## 공통 원칙 (모든 프롬프트 적용)

- **자본시장법**: BUY/SELL/HOLD → POSITIVE/NEGATIVE/NEUTRAL. "추천/조언/recommendation/advice" 단어 금지.
- **DisclaimerBanner**: `frontend/src/app/(dashboard)/layout.tsx`에서 단일 마운트 — 페이지에 추가 X.
- **API URL 변경 금지**: `frontend/src/lib/endpoints.ts`와 백엔드 `routes/*.py`는 1:1 매핑. URL 바꾸면 양쪽 동시.
- **수정 금지 파일** (완성 상태): `engine.py`, `quant_models.py`, `risk_defense.py`, `risk_models.py`, `portfolio_models.py`, `signal_models.py`, `ai_models.py`, `autotrader.py`(disabled).
- **mock fallback data 추가 절대 금지** (자본시장법 거짓정보 제공 위반). 데이터 없으면 503 + "data unavailable" 에디토리얼.
- **커밋 컨벤션**: 1 fix = 1 commit. prefix는 각 프롬프트 별 명시(`fix(portfolio):`, `fix(search):` 등).
- **정직 보고**: 작동/미작동 여부와 무엇을 고쳤는지 거짓 없이.

---

## Prompt #1 — Portfolio + Add Position 검증/수정

````
PivoxQuant(/Users/seanbae/Desktop/취준/pivoxquant)의 Portfolio 페이지와 Add Position 플로우를
실 클릭 검증하고, 깨진 부분만 정확히 수정하라.

## 컨텍스트
이전 CEO 테스트(2026-04-14)에서 "Portfolio 페이지 404 + Add Position 모달 없음"으로 보고됐다.
하지만 현재(2026-05-01) 코드 검토 결과 모두 존재:

핵심 파일:
- frontend/src/app/(dashboard)/portfolio/page.tsx        # V1/V2 feature flag 라우터
- frontend/src/app/(dashboard)/portfolio/_v1/page-v1.tsx # 424 lines, 기본
- frontend/src/app/(dashboard)/portfolio/_v2/page-v2.tsx # 갤러리 shell
- frontend/src/components/portfolio/add-position-modal.tsx
- frontend/src/components/portfolio/portfolio-modal.tsx  # 모달 shell
- frontend/src/lib/endpoints.ts:240  # PORTFOLIO_POSITIONS = "/api/portfolio/positions"

백엔드:
- routes/portfolio.py:694  POST /api/portfolio/positions (create_position_alias)
  - Request:  {symbol, side, quantity, price, purchase_date, note}
  - Response: {ok: true, id, symbol, name, isKorean}
  - Free tier cap: 3 positions, 초과 시 403 {error, code:"TIER_LIMIT"}
- routes/portfolio.py:159  POST /api/portfolio/position (legacy add_position)
  - Request:  {ticker, shares, avg_cost, thesis}

V1 flag 기본값: NEXT_PUBLIC_PORTFOLIO_V2 미설정 → V1 렌더.

## 작업 순서

1. 환경 확인:
   - curl http://localhost:5050/api/auth/me → 200/401 확인
   - curl http://localhost:3000/portfolio 가 페이지 HTML 반환하는지

2. Claude in Chrome MCP로 로그인된 세션에서 /portfolio 접속:
   - 페이지 렌더 확인 (V1 dossier UI)
   - 콘솔 에러/경고 capture
   - Network 탭에서 GET /api/portfolio, /api/portfolio/positions, /api/portfolio/summary 응답 확인

3. Add Position 검증:
   - 빈 상태에서 "Add Position" CTA 클릭 → AddPositionModal 열리는지
   - Symbol="AAPL", Quantity=10, Price=200, Side=Long 입력
   - "Add" 버튼 클릭
   - Network 탭에서 POST /api/portfolio/positions 200 응답 + body {ok, id, symbol, name}
   - 모달 닫힘 + sonner toast "Position recorded" + V1 테이블에 신규 행
   - SWR mutate가 PORTFOLIO_POSITIONS 키 재검증하는지

4. Edit/Buy/Sell/Delete 4개 액션 검증:
   - Edit → PUT /api/portfolio/position/{id}
   - Buy More → POST /api/portfolio/position/{id}/buy
   - Sell → POST /api/portfolio/position/{id}/sell
   - Delete → DELETE /api/portfolio/position/{id}

5. Free tier limit 검증:
   - 3개 추가 후 4번째 시도 → 403 + UI에서 upgrade prompt

6. 한국 주식 검증:
   - Symbol="005930.KS" (삼성전자) 추가 → fx_rate=0.0, isKorean=true 응답

## 수정 원칙
- 위 6단계 중 실패한 것만 수정.
- 작동하는 코드는 절대 건드리지 마.
- 모달 shell (portfolio-modal.tsx) 등 layout 코드는 보수적으로.
- AddPositionModal에서 PORTFOLIO_POSITIONS 사용 중이지만 백엔드에 /position (단수) 엔드포인트도 있음 — 둘 중 어느 것이 정답인지 endpoints.ts와 비교 후 결정.

## 산출물
- git diff로 수정 파일 보고
- 6단계 각각 작동 / 부분작동 / 미작동 표
- 1 fix = 1 commit, prefix `fix(portfolio):`
- 신규 테스트가 가능하면 tests/test_portfolio_flow.py 추가

## 금지
- engine.py, quant_models.py 등 백엔드 서비스 수정
- mock data 추가
- BUY/SELL 단어 도입
- API URL 변경
````

---

## Prompt #2 — Search Stock (Top-bar + Cmd+K) 검증/수정

````
PivoxQuant(/Users/seanbae/Desktop/취준/pivoxquant) 상단 검색바와 Cmd+K command palette
실 동작을 검증하고, 깨진 부분만 정확히 수정하라.

## 컨텍스트
이전 CEO 테스트(2026-04-14)에서 "Search Stock 안 눌림"으로 보고. 현재 코드 검토 결과:

핵심 파일:
- frontend/src/components/layout/top-bar.tsx
  - line 40-73: <button onClick={openSearchCommand}> 검색 트리거
  - line 17: import openSearchCommand from "@/components/ui/search-command"
- frontend/src/components/ui/search-command.tsx
  - openSearchCommand() → window.dispatchEvent(new CustomEvent("pq:search:open"))
  - SearchCommandMenu 컴포넌트가 listener
  - 백엔드 호출: GET /api/search?q=&limit=10 (debounce 300ms)
  - localStorage "pq:search:recents" max 5
- frontend/src/components/layout/dashboard-layout.tsx
  - line 41,50: <TopBar /> 마운트 (mobile + desktop 양쪽)
  - line 57: <CommandPalette />도 별도 마운트 — 두 palette 동시 마운트 충돌 주의

백엔드:
- routes/market.py 또는 routes/discover.py에 GET /api/search 존재 (확인 필요)
- 응답 shape: {results: [{ticker, name, exchange?, currency?, is_korean?}]}

## 작업 순서

1. 환경 확인:
   - 검색 백엔드 라우트 위치 grep으로 확인:
     grep -rn "@.*\.route.*/api/search" routes/
   - 응답 schema 실제 코드 확인

2. Claude in Chrome MCP로 /home 접속:
   - 콘솔 에러/경고 capture
   - 상단 검색 버튼 클릭 → palette 열리는지
   - Cmd+K (또는 Ctrl+K) 단축키 → palette 열리는지
   - 두 방법 모두 같은 modal 인스턴스 사용하는지 (이중 마운트 주의)

3. 검색 인터랙션:
   - "AAPL" 입력 → 300ms 후 /api/search?q=AAPL&limit=10 호출
   - 응답 results[] → "Stocks" 섹션 렌더
   - ↑↓ 키 네비게이션 (activeIdx 갱신)
   - Enter → router.push(`/detail/AAPL`) + saveRecent
   - Esc → 모달 닫힘

4. 빈 query 상태:
   - PAGES 8개 (Home/Portfolio/Watchlist/Risk/Discover/Market/Alerts/Settings)
   - Recents (localStorage에서 로드, 최대 5)

5. 한글/한국 ticker 검색:
   - "삼성" → 한국 종목 결과
   - "005930" → 005930.KS 결과 (is_korean=true)

6. dashboard-layout.tsx의 CommandPalette와 SearchCommandMenu 두 컴포넌트 충돌 확인:
   - 둘 다 Cmd+K listener 등록하지 않는지
   - 한쪽이 leftover면 제거 검토 (단, CommandPalette는 다른 용도일 수 있음 → grep으로 용도 확인 후 결정)

## 수정 원칙
- top-bar.tsx, dashboard-layout.tsx는 글로벌 레이아웃 — 신중히
- search-command.tsx는 모든 페이지에서 공유 — 깨면 광범위 영향
- 실패한 단계만 정확히 수정

## 산출물
- 작동/미작동 표
- 1 fix = 1 commit, prefix `fix(search):`
- search-command.tsx 변경 시 e2e 시나리오 documentation

## 금지
- /api/search URL 변경
- 한국 ticker 처리 로직 임의 수정 (data_fetcher.py에서 정규화 중)
````

---

## Prompt #3 — Watchlist 추가 검증/수정

````
PivoxQuant(/Users/seanbae/Desktop/취준/pivoxquant) Watchlist 추가/삭제 플로우를
실 클릭 검증하고, 깨진 부분만 수정하라.

## 컨텍스트
핵심 파일:
- frontend/src/app/(dashboard)/watchlist/page.tsx (258 lines, 완전 wired)
  - useWatchlist() hook 사용
  - "Add Symbol" 버튼 → setShowAdd(true)
  - DELETE 핸들러: apiFetch(API.watchlist.remove(id), {method:"DELETE"})
- frontend/src/components/watchlist/add-symbol-modal.tsx
  - Debounced GET /api/search?q=&limit=6 autocomplete
  - Submit: POST /api/watchlist {ticker, note}
- frontend/src/lib/endpoints.ts (API.watchlist):
  - list:   GET    /api/watchlist
  - add:    POST   /api/watchlist
  - remove: DELETE /api/watchlist/{id}
  - update: PATCH  /api/watchlist/{id}

백엔드:
- routes/watchlist.py
- 모델: models/watchlist.py (Watchlist)

## 작업 순서

1. Claude in Chrome MCP로 /watchlist 접속:
   - 빈 상태 → "No symbols yet" 에디토리얼 empty state 확인
   - 콘솔 에러 capture
   - GET /api/watchlist 응답 확인

2. Add Symbol 검증:
   - "Add Symbol" 버튼 클릭 → AddSymbolModal 열림
   - "MSF" 입력 → 300ms debounce 후 /api/search?q=MSF&limit=6 호출
   - suggestion list 렌더 확인
   - "Microsoft" suggestion 클릭 → ticker 필드 "MSFT" 채워짐
   - Note: "관찰 중" 입력
   - Submit → POST /api/watchlist {ticker:"MSFT", note:"관찰 중"} → 200
   - 모달 닫힘 + table에 새 행

3. 한국 종목 추가:
   - "삼성" 검색 → 005930.KS suggestion
   - 추가 → 정상 표시 (₩ currency, 한국시간 timestamp)

4. 행 인터랙션:
   - 행 클릭 → router.push("/detail/MSFT")
   - Trash 아이콘 클릭 → e.stopPropagation() (행 클릭과 분리)
   - DELETE /api/watchlist/{id} 200 → toast + 행 제거

5. 시그널 라벨 확인:
   - signal: "POSITIVE" → "Observed — positive signal"
   - "NEGATIVE" → "Observed — negative signal"
   - 다른 값 → "Observed — neutral"
   - BUY/SELL/HOLD/recommend 단어 절대 없는지 grep 검증:
     grep -rE "BUY|SELL|HOLD|recommend|advice" frontend/src/app/\(dashboard\)/watchlist/
     grep -rE "BUY|SELL|HOLD|recommend|advice" frontend/src/components/watchlist/

6. PriceWithTimestamp 컴포넌트 동작:
   - 가격 옆 "2분 전" 같은 relative time
   - market closed 시 "Closed" 배지

## 수정 원칙
- 시그널 라벨은 POSITIVE/NEGATIVE/NEUTRAL 외 도입 금지 (legal)
- 52W range는 백엔드 high_52w/low_52w 필드 추가 전까지 em-dash 유지 (mock 금지)

## 산출물
- 5단계 작동/미작동 표
- 1 fix = 1 commit, prefix `fix(watchlist):`

## 금지
- 52W range 가짜 값 합성 (코드 주석에 명시된 legal risk)
- mock price 데이터 추가
````

---

## Prompt #4 — Risk 페이지 7-Layer Defense 데이터 연동 검증/수정

````
PivoxQuant(/Users/seanbae/Desktop/취준/pivoxquant) /risk 페이지의 데이터 연동을
실 클릭 검증하고, schema mismatch 등 깨진 부분만 수정하라.

## 컨텍스트
핵심 파일:
- frontend/src/app/(dashboard)/risk/page.tsx        # V1/V2 feature flag
- frontend/src/app/(dashboard)/risk/_v1/page-v1.tsx # 기본 (V1)
  - 4 KPI: VaR / ES / Max DD / Corr Risk Index
  - 7-Layer ladder
  - Correlation heatmap
  - Rolling 30d VaR sparkline
  - 401/empty portfolio → DEMO_SUMMARY/DEMO_LAYERS fallback
- frontend/src/app/(dashboard)/risk/_v2/page-v2.tsx # NEXT_PUBLIC_RISK_V2=true 시
- frontend/src/components/risk/seven-layer-panel.tsx
  - export type RiskLayer { no, name, status, metricLabel, metricValue, observation }

백엔드:
- routes/risk.py
- risk_defense.py (567 lines, 완성 상태 — 절대 수정 금지)
  - 7 Layers: VaR / Correlation / VIX / Tail / Daily / Sector / Cash
- risk_models.py (GKYZ, LedoitWolf, ComponentES, ConditionalDD, TailRatio, Sortino)

엔드포인트:
- GET /api/risk/summary       → {var_1d_pct, es_1d_pct, max_dd_90d_pct, corr_risk_index}
- GET /api/risk/layers        → {layers: RiskLayer[]}
- GET /api/risk/correlation   → {tickers: string[], matrix: number[][]}
- GET /api/risk/rolling-var   → {points: [{date, var_pct}]}

## 작업 순서

1. 환경 확인:
   - curl http://localhost:5050/api/risk/summary → 200/401 확인
   - 4개 endpoint의 실제 응답 schema가 frontend interface와 일치하는지 비교
     - routes/risk.py grep "/api/risk/" → handler 함수 → return jsonify(...) 확인

2. Claude in Chrome MCP로 /risk V1 접속:
   - 페이지 렌더링 (헤더 + 4 KPI + 7-Layer + 히트맵 + 스파크라인)
   - 콘솔 에러
   - Network 탭에서 4개 risk 엔드포인트 응답 확인

3. 시나리오 A — 빈 portfolio:
   - "Sample preview" 배너 노출 확인
   - DEMO_SUMMARY 값(-2.14% etc.) 표시
   - 7 Layer ladder DEMO_LAYERS (yellow Correlation, yellow Sector 등) 표시
   - 10x10 demo correlation matrix 히트맵

4. 시나리오 B — portfolio 1~3개 보유:
   - 실데이터로 전환되는지
   - 모든 KPI 값이 실 계산값이고 demo 아닌지
   - layers[].observation 텍스트가 advice/recommend 단어 없는지 검증:
     grep -rE "advice|recommend|should buy|should sell" routes/risk.py

5. 시나리오 C — 503 (FMP 402 cooldown):
   - mock fallback 절대 안 되고 "data unavailable" 에디토리얼 노출
   - 단, demo는 401/empty 케이스에만 (이건 명확히 "Sample preview" 라벨)

6. V2 페이지 (NEXT_PUBLIC_RISK_V2=true 환경에서):
   - 별도 검증 — hero + 4 gauges + concentration + sector + 30d timeline
   - V1과 같은 4개 endpoint 사용하는지

## 수정 원칙
- risk_defense.py, risk_models.py 절대 수정 금지 (완성 상태, 1146+ lines)
- routes/risk.py 응답 schema가 frontend interface와 안 맞으면 백엔드 어댑터로 변환 (frontend interface 변경보다 우선)
- DEMO 데이터는 명백히 "Sample preview" 라벨 있는 401/empty 케이스만

## 산출물
- 시나리오 A/B/C 작동 표
- 1 fix = 1 commit, prefix `fix(risk):`
- schema diff가 있다면 별도 문서화

## 금지
- risk_defense.py 수정
- "위험" 표현은 OK, "추천" "조언" 금지
- 503 케이스에 mock 데이터 노출
````

---

## Prompt #5 — Discover 데이터 표시 검증

````
PivoxQuant(/Users/seanbae/Desktop/취준/pivoxquant) /discover 페이지의 데이터 표시를
검증하라. ⚠️ 빈 결과는 의도된 동작 — 버그가 아닐 수 있음.

## 컨텍스트
⚠️ 중요한 legal context:
routes/discover.py:30~54 (GET /api/discover):
  - §101(투자자문업) 회피 목적
  - pool = 보유 포지션 + 워치리스트 종목으로 한정
  - 둘 다 비면 빈 결과 반환이 정상 동작 (frontend EmptyState가 watchlist 추가 CTA 노출)
  - DISCOVER_POOL 전체 분석 = 임의 ticker 분석 = 자문업 회색지대

핵심 파일:
- frontend/src/app/(dashboard)/discover/page.tsx (26K, 6 sections)
  - 1. Market overview (5 indices)
  - 2. Top movers US (gainers/losers)
  - 3. Top movers KR
  - 4. Sector rotation (1D/5D/1M)
  - 5. Thematic screeners (oversold/52W highs/earnings beats)
  - 6. Live engine scan
  - line 36~39: "Mock fallback data was removed (2026-04-28)" — 의도적

백엔드:
- routes/discover.py
  - GET /api/discover                  → 사용자 ticker pool에서 engine.analyze
  - GET /api/discover/market-overview  → 5 indices
  - GET /api/discover/movers           → US/KR top movers
  - GET /api/discover/sectors          → sector rotation
  - GET /api/discover/screeners        → 3 thematic screeners
  - 모두 503 fail-fast (FMP 402 시 mock 안 함)
- fmp_service.py:72~165
  - _ENDPOINT_402_THRESHOLD = 3 (3 consecutive 402 → trip)
  - _ENDPOINT_402_COOLDOWN = 1800 (30분)

## 작업 순서

1. 환경 확인:
   - .env에서 FMP_API_KEY 설정 확인
   - 현재 FMP plan 잔여량 확인 (코드 변경 X, .env.example 참고)
   - APScheduler 로그에서 fmp 402 cooldown 활성 endpoint 확인

2. 시나리오 A — 빈 portfolio + 빈 watchlist:
   - Claude in Chrome MCP로 /discover 접속
   - 6 sections 각각 어떻게 렌더되는지:
     - Market overview / movers / sectors / screeners → upstream OK면 데이터 표시
     - Live engine scan (/api/discover) → 빈 결과 + EmptyState + watchlist CTA
   - 콘솔/Network 에러 capture

3. 시나리오 B — portfolio 2개 + watchlist 1개:
   - 미리 추가: AAPL, MSFT 보유 + 005930.KS 워치리스트
   - /discover 새로고침
   - Live engine scan에서 3개 분석 결과 노출
   - case-insensitive 매칭 검증:
     - routes/discover.py:50 `allowed = {t.upper() for t in (owned | watched) if t}`
     - DISCOVER_POOL이 .KS suffix 보유한 형태인지 확인:
       grep "DISCOVER_POOL" engine.py | head

4. 시나리오 C — 일부 endpoint 503:
   - movers나 sectors 한 곳이 503이면 그 섹션만 "data unavailable" 에디토리얼
   - 다른 섹션은 정상 표시
   - 절대 fake/mock data 표시 없는지 확인 (legal)

5. FMP 402 cooldown 동작:
   - 로그에서 "FMP endpoint X disabled for 1800s" 메시지 확인
   - 30분 경과 후 자동 retry되는지

## 수정 원칙
- mock fallback data 추가 절대 금지 (자본시장법, 코드 line 36~39 명시)
- 빈 결과는 의도된 동작 — "버그 fix"한답시고 pool 확장 금지
- 진짜 버그(schema mismatch, 라우팅 오류, .KS suffix 매칭 실패 등)만 수정

## 산출물
- 시나리오 A/B/C 표
- 1 fix = 1 commit, prefix `fix(discover):`
- pool 매칭 로직 변경 시 §101 컴플라이언스 영향 분석 첨부

## 금지
- routes/discover.py:54의 pool 한정 로직 임의 확장 (§101 위반)
- mock data 도입
- engine.DISCOVER_POOL 임의 수정
````

---

## 실행 후 통합 체크리스트

5개 프롬프트 순차 완료 후 사용자가 직접 점검:

- [ ] 모든 commit이 prefix 컨벤션 준수 (`fix(area):`)
- [ ] `pytest -q` 통과 (이전 세션 기준 1305/0)
- [ ] `pytest tests/test_no_hardcoded_samples.py -v` 통과 (legal guard)
- [ ] `npm --prefix frontend run lint` 통과 (현재 17 errors 보류항목 제외)
- [ ] CLAUDE.md의 CRITICAL 5건 status 업데이트 (수정 / 의도된 동작 / 외부 액션 등)
- [ ] HANDOVER.md에 v19 세션 추가 (정직한 작동/미작동 보고)

## 안전망

문제 발생 시:
```bash
# 마지막 N개 commit 되돌리기
git log --oneline -10
git reset --hard <commit_before_changes>

# 특정 파일만 되돌리기
git checkout HEAD -- path/to/file
```

각 프롬프트 시작 전:
```bash
git status        # working tree clean 확인
git branch --show # 작업 브랜치 확인 (main에 직접 X 권장)
git checkout -b fix/critical-bug-N  # feature branch 생성
```
