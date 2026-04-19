# Dead Code 후보 리스트 (CEO 판단 필요)

> 2026-04-19 cleanup 패스에서 식별된 미사용 코드. **자동 삭제하지 않았음** —
> 스케줄러/백그라운드 참조 가능성, 또는 의도적으로 보존된 코드일 수 있어
> CEO(배상현) 확인 후 삭제 권장.

---

## 백엔드 — Python 파일

### `investor_profiles.py` (미사용, 루트)
- `from investor_profiles` / `import investor_profiles` 참조 **0회**.
- 내부 독스트링: `get_profile_params(investor_type)` 제공 목적.
- **권고**: onboarding/questionnaire 파이프라인에서 재연결 계획이 없다면
  삭제 검토. (`questionnaire.py`와 통합 가능성 있음)

---

## 프론트엔드 — 미사용 React Hooks

`frontend/src/lib/hooks.ts` 에서 정의됐으나 어느 페이지/컴포넌트에서도
import 되지 않은 훅 목록. 총 **8개**, 추정 LOC 감소량 **약 150~200줄**.

| Hook | 정의 라인 | 비고 |
| --- | --- | --- |
| `useEarnings` | L66 | 실적 캘린더용. 페이지 미연결 |
| `useCrossAsset` | L82 | Cross-asset 대시보드용. UI 미구현 |
| `useVixStrategy` | L89 | VIX 전략 위젯용. UI 미구현 |
| `useDaytradeScan` | L103 | DayTrade → Market 통합 후 미사용 |
| `useQuestionnaire` | L124 | 온보딩 재설계 대기 |
| `useAiStatus` | L133 | AI 상태 배지용. UI 미구현 |
| `useAiCoaching` | L145 | "코치" 네이밍 법적 이슈로 보류 |
| `useRealtimePrices` | L318 | SSE provider가 직접 `realtime.tsx`에서 처리 |

---

## 프론트엔드 — 미사용 UI 컴포넌트

`frontend/src/components/ui/` 에서 shadcn 기본 컴포넌트로 생성됐으나
어느 컴포넌트/페이지에서도 import 되지 않음. 총 **624 LOC**.

| Component | LOC | 비고 |
| --- | --- | --- |
| `avatar.tsx` | 109 | 프로필 드롭다운 미구현 상태 |
| `checkbox.tsx` | 31 | Terms checkbox는 native input 사용 |
| `dialog.tsx` | 159 | `modal-shell.tsx`로 대체됨 |
| `dropdown-menu.tsx` | 268 | 프로필/알림 드롭다운 미구현 |
| `input.tsx` | 21 | native input 사용 |
| `label.tsx` | 20 | native label 사용 |
| `logo.tsx` | 16 | 랜딩에서 inline SVG 사용 |

**권고**: avatar/dropdown-menu는 P1(프로필 드롭다운 구현) 에서 사용될
예정이므로 **보존**. 나머지 5개(`checkbox`, `dialog`, `input`, `label`,
`logo`)는 삭제해도 무방 — 단, shadcn CLI로 언제든 재생성 가능.

---

## 프론트엔드 — 의존성 검토

`frontend/package.json`:
- **`shadcn`** (`^4.1.2`) — CLI 도구. runtime import 0회. `devDependencies`
  로 이동하거나 제거 권장 (필요 시 `npx shadcn@latest` 사용).
- **`tw-animate-css`** — `src/app/globals.css`에서 `@import` 사용 중.
  **보존** (globals.css는 정책상 수정 금지).

## 백엔드 — 의존성 검토

`requirements.txt` 전수 확인 완료. 모든 패키지가 실제 import 됨
(lazy/conditional import 포함). **제거 후보 없음**.

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
