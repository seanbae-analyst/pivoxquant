# Code Quality Audit — SIMPLIFY_QUALITY_2026-04-24

Auditor: audit-code agent (2차 교차검증)
Date: 2026-04-24
Scope: 10 files — persona_classifier_v2.py, group_benchmark.py, pre_trade_checklist_service.py, persona_warnings.py, routes/profile.py, routes/market.py (_kis_index_snapshot section), profile/page.tsx, engine-models-drawer.tsx, report-flip-card.tsx, useFocusTrap.ts

---

## Summary

총 20개 finding. P1(즉시 위험) 2건, P2(품질 이슈) 11건, P3(개선 제안) 7건.

Phase 2 위험 패턴 중 `_audit_all()` import-time 실행은 **의도된 설계** (import 시 법적 용어 사전 검증)로, 단순 제거는 불가. 단, 구체 예외 좁히기와 매직 넘버 추출은 수정 가능.

---

## Phase 1 — Hacky 패턴

| # | 파일:줄 | 카테고리 | 심각도 | 수정 제안 |
|---|---------|----------|--------|-----------|
| 1 | `report-flip-card.tsx:85–213` vs `488–596` | Copy-paste with variation | P2 | `FrontFace` (3D용)와 `FrontFaceContent` (reduced-motion용)가 JSX 구조를 거의 동일하게 중복. icon/heading/excerpt/footer 블록이 두 곳에 존재. 두 브랜치를 단일 `<FrontBody>` 컴포넌트로 추출하고 `tabIndex`/`aria-hidden`만 파라미터로 받으면 약 100줄 제거 가능 |
| 2 | `report-flip-card.tsx:228–355` vs `598–712` | Copy-paste with variation | P2 | `BackFace`와 `BackFaceContent`도 동일 패턴. paper-grain overlay div, kicker/heading/lede/bullets/closer 구조가 이중 유지됨. `<BackBody>` 추출로 해결 |
| 3 | `engine-models-drawer.tsx:649–735` | Unnecessary JSX nesting | P3 | `DrawerContent` 내 `<section>` 3개 (`what it measures`, `how it enters`, `reference`) 모두 동일한 `h4`+`p` 구조. `<MethodSection label={...}>{content}</MethodSection>` 단일 컴포넌트로 추출하면 반복 제거. 현재 각 section이 `mb-6`+`font-serif uppercase` 스타일을 복붙 |
| 4 | `engine-models-drawer.tsx:503–558` | Stringly-typed | P3 | `CATEGORIES` 배열의 `key` 필드가 `Category` union type과 이중 관리됨. `CATEGORIES`가 `ModelDef[]`를 derive해서 count를 계산하면 `count: 16` 같은 하드코딩 제거 가능 (현재 MODEL_DEFS 필터로 `models.length` 구하지만 CATEGORIES.count는 별도 숫자로 하드코딩) |
| 5 | `routes/profile.py:174–180` vs `300–306` | Copy-paste with variation | P2 | `submit_onboarding`과 `update_profile` 양쪽에서 profile 필드를 동일한 순서로 `answers.get(...)` 할당. 공통 `_apply_answers(profile, answers)` 헬퍼로 추출 가능 |
| 6 | `routes/profile.py:597–603` | Redundant state | P2 | `submit_pulse`에서 `cadence` 미입력 시 DB 조회로 최근 값을 가져옴. 이 조회는 `GET /pulse` 에서도 동일하게 수행됨. 프론트가 `GET /pulse` 응답의 `cadence`를 POST body에 포함시키면 서버 조회 제거 가능. 현재는 POST에서 추가 쿼리가 발생 |
| 7 | `routes/market.py:117–134` | Global mutable state + 함수 내 상수 | P2 | `_US_POPULAR` dict가 FMP 실패 시마다 함수 내부에서 재생성됨 (line 117). 모듈 레벨 상수로 올리면 GC 부담 제거 |
| 8 | `services/profile/group_benchmark.py:559–579` | Leaky abstraction | P2 | `_ticker_to_sector`가 `from services.kr_stock_registry import get_sector` 를 **호출마다** lazy import. 이 패턴은 Position 수만큼 반복 import 시도를 유발. 모듈 레벨에서 한 번 import-or-None 처리 후 모듈 변수로 캐싱하면 해결 |
| 9 | `services/profile/group_benchmark.py:264–289` | Parameter sprawl | P3 | `_aggregate_metrics(user_ids, cutoff, window_days, persona)` — 4개 파라미터이나 `cutoff`는 `window_days`에서 직접 유도 가능. `now` 참조가 이미 호출부에 있으므로 `cutoff` 전달 대신 내부에서 계산하거나 dataclass로 묶어 전달 |
| 10 | `profile/page.tsx:49–58` | Stringly-typed | P3 | `INVESTOR_TYPE_LABELS` Record가 profile/page.tsx 내부에 로컬 선언됨. 동일 매핑이 다른 파일에서도 필요해질 경우 중복 발생. `lib/cfo/hooks.ts`의 `PERSONA_LABELS` 패턴처럼 `lib/`으로 이동 권장 |
| 11 | `profile/page.tsx:592–598` | Stringly-typed | P3 | `tier` → `tierLabel` 변환 로직이 page.tsx 내 인라인. "pro"/"operator"/"premium"/"partner" 등의 raw tier 문자열이 직접 비교됨. tier enum 또는 helper가 없으면 백엔드 tier 값 변경 시 UI만 깨짐 |

---

## Phase 2 — 위험 패턴

| # | 파일:줄 | 패턴 | 심각도 | 수정 제안 |
|---|---------|------|--------|-----------|
| 12 | `pre_trade_checklist_service.py:374` | `_audit_all()` import-time 실행 | P1 | 의도된 법적 방어선이므로 제거는 금지. **단, 실행이 `_PERSONA_SPECIFIC` 구축 완료 이전에 트리거될 경우 `NameError` 가능**. 현재 `_audit_all()` 호출이 모듈 레벨 assert (319–325줄) 이후에 위치하므로 순서는 안전. 그러나 모듈이 다른 곳에서 부분 import될 경우 예외가 전파됨. try/except로 감싸서 `ImportError` 대신 `ValueError`로 명시 재전파 권장: `try: _audit_all() except ValueError: raise` |
| 13 | `persona_warnings.py:254` | `_audit_all()` import-time 실행 | P1 | 동일. `_TEMPLATES`와 `_GENERIC` 구축 완료 후에 위치하므로 순서는 안전. 단, `_assert_legal_safe` 내부에서 `ValueError`를 raise하는데 import-time에 발생하면 `ModuleNotFoundError`가 아닌 `ValueError`로 앱이 시작 불가. 이 의도가 맞다면 현재 설계 OK — 단, 앱 로그에 traceback이 숨겨질 수 있으므로 `logger.critical` + re-raise 패턴 추천 |
| 14 | `routes/profile.py:193, 272, 319, 487, 634` | `except Exception` 광범위 포획 | P2 | DB commit 실패의 경우 `sqlalchemy.exc.SQLAlchemyError`로 좁혀야 함. 현재 `Exception`은 `KeyboardInterrupt`를 제외한 모든 예외를 포획 (Python 3에서 `KeyboardInterrupt`는 `BaseException` → 실제론 포획 안 됨). 의미있는 변경: `except sqlalchemy.exc.SQLAlchemyError` |
| 15 | `routes/market.py:91, 112` | `except Exception` — 광범위 포획 | P2 | FMP search 실패 처리. `requests.exceptions.RequestException`으로 좁혀야 네트워크 오류와 프로그래밍 오류를 구분 가능. 현재는 `AttributeError` 등 버그도 조용히 삼킴 |
| 16 | `services/profile/persona_classifier_v2.py:203–204, 417–419` | Magic number | P2 | `cv / 1.5` (CV 상한 정규화), `margin * 12.0` (margin 스케일), `0.35 + 0.5 * margin_score + 0.4 * ...` (confidence blend 계수) 가 설명 주석은 있으나 named constant 미사용. `_CV_CEILING = 1.5`, `_MARGIN_SCALE = 12.0`, `_CONF_BASE = 0.35`, `_CONF_MARGIN_W = 0.5`, `_CONF_EVIDENCE_W = 0.4` 로 추출 권장 |
| 17 | `services/profile/group_benchmark.py:494` | Magic number | P2 | `if avg_loss >= (avg_win * 1.5)` — 1.5 배수가 disposition effect 판정 기준이나 named constant 없음. `_DISPOSITION_RATIO_THRESHOLD = 1.5` 로 추출 |
| 18 | `services/profile/group_benchmark.py:506` | Magic number | P2 | `if len(tickers) >= 2` (herding: 하루 2개 이상 ticker), `if herding_days >= 3` (3일 이상) — 두 임계치 모두 named constant 없음. `_HERDING_MIN_TICKERS_PER_DAY = 2`, `_HERDING_MIN_DAYS = 3` 추출 권장 |
| 19 | `services/profile/group_benchmark.py:295–296` | Comment-as-cache: 잘못된 설명 | P3 | "We cache the result on the SQLAlchemy session identity" 주석이 있으나 실제로 `_all_users_baseline`는 캐싱 없이 매 호출마다 전체 TradeHistory 조회. `compute_all_personas`가 8회 호출 시 baseline이 8번 쿼리됨. 주석이 거짓 — 실제 캐싱 미구현. 주석 수정 또는 실제 캐싱 구현 필요 |

---

## Phase 3 — 개선 제안 (추가)

| # | 파일:줄 | 패턴 | 심각도 | 수정 제안 |
|---|---------|------|--------|-----------|
| 20 | `engine-models-drawer.tsx:754–769` | Redundant state | P3 | `isDesktop` state와 `desktopTrapRef` / `mobileTrapRef` 두 개의 focus trap ref를 동시에 유지. 실제로 활성화되는 trap은 하나뿐. 단일 `activeTrapRef = isDesktop ? desktopTrapRef : mobileTrapRef`로 사용하면 충분하지만, Tailwind `hidden/md:flex`와 쌍을 이루는 현재 구조상 리팩터는 레이아웃 변경 동반. 현재는 기능 정확하나 trap 2개가 항상 마운트 상태임 |

---

## 통과 항목 (양호)

- `useFocusTrap.ts` — 단일 책임, 43줄, 클린. `data-focus-skip` 이스케이프 해치 포함. PASS
- `persona_classifier_v2.py` — `_FeatureBundle` dataclass 사용, FEATURE_KEYS 순서 명시, `__all__` 관리. 전반적으로 양호
- `pre_trade_checklist_service.py:96–316` — `_UNIVERSAL`/`_PERSONA_SPECIFIC` 분리, frozen dataclass 사용, 데이터-로직 분리. PASS
- `persona_warnings.py` 전체 — template dict 분리, generic fallback, try/except 내 stats 포맷팅. PASS
- `routes/profile.py` — Layer 2 엔드포인트 모두 HTTP 200 보장 계약 명시적 문서화. PASS
- `group_benchmark.py` — MIN_GROUP_SIZE, VALID_PERSONAS, VALID_WINDOWS를 models에서 임포트. 매직 넘버 대신 모델 상수 활용 패턴은 양호

---

## Checklist 요약

- [x] null-safe: API 응답 try-catch 처리 — 모두 존재 (단, 광범위 포획 개선 필요)
- [x] 기존 코드 보존: 덮어쓰기 없이 추가만 했는가 — 확인됨
- [ ] TypeScript strict: any 타입 — `engine-models-drawer.tsx:569`의 kr_stock_registry import시 `_kr_sector = None  # type: ignore[assignment]` (Python, 허용 가능)
- [ ] Magic number 없음 — Finding #16, 17, 18 참조
- [ ] copy-paste 최소화 — Finding #1, 2, 3 참조
- [ ] Leaky abstractions — Finding #8 참조 (per-call lazy import)
- [ ] 허위 주석 없음 — Finding #19 참조 (캐싱 주석 불일치)

## Status: COMPLETE

총 finding 20개. P1 2건(import-time 실행 — 의도 설계이나 로깅 강화 권장), P2 11건, P3 7건.
코드 수정은 engineering 위임 필요.
