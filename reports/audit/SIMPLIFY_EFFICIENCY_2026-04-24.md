# SIMPLIFY_EFFICIENCY_2026-04-24

Auditor: audit-code (Sonnet 4.6)
Scope: 10개 파일 효율성 교차검증 — hot path bloat / N+1 / 메모리 누수
Date: 2026-04-24

---

## 요약

| 심각도 | 건수 |
|--------|------|
| High   | 6    |
| Med    | 5    |
| Low    | 4    |
| Total  | 15   |

---

## 발견 사항 상세

| # | 파일:줄 | 분류 | 문제 | 영향 | 제안 |
|---|---------|------|------|------|------|
| 1 | `services/profile/persona_classifier_v2.py:478-480` | High — per-request redundant DB query | `classify_persona_multi()` 진입 시 `_fetch_trades`, `_fetch_positions`, `InvestmentProfile.query.filter_by` 3개의 독립 DB 쿼리를 직렬로 실행. 동일 함수를 호출하는 `get_persona_confidence` (L516), `explain_persona_classification` (L521)도 각각 전체 분류를 다시 계산함 — wrapper 2개가 `classify_persona_multi` 전체를 재실행하여 DB hit × 3 | GET /api/profile/persona-detail 한 번에 최소 3회 DB I/O + wrapper 경로는 2배 | `get_persona_confidence`와 `explain_persona_classification`을 classify 결과의 필드 슬라이스로 교체. 또는 Redis/SQLAlchemy identity-map level short-TTL cache (e.g., 60s) 적용 |
| 2 | `services/profile/persona_classifier_v2.py:221-234` | High — per-request hot-path DB | `_extract_features` 내부에서 `_fetch_pulse` (L221) 와 `_fetch_feedback` (L228)가 호출됨. 두 쿼리는 `classify_persona_multi`를 부르는 모든 request마다 실행됨. `window_days * 2` = 180d 분량 행을 매번 로드 | 요청마다 WeeklyPulse + ArtifactFeedback 풀 테이블 스캔 가능 (인덱스 없는 경우) | user_id, submitted_at/created_at 복합 인덱스 확인. 두 쿼리를 classify_persona_multi 최상단에서 한 번만 fetch 후 번들로 전달 |
| 3 | `services/profile/group_benchmark.py:219-246` | High — Overly broad query + Python-side filter | `_user_ids_for_persona()`: `InvestmentProfile` 전체를 `profile_type IS NOT NULL` 조건만 걸어 로드(L236-239)한 뒤 Python dict lookup으로 persona 매핑 수행. 유저가 많아질수록 전체 테이블 로드 | 유저 수 1000명 시 불필요한 O(n) 행 로드 | SQL WHERE 절에서 직접 `profile_type IN (legacy_types)` 필터링. `DECLARED_TO_PERSONA` key set이 소규모이므로 in-clause가 효율적 |
| 4 | `services/profile/group_benchmark.py:586-620` | High — 중복 전체 테이블 스캔 | `_all_users_baseline()`: `TradeHistory.query.filter(traded_at >= cutoff).all()` 로 전체 유저 거래 내역 로드. `compute_all_personas()` → `compute_persona_stats()` × 8 반복 시 각 호출이 `_aggregate_metrics` → `_all_users_baseline`을 8회 호출 | 8 persona × 1 baseline = TradeHistory 전체 테이블을 9회 로드. 거래 10만 건 시 심각한 cron 과부하 | `compute_all_personas`에서 `_all_users_baseline`을 한 번만 계산하고 `_aggregate_metrics`에 파라미터로 전달. 현재 코드의 "session identity cache" 주석(L294)은 SQLAlchemy identity map이 이를 처리하지 않음 — 실제로 매번 DB 쿼리 발생 |
| 5 | `services/profile/group_benchmark.py:438-523` | Med — FIFO 로직 중복 | `_user_mistakes()` 내 disposition 계산(L451-490)이 `_avg_holding_days()` (L406-435)와 동일한 FIFO BUY/SELL 매칭 로직을 반복 구현. 동일 user의 trades를 두 번 순회하며 동일한 `opens` dict를 별도 구성 | per-user O(n) 연산을 2회 수행. 그룹 통계 배치에서 유저×2 반복 | 공통 FIFO 매처를 유틸 함수로 추출, `_avg_holding_days`와 `_user_mistakes` 양쪽에서 재사용 |
| 6 | `services/artifacts/pre_trade_checklist_service.py:363-374` | Med — import-time regex 검사 | `_audit_all()` (L363)이 모듈 임포트 시 즉시 실행됨(L374). `_UNIVERSAL`(3) + `_PERSONA_SPECIFIC`(8 personas × 4 questions) = 35 문자열 × 2 필드 × 10 forbidden terms = 700회 substring 검색. 유사하게 `persona_warnings.py`의 `_audit_all()`(L246-254)도 임포트마다 실행 | 워커 spawn / 모듈 reload / 테스트 실행마다 추가 CPU. 콘텐츠가 정적이라 runtime 중 변하지 않음 | 정적 데이터이므로 1회만 실행하면 됨. 현 구조 자체는 안전하지만, `_audit_all()`을 `if __debug__:` 블록으로 래핑하거나, 빌드/CI 단계 pytest로만 실행하도록 위임 |
| 7 | `routes/profile.py:696-708` | Med — 요청마다 duplicate DB query | `get_persona_benchmark()` 내 `get_persona_stats(persona, window)` 가 None을 반환할 때, 이유 판별을 위해 `PersonaGroupStats.query.filter_by(...).first()` 를 추가로 실행(L703-709). get_persona_stats 내부에서 이미 동일 쿼리를 실행하고 있음(group_benchmark.py L193-200) | 캐시 miss 경로에서 동일 PersonaGroupStats 행을 2회 조회 | `get_persona_stats`가 `(data, reason)` tuple 반환하도록 시그니처 확장, 또는 suppressed row를 별도 반환값으로 노출 |
| 8 | `routes/profile.py:760-786` | Med — N+1 패턴 | `get_persona_benchmark_all()`: `get_all_persona_stats(window)`를 한 번 호출 후(L759), for loop에서 `PersonaGroupStats.query.filter_by(persona=p).first()` 를 suppressed 판별을 위해 PERSONA_CODES 수(8)만큼 재호출(L771-775) | request마다 PersonaGroupStats를 최대 1+8=9회 쿼리 | 단일 쿼리로 window에 해당하는 모든 최신 row를 로드한 뒤 persona별로 분기. `GROUP BY persona`를 활용하거나 subquery로 최신 row 선택 |
| 9 | `routes/market.py:683-698` | Med — 반복 KISService 인스턴스화 | `_kis_index_snapshot()` 내부에서 KIS live quote(L647)와 KIS history fallback(L685) 두 경로 모두에서 `KISService()`를 새로 생성. per-ticker 호출이며 KR 인덱스는 4개(`_KR_INDEX_SPEC`)이므로 최대 8회 인스턴스화 | 커넥션 풀/세션 재생성 비용. KISService 생성자에 I/O가 있는 경우 심각 | `market_indices()` 레벨에서 단일 `KISService()` 인스턴스를 생성해 파라미터로 전달, 또는 request-scoped 싱글턴 적용 |
| 10 | `routes/market.py:80-82` | Low — import-time env lookup | `search_stocks()` 핸들러 내부에서 매 요청마다 `os.environ.get("FMP_API_KEY", "")` 실행(L81). 환경변수는 변경되지 않음 | 미미한 오버헤드; 가독성 문제 | 모듈 레벨 상수로 캐시. `_FMP_API_KEY = os.environ.get("FMP_API_KEY", "")` |
| 11 | `frontend/src/app/(dashboard)/profile/page.tsx:186-210` | Low — localStorage 중복 파싱 | `LivingCFOControls` useEffect 내부(L196-209)에서 `pq_cfo_feedback_votes_v1` localStorage 항목을 JSON.parse 후 Object.keys 계산. 이 컴포넌트는 pulse data 변경마다 재실행됨(`[pulse?.cadence]` dep) | render마다 localStorage 접근 + JSON.parse. 빈번하지 않으나 불필요 | feedbackCount를 별도 useMemo 또는 한 번만 실행되는 useEffect `[]`로 분리 |
| 12 | `frontend/src/components/landing/engine-models-drawer.tsx:863-944` | Low — 불필요한 반복 filter | `CATEGORIES.map()` 내부에서 매 render마다 `MODEL_DEFS.filter((m) => m.category === col.key)` 를 6회 실행(L864). MODEL_DEFS는 정적 상수(40개 항목) | 매 render마다 O(40×6) = 240회 비교. 40개 항목이라 실제 비용은 미미하나 구조 불필요 | 모듈 상단에서 `groupBy(MODEL_DEFS, 'category')` 결과를 Map으로 한 번 계산 |
| 13 | `frontend/src/lib/useFocusTrap.ts:65` | Low — Tab keydown 시 querySelectorAll 재실행 | `onKeyDown` handler 내부(L65)에서 Tab 키 누를 때마다 `querySelectorAll(FOCUSABLE_SELECTOR)` 전체 DOM 탐색 수행. 드로어 내 focusable 목록은 열린 동안 바뀌지 않음 | Tab 연타 시 반복 DOM 쿼리. 모달 내 요소가 많으면 누적 비용 증가 | `active` 시점에 focusables 목록을 한 번 메모이제이션(useMemo 불가 위치이므로 ref에 캐시), DOM mutation이 없으면 재계산 스킵 |
| 14 | `services/profile/persona_classifier_v2.py:489` | Low — 윈도우 필터 이중 수행 | `classify_persona_multi` L489에서 `trade_count` 산출 시 `trades` 전체를 list comprehension으로 재필터링(traded_at >= now - window_days). 이미 `_extract_features` 내부(L171-172)에서 동일 window 필터를 수행한 `window_trades`가 존재하지만 반환되지 않음 | 미미한 이중 순회. trades 수 많으면 두 번 루프 | `_FeatureBundle`에 `trade_count` 필드 추가하거나 `window_trades`를 번들로 반환 |
| 15 | `services/profile/group_benchmark.py:559-579` | Low — per-ticker 반복 import | `_ticker_to_sector()` 내부(L569)에서 매 호출마다 `from services.kr_stock_registry import get_sector` 동적 임포트 수행. `_sector_distribution`이 Position 목록 전체를 순회하므로 포지션 수만큼 반복 import try-except 실행 | 동적 import는 첫 호출 이후 sys.modules에서 캐시되나, try-except 블록 자체는 매번 실행됨 | 모듈 레벨에서 `_kr_sector` 한 번 import 시도 후 결과를 캐시. `_ticker_to_sector` 반복 시 재시도 불필요 |

---

## Phase 3 — 우선순위 정렬

### High (즉시 대응 권장 — 요청마다 발생)

1. **#4** `group_benchmark._all_users_baseline` 8회 중복 — cron 배치에서 TradeHistory 전체를 9회 로드. 배치 단일 실행 시 데이터가 클수록 선형 비용 증가.
2. **#1** `classify_persona_multi` wrapper 재계산 — 동일 분류를 호출마다 반복. `/api/profile/persona-explain`은 전체 9-dim 계산을 tooltip용으로 재실행.
3. **#3** `_user_ids_for_persona` 전체 테이블 로드 후 Python 필터 — SQL에서 처리해야 할 작업을 Python에서 수행.
4. **#8** `get_persona_benchmark_all` N+1 — 8개 persona별 추가 쿼리.

### Med (단기 개선)

5. **#5** FIFO 로직 중복 — 코드 중복 + 배치 per-user 처리 비용.
6. **#7** `get_persona_benchmark` 중복 PersonaGroupStats 조회.
7. **#9** KISService 반복 인스턴스화.
8. **#6** import-time `_audit_all` 반복 — 로직은 정확하나 정적 데이터 재검증 불필요.

### Low (선택적 개선)

9. **#2** pulse/feedback per-request 쿼리 — 인덱스 존재 시 큰 문제 아님.
10. **#10~#15** 미세 최적화 — 실제 부하 측정 후 판단.

---

## 에스컬레이션

**불필요** — P0 보안/아키텍처 위반 없음.

주목할 설계 경계: `_all_users_baseline`의 주석(group_benchmark.py L294)이 "session identity map에서 캐시한다"고 명시하나 이는 사실이 아님 — SQLAlchemy identity map은 동일 세션 내 동일 PK 행을 캐시하지만, `filter(traded_at >= cutoff)` 결과집합 전체를 캐시하지 않음. 주석이 실제 동작을 오해하게 만드는 misleading comment임. engineering에게 전달 권장.

---

## Checklist 결과

- null-safe: API 응답 try-except — 모든 route handler에 예외 처리 존재 (PASS)
- TypeScript strict `any` 0개 — engine-models-drawer / useFocusTrap 기준 (PASS)
- 에러 핸들링 폴백 — Flask routes 전체 500 fallback 존재 (PASS)
- 기존 코드 보존 — 추가 파일, 덮어쓰기 없음 (PASS)
- 모바일 375px — engine-models-drawer bottom sheet 구현됨 (PASS)
- 숫자 포맷 — `round()` 2자리 일관 적용 (PASS)
- console.log — 없음 (PASS)
- 하드코딩 URL/키 — os.environ 사용, 단 `search_stocks` 내부 request-level env 조회 (#10) (CONDITIONAL)
- N+1 — #8 발견 (FAIL — 수정 권장)
- Hot-path compute — #1 #4 발견 (FAIL — 수정 권장)

**판정: CONDITIONAL** — 기능 정확성과 법적 안전성은 PASS. 효율성 이슈 15건 중 High 4건은 개선이 권장됨.
