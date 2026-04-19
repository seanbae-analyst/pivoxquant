# Dead Code 제거 기록

> 2026-04-19 cleanup 패스에서 식별된 미사용 코드 + 실제 제거 기록.

---

## 백엔드 — Python 파일

### `investor_profiles.py` (미사용, 루트)
- [x] **제거 완료 (2026-04-19)** — 1164줄 삭제
- `from investor_profiles` / `import investor_profiles` 참조 **0회** 최종 확인 후 삭제.
- 재연결 계획이 생기면 git 히스토리에서 복원 가능.

---

## 프론트엔드 — 미사용 React Hooks

`frontend/src/lib/hooks.ts` 에서 정의됐으나 어느 페이지/컴포넌트에서도
import 되지 않은 훅 목록. 총 **8개 전부 제거 완료 (2026-04-19)**.

| Hook | 정의 라인 | 상태 |
| --- | --- | --- |
| `useEarnings` | L66 | [x] 제거 |
| `useCrossAsset` | L82 | [x] 제거 |
| `useVixStrategy` | L89 | [x] 제거 |
| `useDaytradeScan` | L103 | [x] 제거 |
| `useQuestionnaire` | L124 | [x] 제거 |
| `useAiStatus` | L133 | [x] 제거 |
| `useAiCoaching` | L145 | [x] 제거 (ai/page.tsx 가 직접 apiFetch 사용 중) |
| `useRealtimePrices` | L318 | [x] 제거 (@deprecated wrapper) |

부수 효과로 `useState`, `useCallback`, `useMemo`, `useRealtimeContext`, `apiFetch`
import 도 정리.

---

## 프론트엔드 — 미사용 UI 컴포넌트

`frontend/src/components/ui/` 에서 shadcn 기본 컴포넌트로 생성됐으나
어느 컴포넌트/페이지에서도 import 되지 않음.

| Component | LOC | 상태 |
| --- | --- | --- |
| `avatar.tsx` | 109 | 보존 — P1 프로필 드롭다운 구현 예정 |
| `checkbox.tsx` | 31 | [x] 제거 |
| `dialog.tsx` | 159 | [x] 제거 (`modal-shell.tsx`로 대체됨) |
| `dropdown-menu.tsx` | 268 | 보존 — P1 프로필/알림 드롭다운 예정 |
| `input.tsx` | 21 | [x] 제거 (native input 사용) |
| `label.tsx` | 20 | [x] 제거 (native label 사용) |
| `logo.tsx` | 16 | [x] 제거 (랜딩에서 inline SVG 사용) |

**제거된 UI 컴포넌트 총 247줄.** shadcn CLI로 언제든 재생성 가능
(`npx shadcn@latest add <name>`).

---

## 프론트엔드 — 미사용 타입 (types.ts)

`frontend/src/lib/types.ts` 에서 어디서도 import 되지 않는 타입들 제거.
Artifact 관련 타입은 전부 보존.

| Type | 상태 | 사유 |
| --- | --- | --- |
| `EarningsItem` | [x] 제거 | `useEarnings` 훅과 함께 사용됐음 |
| `EarningsResponse` | [x] 제거 | `useEarnings` 훅과 함께 사용됐음 |
| `CrossAssetItem` | [x] 제거 | `useCrossAsset` 훅과 함께 사용됐음 |
| `CrossAssetResponse` | [x] 제거 | `useCrossAsset` 훅과 함께 사용됐음 |
| `VixStrategyResponse` | [x] 제거 | `useVixStrategy` 훅과 함께 사용됐음 |
| `SignalMsg` | [x] 제거 | DayTradeResult/ScanResult에서만 사용 |
| `DayTradeResult` | [x] 제거 | `useDaytradeScan` 훅과 함께 사용됐음 |
| `DayTradeScanResponse` | [x] 제거 | `useDaytradeScan` 훅과 함께 사용됐음 |
| `ScanResult` | [x] 제거 | 어디서도 미사용 (orphaned) |
| `QuestionOption` | [x] 제거 | `useQuestionnaire` 훅과 함께 사용됐음 |
| `Question` | [x] 제거 | `useQuestionnaire` 훅과 함께 사용됐음 |
| `QuestionnaireResponse` | [x] 제거 | `useQuestionnaire` 훅과 함께 사용됐음 |
| `AiStatusResponse` | [x] 제거 | `useAiStatus` 훅과 함께 사용됐음 |
| `AiMorningSummaryResponse` | [x] 제거 | 어디서도 미사용 (orphaned) |
| `AiChatMessage` | [x] 제거 | 어디서도 미사용 (orphaned) |
| `ShareTokenResponse` | [x] 제거 | Portfolio Share 기능 미구현 (orphaned) |
| `SharedPosition` | [x] 제거 | Portfolio Share 기능 미구현 (orphaned) |
| `SharedPortfolioResponse` | [x] 제거 | Portfolio Share 기능 미구현 (orphaned) |
| `AiCoachingResponse` | 보존 | ai/page.tsx 가 직접 사용 중 |
| `AiSwotResponse` 외 AI 타입 | 보존 | ai/page.tsx 가 사용 중 |
| `Artifact*` | 보존 | 최근 추가된 MVP 타입 |

---

## 프론트엔드 — 의존성 검토

`frontend/package.json`:
- [x] **`shadcn`** (`^4.1.2`) — `dependencies` → `devDependencies` 이동 완료.
  필요 시 `npx shadcn@latest` 사용.
- **`tw-animate-css`** — `src/app/globals.css`에서 `@import` 사용 중. **보존**.

## 백엔드 — 의존성 검토

`requirements.txt` 전수 확인 완료. 모든 패키지가 실제 import 됨
(lazy/conditional import 포함). **제거 후보 없음**.

---

## 검증 결과 (2026-04-19)

- `npx tsc --noEmit` ✅ 통과 (exit 0)
- `npx eslint .` ✅ 통과 (exit 0)
- `npx next build` ✅ 빌드 성공 (compiled in ~38s, 모든 페이지 prerender 성공)
- `python3 -m pytest tests/` ✅ 279 passed, 60 warnings in 77.59s

회귀 없음.

---

## 다음 세션 후보

다음 dead-code 패스에서 검토할 항목:

1. **services/ 디렉토리 구조 분리** (ai/, brokers/, data/, infra/) — 임포트 경로
   갱신 범위가 커서 별도 리팩토링 세션 권장.
2. **공유 포트폴리오 기능** (`SharedPosition*` 타입 제거됨) — 재구현 시
   타입 복원 필요. 현재 `routes/` 에는 구현된 엔드포인트가 있는지 확인 필요.
3. **`avatar.tsx`, `dropdown-menu.tsx`** — P1 프로필 드롭다운이 구현되지 않으면
   다음 cleanup에서 제거 검토.

---

## 디렉토리 구조 권고 (보류 — 이동 금지)

현재 `services/` 평탄 구조. 향후 다음과 같이 분리 권장:

```
services/
├── ai/         # ai_service, morning_brief_service
├── artifacts/  # (이미 존재)
├── brokers/    # broker_sync_service, broker/user_kis, broker/user_kiwoom
├── data/       # (이미 존재) fred, pykrx, sec_edgar
└── infra/      # cache, crypto, fx, market_status, push, serializers,
                #   thesis, kr_stock_registry, us_stock_registry
```

**이번 패스에서는 이동하지 않음** — import 경로 갱신 범위가 크고
회귀 위험이 높아 별도 리팩토링 세션에서 진행 권장.

---

## 중복/유사 로직 (중복 아님 확인)

- `services/data_fetcher.py` (1305 L) vs `services/fmp_service.py` (1139 L):
  data_fetcher는 Alpaca→FMP 폴백 + KIS 한국 데이터까지 포함, fmp_service는
  FMP v4 stable 전용 + TTL 캐시/예산 관리. **서로 다른 책임, 유지**.
- `services/morning_brief_service.py` (367 L) vs
  `services/artifacts/weekly_memo_service.py` (754 L): 전자는 매일 아침
  브리프(Thesis Tracker 기반), 후자는 주간 Investor Memo(PDF/이메일).
  artifact 타입이 다름. **의도된 구조, 유지**.
- `routes/broker_sync.py` (46 L) vs `routes/broker_oauth.py` (219 L):
  전자는 generic/Alpaca 싱크 엔드포인트, 후자는 KIS OAuth 개인자격증명.
  **서로 다른 책임, 유지**.
