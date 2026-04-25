# Simplify / Reuse Audit — 2026-04-24

**Auditor**: audit-code (Sonnet 4.6)
**Scope**: 이번 세션 추가/대폭 수정 파일 9개
**Working dir**: `/Users/seanbae/Desktop/취준/stockpilot`
**Status**: COMPLETE

---

## Summary

총 **14개 finding**, 심각도별 분류:

| 심각도 | 건수 |
|--------|------|
| High   | 4    |
| Med    | 7    |
| Low    | 3    |

---

## Phase 1 — 기존 유틸 중복 검사

### Finding Table

| # | 파일:줄 | 중복 패턴 | 대체 위치 | 제안 |
|---|---------|-----------|-----------|------|
| 1 | `services/profile/group_benchmark.py:405–435` | `_avg_holding_days` — FIFO BUY/SELL 매칭 + 평균 보유일 계산 | `services/profile/persona_analytics.py:295` (`_avg_holding_period`) | `group_benchmark._avg_holding_days`를 삭제하고 `persona_analytics._avg_holding_period` import해서 사용. 반환 타입 차이(float vs float\|None)만 래핑하면 됨 |
| 2 | `services/profile/group_benchmark.py:452–481` | `_user_mistakes` 내부의 2차 FIFO 루프 (disposition 계산용) — 동일한 `opens.setdefault / remaining > 1e-9 / queue.pop(0)` 패턴 | `services/profile/persona_analytics.py:295` | finding #1과 동일. 공통 `_fifo_hold_pairs(trades) -> list[tuple[float, bool]]` 추출 후 두 함수가 공유 |
| 3 | `services/profile/rolling_metrics.py:174–205` | `_holding_period_days` — 또 하나의 FIFO 구현. `persona_analytics._avg_holding_period`와 로직 98% 동일 (열 이름·타입 캐스팅 포함) | `services/profile/persona_analytics.py:295` | `rolling_metrics._holding_period_days` 삭제 후 `_avg_holding_period` 재사용. 차이점(fallback ref 기준: `datetime.utcnow()` vs `trades[-1].traded_at`) 통일 필요 |
| 4 | `services/profile/persona_classifier_v2.py:240–270` | `_hold_time_cv` 내부 FIFO 루프 — `_avg_holding_period`와 동일 구조. 단 pair 목록이 필요하고 CV 계산이 추가됨 | `services/profile/persona_analytics.py:295` | finding #1 대책 적용 후 공통 `_fifo_pairs` 사용. CV는 pair 결과 위에 2줄로 계산 가능 |
| 5 | `services/profile/group_benchmark.py:559–579` | `_ticker_to_sector` — `kr_stock_registry.get_sector` lazy import + UNKNOWN fallback | `services/profile/persona_analytics.py:213` (`_sector_map_from_positions`) | 두 함수의 kr_stock_registry 호출 패턴이 동일. `persona_analytics._sector_map_from_positions`를 ticker→sector 단일 해결 진입점으로 지정하고, `group_benchmark`는 positions를 먼저 조회한 뒤 이 함수를 재사용 |
| 6 | `services/profile/rolling_metrics.py:213–229` | `_sector_tilt_hhi` — HHI 계산 (`volume_by_sector`, `sum((v/total)^2)`) | `services/profile/persona_analytics.py:331` (`_sector_diversification`) | 로직 동일. 유일한 차이: `rolling_metrics`는 `1 - hhi`를 반환하지 않고 raw HHI를 반환(주석에 "frontend treats higher = more tilt" 명시). 이 의미 반전은 `persona_analytics._sector_diversification`에 파라미터 `invert=True` 추가로 통합 가능 |

**소계: 6건, High(4) + Med(2)**

---

## Phase 2 — Hand-rolled 로직 탐지

| # | 파일:줄 | 중복/핸드롤 패턴 | 대체 위치 | 제안 |
|---|---------|-----------------|-----------|------|
| 7 | `services/profile/persona_classifier_v2.py:541–542`<br>`services/profile/rolling_metrics.py:239–240`<br>`services/profile/group_benchmark.py:642–643`<br>`services/profile/persona_analytics.py:430–431` | `_utc_now()` 동일 1줄 함수가 **4개 파일**에 중복 | `services/profile/__init__.py` 또는 새 `services/profile/_utils.py` | 한 곳에 정의(`_utils.py:_utc_now`) 후 4개 파일에서 import. 3줄 절감 × 3파일 |
| 8 | `services/artifacts/pre_trade_checklist_service.py:335–374`<br>`services/artifacts/persona_warnings.py:226–254` | `_FORBIDDEN_TERMS` + `_assert_legal_safe` + `_audit_all` 패턴이 두 파일에 각각 독립 구현. checklist 버전(344 terms)과 warnings 버전(233 terms)이 거의 동일 | `services/legal_filter.py` | `legal_filter.py`에 `assert_legal_safe(text, where)` 공개 함수 추가 후 두 모듈이 import. `_FORBIDDEN_TERMS` 두 개를 합집합으로 통일. import-time audit은 각 모듈에서 유지(각자 다른 copy를 심사하므로) |
| 9 | `routes/market.py:80–81` | `import os` + `os.environ.get("FMP_API_KEY", "")` 를 라우트 핸들러 내부에서 직접 호출 | `fmp_service.py:18` (`FMP_KEY = os.environ.get(...)`) | `fmp_service.FMP_KEY` 또는 `fmp_service.is_configured()` 사용. `import os`를 라우트에서 제거 |
| 10 | `services/profile/group_benchmark.py:327–337` | `_realised_pnls` — `(t.action or "").upper() != "SELL"` + `float(t.pnl_pct or 0.0)` + finite 체크 | `services/profile/persona_classifier_v2.py:273–324` (`_loss_cut_discipline`) 안에도 동일한 SELL 필터링 패턴 존재 | 공통 `_sell_trades(trades) -> list[TradeHistory]` 헬퍼 추출 |
| 11 | `services/profile/rolling_metrics.py:232–236` | `_round_float` — `round(float(value), ndigits)` try/except 래퍼 | Python 내장. `round(float(x or 0), n)` 패턴으로 충분 | `_round_float` 삭제 후 호출부 인라인. 3개 호출 위치(L158–160) 모두 단순 치환 가능 |
| 12 | `services/profile/group_benchmark.py:634–639` | `_finite` — `math.isnan / math.isinf` 체크 | 동일 파일의 `_safe_median`에서만 사용. Python `math.isfinite(x)` 단일 함수로 대체 가능 | `_finite(x)` 삭제. `_safe_median` 내부 `if _finite(v)` → `if math.isfinite(v)` |
| 13 | `models/persona_group_stats.py:41–44` | `VALID_PERSONAS = (...)` 8 코드 튜플 — "must stay in sync with services/profile/persona_analytics.PERSONA_CODES" 주석 명시 | `services/profile/persona_analytics.py:45` (`PERSONA_CODES`) | 모델 레이어에서 analytics import는 순환 import 위험이 있으나, `models/persona_group_stats.py`가 analytics를 import하지 않고 있음. 대신 `models/__init__.py`에서 `VALID_PERSONAS = PERSONA_CODES` alias 형태로 한 번만 정의하고 다른 쪽에서 import. 또는 현상 유지 + 테스트로 동기화 보장 (Low) |

**소계: 7건, Med(5) + Low(2)**

---

## Phase 3 — 추가 관찰

| # | 파일:줄 | 관찰 | 제안 |
|---|---------|------|------|
| 14 | `services/artifacts/persona_resolver.py:34–39`<br>`services/agents/persona_adapter.py:47–52`<br>`services/agents/journal_companion.py:46–55` | `VALID_PERSONAS` frozenset이 **3개 파일**에 독립 정의. `persona_resolver.py`에 "Must match services.agents.persona_adapter.VALID_PERSONAS" 주석, `persona_adapter.py`에도 동일 주석. 실제 동기화가 테스트로 보장되지 않음 | `persona_resolver.VALID_PERSONAS`를 SSOT로 지정하고 나머지 두 파일이 import. 단, agents 레이어가 artifacts 레이어를 import하는 방향이 적절한지 아키텍처 검토 필요 |

**소계: 1건, Low**

---

## 심각도 분류 기준 및 판정 요약

| # | Finding | 심각도 | 근거 |
|---|---------|--------|------|
| 1 | `_avg_holding_days` vs `_avg_holding_period` 중복 | **High** | 버그 fix 시 4곳 중 하나만 수정될 위험. FIFO 로직은 금전 계산에 직결 |
| 2 | `_user_mistakes` 내부 2차 FIFO | **High** | 동일 |
| 3 | `rolling_metrics._holding_period_days` 중복 | **High** | fallback 기준(`datetime.utcnow()` vs `trades[-1].traded_at`)이 달라 결과값 불일치 위험 |
| 4 | `_hold_time_cv` FIFO | **High** | 동일 |
| 5 | `_ticker_to_sector` vs `_sector_map_from_positions` | **Med** | 행동 일치하나 로직이 분산. 미래 registry 변경 시 2곳 수정 필요 |
| 6 | `_sector_tilt_hhi` vs `_sector_diversification` | **Med** | HHI 계산 동일, 반환 방향만 다름. 통합 가능하나 의미 반전 주의 필요 |
| 7 | `_utc_now` 4중 정의 | **Med** | 무해하나 불필요한 반복 |
| 8 | `_assert_legal_safe` 2중 정의 | **Med** | 두 버전의 금지 목록이 서로 다름 (checklist: 11개, warnings: 12개). 통일 필요 |
| 9 | `os.environ.get("FMP_API_KEY")` 직접 호출 | **Med** | `fmp_service.FMP_KEY`가 SSOT. 라우트에서 직접 접근은 config 위반 |
| 10 | `_sell_trades` 헬퍼 미추출 | **Med** | SELL 필터링 패턴 반복 |
| 11 | `_round_float` 과설계 | **Low** | 3줄 try/except가 `round(float(x or 0), n)` 1줄로 충분 |
| 12 | `_finite` 헬퍼 | **Low** | `math.isfinite` 내장으로 대체 가능 |
| 13 | `VALID_PERSONAS` 모델 레이어 중복 | **Low** | 주석이 sync 책임을 인정하고 있음. 현상 유지 허용이나 테스트 추가 권장 |
| 14 | `VALID_PERSONAS` 3개 파일 독립 정의 | **Low** | SSOT 없음. 아키텍처 방향 결정 필요 |

---

## 체크리스트 결과

- [x] null-safe API 응답: 모든 서비스 함수 try/except + 빈 리스트/0 폴백 ✅
- [x] TypeScript strict any: `page.tsx` 내 `any` 0개 (`unknown` 사용, L455) ✅
- [x] 에러 핸들링: 라우트 모두 try/except + rollback ✅
- [x] 기존 코드 보존: v1 `compute_persona_response` 미수정 확인 ✅
- [x] console.log 제거: profile/page.tsx 내 없음 ✅
- [x] 하드코딩 URL/키: `routes/market.py:80` `os.environ.get("FMP_API_KEY")` 직접 접근 **[Finding #9]** ⚠️
- [x] 숫자 포맷: `_round_float` / `round(float(...))` 일관 사용 ✅
- [x] FIFO 중복: **4개 파일**에 동일 알고리즘 **[Finding #1–4]** ⚠️

---

## Status: COMPLETE

- 총 14개 finding 식별
- 코드 수정 없음 (read-only 분석)
- 에스컬레이션: **불필요** (P0 보안/아키텍처 위반 없음. P1 이하 전부)

