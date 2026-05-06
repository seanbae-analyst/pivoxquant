# AutoTrade Removal + Alpaca BYO Conversion — 2026-04-27

**결정자**: CEO (배상현) + 법무 감사 결과
**근거**:
- 자동매매(autotrade) live 활성화 시 **투자일임업 등록 의무** (자본금 5억) → 기능 자체 제거
- Alpaca 시장 데이터 재배포 시 **commercial license** 필요 → **BYO(Bring Your Own Key)** 모델로 명시화 (사용자 본인 키만 forward, 우리는 재배포 X)

---

## 1. 미션 1 — 자동매매 완전 제거

### 1-A. Frontend — 삭제된 파일

| 경로 | 비고 |
|------|------|
| `frontend/src/app/(dashboard)/autotrade/page.tsx` | 페이지 본체 |
| `frontend/src/app/(dashboard)/autotrade/layout.tsx` | route metadata |
| `frontend/src/app/(dashboard)/autotrade/` (디렉토리) | `rm -rf` 처리 |

### 1-B. Frontend — 변경된 파일

| 경로 | 변경 |
|------|------|
| `frontend/src/app/(dashboard)/layout.tsx` | `DisclaimerKind` 에서 `"auto-trade"` 제거. `PATH_TO_TYPE` 에서 `["/autotrade", "auto-trade"]` 매핑 제거. `ALWAYS_EXPANDED_PREFIXES` 에서 `"/autotrade"` 제거 → 빈 배열. |
| `frontend/src/components/layout/terminal-sidebar.tsx` | `TerminalSidebarKey` 유니언에서 `"autotrade"` 제거. `PORTFOLIO` 그룹에서 autotrade item 제거. lucide `Bot` import 제거. |
| `frontend/src/components/layout/bottom-nav.tsx` | Portfolio 그룹에서 `{ href: "/autotrade", ...Bot }` 제거. lucide `Bot` import 제거. |
| `frontend/src/lib/endpoints.ts` | `autotrade` 그룹 (status / start / stop / sellAll / pending / approve / reject) 통째로 제거. 복원 절차 코멘트 첨부. |
| `frontend/src/app/robots.ts` | disallow 목록에서 `"/autotrade/"` 제거. |
| `frontend/src/messages/en.json` | `nav.autotrade` 및 `dashboard.autotrade.{title,paperMode,killSwitch,enable,disable,status}` 제거. |
| `frontend/src/messages/ko.json` | 위 동일 (한글 라벨 제거). |
| `frontend/src/i18n/ko.ts` | `autotrade` 키 그룹 (pageTitle/Subtitle, statusRunning/Stopped, paper/liveMode, engine, tradesToday, pendingApproval, startPaper, starting/stopping, stopTrade, pendingTrades, noPendingRunning/Stopped, warningTitle/Desc, lastRun, approve, reject) 통째로 제거. |

### 1-C. Backend — 비활성화된 파일 (보존, 미삭제)

| 경로 | 처리 |
|------|------|
| `stockpilot/autotrader.py` | **파일 보존** (rollback 가능). 현재 routes/ 에서 import 안 됨. |
| `stockpilot/routes/autotrade.py` | **파일 보존** (rollback 가능). routes/__init__.py 에서 등록 해제. |

### 1-D. Backend — 변경된 파일

| 경로 | 변경 |
|------|------|
| `stockpilot/routes/__init__.py` | `from .autotrade import autotrade_bp` 주석 처리. blueprints 리스트의 `autotrade_bp` 주석 처리. 두 위치 모두 `# REMOVED 2026-04-27 per CEO + legal` 마킹 + 복원 절차 (3-step) 첨부. |
| `stockpilot/app.py` | `svc.init_trader(db, Position, TradeHistory, app)` 호출 주석 처리 — boot 시 AutoTrader 인스턴스화 차단. 복원 절차 코멘트 첨부. |
| `stockpilot/services/container.py` | top-level `from autotrader import AutoTrader` 제거 (module load 시 autotrader.py side-effect 실행 차단). `trader: AutoTrader \| None = None` → `trader: Any = None` 로 변경. `init_trader()` 본문을 no-op (`return None`) 로 치환 — 호환성 유지. 복원 절차 4-step 코멘트 첨부. |
| `stockpilot/config.py` | `ALPACA_ENABLED` 주석 블록 갱신 — `autotrader.py` 참조 제거, BYO 모델 명시. |

### 1-E. 문서 / 메모리 — 변경된 파일

| 경로 | 변경 |
|------|------|
| `stockpilot/CLAUDE.md` | `autotrader.py` 항목에 `⚠️ REMOVED` 마킹. dashboard 페이지 목록에서 `autotrade` 삭제. "건드리지 말 것" 원칙에서 `autotrader.py` 제거. |
| `stockpilot/HANDOVER.md` | 보안 섹션 상단에 `2026-04-27 AutoTrade 기능 완전 제거` + `Alpaca BYO 명시화` 항목 신규 추가. C1 (AutoTrader 싱글톤 leak fix) 에 `※ 2026-04-27 기능 자체 제거됨` 부기. |
| `stockpilot/PRODUCT_PLAN.md` | TradingView 비교 행에서 `자동매매 없음` 약점 항목 삭제. 코멘트로 사유 명시. |
| `~/.claude/.../memory/product_features.md` | `자동매매 (Alpaca/KIS)` 행 status `✅` → `❌ REMOVED 2026-04-27` 로 갱신. 재활성화 조건 (자본금 5억 + 투자일임업 등록) 명시. |

---

## 2. 미션 2 — Alpaca BYO(Bring Your Own Key) 전환

### 2-A. 핵심 결론
- **server-side `ALPACA_ENABLED` 는 이미 default OFF** — 변경 없음 (기존 kill-switch가 BYO 정책에 부합)
- **per-user BYO 인프라는 이미 존재** — `services/broker/user_alpaca_service.py` (암호화 저장된 사용자 키로 paper account 조회만 forward)
- 본 작업에서는 **BYO 정책 명시화 + UI 카피 + 약관/개인정보처리방침** 만 보강

### 2-B. 변경된 파일

| 경로 | 변경 |
|------|------|
| `stockpilot/config.py` | `ALPACA_ENABLED` 주석 블록을 BYO 모델 설명으로 갱신. server-key path는 OFF 유지 / per-user path 는 `user_alpaca_service.py` 라고 명시. autotrader.py 참조는 동시에 제거. |
| `frontend/src/app/(dashboard)/settings/page.tsx` | `ALPACA_ENABLED` 게이팅 주석을 "Phase-1 hidden" 에서 "BYO 모델 명시화" 로 갱신. |
| `frontend/src/components/broker/alpaca-connect-modal.tsx` | description 아래에 BYO 안내 문단 추가 — "Bring Your Own Key (BYO): market data is fetched under your own Alpaca account license. PivoxQuant does not redistribute Alpaca market data — your keys, your license." |
| `frontend/src/content/terms-ko.md` | 제9조 (콘텐츠 저작권) 에 BYO 조항 신규 (구 2항을 2,3,4,5 로 재번호). 본인 발급 API 키, 회사 미재배포, 라이선스·요금 책임 본인 명시. |
| `frontend/src/content/privacy-ko.md` | 제3자 제공 표 Alpaca 행을 `BYO` 마킹 + `이용자 본인 발급 API 키(암호화 저장)` 로 갱신. 신규 섹션 `2-1. Alpaca BYO 원칙` 추가 — 암호화 저장, 본인 계정 데이터만 조회, 재배포 X, 키 폐기/연동해지 가능. |

### 2-C. 변경하지 않은 파일 (이미 BYO 호환)

- `stockpilot/data_fetcher.py` — `ALPACA_ENABLED=0` default 로 system-key path 자동 비활성화. 변경 불필요.
- `stockpilot/services/broker/user_alpaca_service.py` — BYO 핵심 구현체, 이미 paper-only + 암호화 저장 + 본인 계정 한정. 변경 불필요.
- `stockpilot/realtime_service.py`, `stockpilot/daytrade_service.py` — 동일 kill-switch 적용 중, 변경 불필요.

---

## 3. 잔존 reference (의도된 marker)

`grep -rn "autotrade\|autotrader" frontend/src` 결과 (8건, 전부 `// REMOVED 2026-04-27 per CEO + legal` 마커):

```
src/app/robots.ts:24                       — disallow 목록 위치 마커
src/app/(dashboard)/layout.tsx:24          — DisclaimerKind 변경 사유 주석
src/app/(dashboard)/layout.tsx:50          — ALWAYS_EXPANDED_PREFIXES 변경 사유 주석
src/components/layout/terminal-sidebar.tsx:55  — 유니언 변경 사유 주석
src/components/layout/terminal-sidebar.tsx:90  — PORTFOLIO 항목 변경 사유 주석
src/components/layout/bottom-nav.tsx:95    — Portfolio nav 변경 사유 주석
src/lib/endpoints.ts:80                    — endpoints 그룹 제거 + 복원 절차 주석
src/i18n/ko.ts:221                         — i18n 그룹 제거 사유 주석
```

모두 의도된 placeholder 코멘트. 향후 grep 으로 자동매매 제거 시점 / 사유 추적 가능.

Backend grep:

```
stockpilot/routes/__init__.py:16-21        — import 주석 처리 + 복원 3-step 가이드
stockpilot/routes/__init__.py:62-64        — blueprints 리스트 주석 처리
stockpilot/CLAUDE.md (3건)                 — REMOVED 마킹
stockpilot/HANDOVER.md                     — 신규 항목
stockpilot/PRODUCT_PLAN.md                 — 비교표 주석
stockpilot/autotrader.py / routes/autotrade.py  — **파일 자체 보존 (rollback)**
stockpilot/config.py                       — autotrader.py 참조 제거 완료, alpaca 주석에 한해 BYO 설명 유지
```

---

## 4. 검증 결과

### 4-A. TypeScript
`cd frontend && npx tsc --noEmit` — Source code TS clean.
**4건 error 발견** — 모두 stale `.next/types/validator.ts` (Next.js dev preview server 가 cache regenerate 대기 중):

```
.next/types/validator.ts(25,44):  Type '"/autotrade"' is not assignable to type 'LayoutRoutes'.
.next/types/validator.ts(25,75):  (동일)
.next/types/validator.ts(116,39): Cannot find module '../../src/app/(dashboard)/autotrade/page.js'
.next/types/validator.ts(534,39): Cannot find module '../../src/app/(dashboard)/autotrade/layout.js'
```

이 cache 는 dev server 다음 reload 시 자동 재생성됨. `.next` 디렉토리 삭제 시 즉시 해소되나 현재 dev preview 가 점유 중이라 권한 거부. **Source TS 자체는 clean** — 검증 PASS 로 간주.

### 4-B. 영향 받지 않은 기능 (확인)
- 수동 매수/매도 모달 (`broker_oauth_bp`, manual-card.tsx) — 정상
- KIS read-only 연결 (`kis_service.py`, kis-card.tsx) — 정상
- Alpaca BYO 연결 (`user_alpaca_service.py`, alpaca-card.tsx) — 정상
- Portfolio / Watchlist / Risk / Market — autotrade 와 독립, 영향 없음

---

## 5. 향후 자동매매 재활성화 시 절차

### 법적 선결 조건
1. **자본금 5억 원 확보** (자본시장법상 투자일임업 최소 자기자본)
2. **금융위원회 투자일임업 등록 완료** (등록 신청서, 임원 자격, 내부통제 시스템 심사)
3. 법무팀 사인오프 + Alpaca commercial data license 별도 검토

### 코드 복원 path
1. **Backend** `stockpilot/routes/__init__.py`:
   - `# from .autotrade import autotrade_bp` → 주석 해제
   - blueprints 리스트의 `# autotrade_bp,` → 주석 해제
2. **Backend** `stockpilot/autotrader.py` 그대로 사용 (보존됨)
3. **Backend** `stockpilot/routes/autotrade.py` 그대로 사용 (보존됨)
4. **Frontend** 신규 작성 필요 (페이지 / 네비 / endpoints / i18n / disclaimer 매핑 5종):
   - `app/(dashboard)/autotrade/page.tsx` + `layout.tsx`
   - `components/layout/terminal-sidebar.tsx` PORTFOLIO 그룹에 항목 + key 유니언 추가
   - `components/layout/bottom-nav.tsx` Portfolio 그룹에 항목 추가
   - `lib/endpoints.ts` autotrade 그룹 복원
   - `app/(dashboard)/layout.tsx` `DisclaimerKind` 에 `"auto-trade"` 복원, `PATH_TO_TYPE` + `ALWAYS_EXPANDED_PREFIXES` 복원
   - `messages/{en,ko}.json` + `i18n/ko.ts` 라벨 복원
   - `app/robots.ts` disallow 목록 복원
5. **Docs** `CLAUDE.md` / `HANDOVER.md` / `PRODUCT_PLAN.md` / `product_features.md` REMOVED 마커 정리

### 정책
- 본 git diff 는 **CEO 검토 후 commit 결정** — 본 세션에서는 push/commit 미수행.
- rollback 시 `git revert` 또는 위 path 의 수동 복원 양자 가능.

---

## 6. 운영 규칙 준수 확인

| 규칙 | 준수 |
|------|------|
| git commit/push 금지 | ✅ 미수행 |
| 백엔드 파일 직접 삭제 금지 (비활성화만) | ✅ autotrader.py / routes/autotrade.py 모두 보존 |
| 잔존 reference 정리 또는 보고 | ✅ 위 §3 에 전수 보고 (모두 의도된 marker) |
| 다른 기능 영향 없음 확인 | ✅ §4-B |
| 매 단계마다 진행 보고 | ✅ 정찰 / frontend / backend / BYO / docs / 검증 6단계 보고 |
