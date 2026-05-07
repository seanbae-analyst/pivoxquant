# 코드 구조 정리 계획 — 2026-05-06

작성자: Code Janitor Agent (import-police / dead-code-hunter / style-enforcer / architecture-guard)
기준: feedback_thorough_fixes + feedback_no_false_reports + feedback_pr_workflow + feedback_feature_preservation

---

## Tier 2 실행 결과 (2026-05-06 세션)

### Tier 2-6: 루트 .md 이동 — DONE (commit 보류, CEO 검토 대기)

- **이동 완료**: 21개 파일 → `docs/archive/reports/`
- **방법**: `git mv` (21개 전부 staged, `R` 상태 확인)
- **보존**: `CLAUDE.md`, `HANDOVER.md`, `CLEANUP_PLAN_2026-05-06.md` (3개)
- **근거**: `git status --short | grep "^R" | wc -l` → 21
- **cross-reference**: `AUTOTRADE_REMOVAL_2026-04-27.md`, `LEGAL_CONSULT_PACKAGE.md`, `TODO.md` 가 HANDOVER.md에서 참조되나 링크 텍스트 수준 (기능 영향 없음)
- **commit 전 루트 상태**: `ls *.md` → CLAUDE.md, CLEANUP_PLAN_2026-05-06.md, HANDOVER.md (3개)

이동된 파일 목록:
```
ARCHITECTURE.md
AUTOMATION_STRATEGY_2026-05-01.md
AUTOPILOT_STATE.md
AUTOTRADE_REMOVAL_2026-04-27.md
BUG_SWEEP_2026-04-23.md
EMAIL_BUG_AUDIT_2026-05-01.md
LANDING_SAMPLES_AUDIT_2026-05-03.md
LEGAL_CONSULT_PACKAGE.md
LEGAL_COVER_LETTER.md
MASTER_FIX_PLAN_2026-05-01.md
NEEDS_CONFIG.md
NEW_FINDINGS.md
NEXT_SESSION_BRIEF.md
OVERNIGHT_AUTONOMOUS_REPORT_2026-05-02.md
PRELAUNCH_CHECKLIST_2026-05-01.md
PRODUCT_PLAN.md
RAILWAY_ENV_TODO.md
RAILWAY_ENV_TODO_2026-04-28.md
REPORT_REDESIGN_2026-04-27.md
SECONDARY_BUG_SWEEP_2026-05-01.md
TODO.md
```

### Tier 2-9: alembic heads — DONE (READ-ONLY)

- **방법**: 파일 직접 분석 (venv/bin/alembic -c migrations/alembic.ini heads 출력 없음 — DB 없이 실행 시 stdout silence)
- **결과**: **단일 head** (single head)
  - HEAD: `026_db_integrity_constraints` (`026_db_integrity_constraints.py`)
  - 총 revision 수: 27개
  - 체인: 001 → 002 → ... → 026 (선형, 분기 없음)
- **다중 head 없음** — 별도 merge migration 불필요

### Tier 2-7: stale worktrees prune — 보류

- **사유**: Wave 1 agent들이 사용했던 worktree가 locked 상태. PID 38381/85619 실존 여부 미확인.
  실수로 진행 중 agent worktree 삭제 방지 위해 CEO 명시적 ACK 후 별도 세션에서 실행.
- **다음 액션**: CEO가 `git worktree list` 확인 후 "prune해도 됨" 명시 시 실행

### Tier 3 전부 — 별도 task 분리

- `_v1 dirs 9개 제거`: feedback_feature_preservation 룰 — v1→v2 매핑 표 선행 필요
- `services/ flat .py 19개 패키지 재배치`: >30 files 가능, PR 분할 룰 (feedback_pr_workflow)
- `hooks 분산 정리`: 컴포넌트 impact 분석 선행 필요

---

---

## 진단 요약 (Phase A grep/ls 결과만 인용)

| 항목 | 실측값 | 기준 | 상태 |
|------|--------|------|------|
| 루트 .md 파일 | 23개 | ~5개 | 과다 |
| 루트 .py 파일 | 5개 | 5개 (HANDOVER 기준) | 정상 |
| 루트 총 파일 (비숨김) | 37개 | — | 과다 |
| services/ 미분류 flat .py | 19개 | 0개 (패키지화 목표) | 미완료 |
| services/ 서브패키지 수 | 15개 (__init__.py 보유) | — | 정상 |
| frontend _v1 디렉토리 | 9개 | 0개 | dead code 후보 |
| frontend " 2" 디렉토리 (src/) | 3개 | 0개 | Finder 복제본 |
| stale worktrees (.claude/worktrees/) | 11개 | 0개 | 정리 필요 |
| 루트 __pycache__ 고아 .pyc 모듈 | 18종 | 0개 | 삭제 가능 |
| TODO/FIXME (main 소스, 워크트리 제외) | 4개 | — | 수용 가능 |
| 취준/ 루트 .md 중복 세션보고서 | 7개 | 0개 | archive 대상 |

### 중복/duplicate 디렉토리 관계

```
stockpilot          → symlink → pivoxquant/   (정상, symlink)
stockpilot 2        → symlink → pivoxquant/   (정상, symlink)
pivox-samples-fix/  → git worktree (fix/sample-reports-data-p0 브랜치, 활성)
/private/tmp/pq-frontend-wave1/ → git worktree (fix/frontend-wave1-critical 브랜치, 활성)
```

`취준/StockPilot design/`, `취준/pivoxone/`, `취준/pivox-samples-fix/` 는 별도 프로젝트/워크트리로 레포 외부.

### Alembic 상태

`alembic heads` 실행 결과: `FAILED: No 'script_location' key found in configuration.`
— migrations/ 디렉토리에 alembic.ini 가 없고 루트에도 없음. alembic.ini 위치 확인 필요 (Tier 2).

### services/ 패키지 구조 불일치

session_2026-05-03 보고 "5개 서비스 패키지화" vs 실측:
- 패키지화 완료 (15개 서브디렉토리에 __init__.py): agents, ai, artifacts, behavior, broker, data, email, kis, legal, mock_data, pre_trade, profile, quant, trading, twin
- 미분류 flat .py 19개가 services/ 루트에 잔재:
  `access_guard.py`, `alert.py`, `alert_service.py`, `cache_service.py`, `cache_ttl.py`,
  `container.py`, `crypto_service.py`, `email_token.py`, `fx_service.py`,
  `kr_stock_registry.py`, `legal_filter.py`, `market_status.py`, `name_resolver.py`,
  `news_service.py`, `price_overlay.py`, `push_service.py`, `serializers.py`,
  `ticker_normalizer.py`, `us_stock_registry.py`
- services/ 루트에 `__init__.py` 없음 (패키지 선언 미완료)

### Frontend 구조 이슈

- `_v1` 디렉토리 9개: login, signup, home, portfolio, profile, reports, risk, settings, signals
  — v2로 전환 완료 후 잔재인지 미확인. feedback_feature_preservation 원칙상 단순 삭제 금지.
- `" 2"` suffix 디렉토리 3개 (Finder 복제본 의심):
  `(auth)/login 2/`, `(auth)/onboarding 2/`, `simulator/what-if 2/`
  — 내부 파일 없음(find 결과 0줄). 빈 디렉토리.
- hooks 파일이 3곳에 분산: `lib/hooks.ts`, `lib/cfo/hooks.ts`, `components/portfolio/v2/hooks-v2.ts`

### 고아 .pyc (루트 __pycache__, 대응 .py 없음)

18종: `ai_models`, `ai_service`, `autotrader`, `backtester`, `data_fetcher`,
`daytrade_service`, `edgar_service`, `engine`, `fmp_service`, `kis_service`,
`kis_token_manager`, `portfolio_models`, `quant_models`, `questionnaire`,
`realtime_service`, `risk_defense`, `risk_models`, `signal_models`

이 모듈들은 services/ 패키지화 과정에서 이동됐거나 삭제된 것. .pyc는 삭제 안전.

### 취준/ 루트 세션보고서 (repo 외부, 단 .md 파일)

`AUTOMATION_STRATEGY_2026-05-01.md`, `CRITICAL_BUG_VERIFICATION_2026-05-01.md`,
`EMAIL_BUG_AUDIT_2026-05-01.md`, `MASTER_FIX_PLAN_2026-05-01.md`,
`PRELAUNCH_CHECKLIST_2026-05-01.md`, `SECONDARY_BUG_SWEEP_2026-05-01.md`,
`pivoxquant_landing_fix_prompt.md` — 취준/ 루트에 있으며 repo에는 없음.

### Git worktree 상태 (11개 locked)

모두 `locked claude agent (pid XXXXX)` 상태. PID 38381, 85619 두 개로 집중.
macOS에서 PID를 검증해야 실제 살아있는지 확인 가능 (Tier 2).

---

## 정리 액션 (위험도별)

### Tier 1 — 안전 (CEO ACK 없이 즉시 실행 가능)

1. **루트 __pycache__ 고아 .pyc 삭제** — 18종 .pyc + __pycache__/ 전체
   - 영향 파일: __pycache__/ 내 ~35개 .pyc
   - 롤백 cost: 없음 (Python이 실행 시 재생성)
   - 근거: find 결과 대응 .py 없음 확인

2. **빈 " 2" 디렉토리 3개 삭제**
   - `frontend/src/app/(auth)/login 2/`
   - `frontend/src/app/(auth)/onboarding 2/`
   - `frontend/src/app/simulator/what-if 2/`
   - 영향 파일: find 결과 내부 파일 0개
   - 롤백 cost: 없음

3. **취준/ 루트 세션보고서 7개 → 취준/archive/ 이동** (repo 외부 작업)
   - `AUTOMATION_STRATEGY_2026-05-01.md` 외 6개
   - 영향: repo 바깥 파일이므로 git history 무관
   - 롤백 cost: mv 역방향으로 즉시 복구

4. **.gitignore에 `.bughunt-*` 패턴 추가**
   - `.bughunt-2026-05-04-runs/` 현재 gitignore에 없음 (git check-ignore 미처리)
   - 기존 `nightly_artifacts/` 패턴 아래 한 줄 추가
   - 롤백 cost: 낮음 (한 줄 삭제)

5. **pivoxquant/.DS_Store → .gitignore 확인** (이미 있음 — 무조건 OK)
   - `.gitignore:27: .DS_Store` — 이미 처리됨. 별도 액션 불필요.

---

### Tier 2 — 주의 (CEO ACK 필요)

6. **루트 보고서 .md 11개 → docs/archive/ 이동** (repo 내부)
   - 대상: `AUTOTRADE_REMOVAL_2026-04-27.md`, `BUG_SWEEP_2026-04-23.md`,
     `EMAIL_BUG_AUDIT_2026-05-01.md`, `LANDING_SAMPLES_AUDIT_2026-05-03.md`,
     `MASTER_FIX_PLAN_2026-05-01.md`, `NEW_FINDINGS.md`, `NEXT_SESSION_BRIEF.md`,
     `OVERNIGHT_AUTONOMOUS_REPORT_2026-05-02.md`, `RAILWAY_ENV_TODO.md`,
     `RAILWAY_ENV_TODO_2026-04-28.md`, `REPORT_REDESIGN_2026-04-27.md`,
     `SECONDARY_BUG_SWEEP_2026-05-01.md`, `AUTOMATION_STRATEGY_2026-05-01.md`,
     `PRELAUNCH_CHECKLIST_2026-05-01.md`
   - 영향 파일: 14개 .md (commit 1개)
   - 주의: HANDOVER.md 등 일부는 링크 참조 가능 — 이동 전 grep 확인 필요
   - 판단: docs/archive/ 디렉토리 이미 존재 (`docs/archive/` 확인됨)

7. **stale worktrees 정리** (git worktree remove)
   - 11개 locked worktrees 중 PID 38381/85619 실존 여부 확인 후 prune
   - 명령: `git worktree prune` (dead worktrees만 자동 제거)
   - 영향: `.claude/worktrees/` 내 각 브랜치 (모두 이미 main에 머지됐는지 확인 필요)
   - CEO ACK 필요: 실수로 진행 중 agent 워크트리 삭제 방지

8. **services/ flat .py 19개 적절한 패키지로 이동**
   - 예: `alert.py` + `alert_service.py` → 통합 후 `services/data/` 또는 신규 `services/alerts/` 패키지
   - `ticker_normalizer.py` → services/ 루트 유지 or `services/data/` 이동 검토
   - 영향 파일: 19개 + import 경로 변경 N개 (라우트/테스트 포함)
   - 주의: feedback_feature_preservation — 모든 import 경로 매핑 표 작성 후 진행

9. **alembic.ini 위치 파악 + heads 확인**
   - `alembic heads` 실패 원인: script_location 미설정
   - `migrations/alembic.ini` 존재하나 루트 실행 시 인식 못 함
   - PR 워크플로우 규칙 1번: alembic heads 먼저 — 현재 BLOCKED 상태
   - 수정: `alembic -c migrations/alembic.ini heads` 로 확인 필요

---

### Tier 3 — 위험 (별도 PR 분할 필요, feedback_pr_workflow 적용)

10. **_v1 디렉토리 9개 제거** (frontend)
    - 영향 파일: 9개 디렉토리 × N개 파일 (>30 files 가능)
    - 필수 사전 작업: v2 페이지들이 v1 컴포넌트를 import하는지 grep으로 확인
    - PR 분할: auth/_v1, dashboard/_v1 각각 별도 PR
    - feedback_feature_preservation: v1 인벤토리 + v2 매핑 표 작성 후 진행

11. **services/ 패키지화 완성 + __init__.py 추가**
    - 19개 flat .py를 서브패키지로 재배치 + 전체 import 경로 업데이트
    - 영향 파일: 30개 이상 예상 (routes/ 전체 + tests/ 다수)
    - feedback_pr_workflow: 반드시 분할 PR (모듈 그룹별: cache/registry/alert/push 등)

12. **hooks 분산 정리** (lib/hooks.ts, lib/cfo/hooks.ts, components/portfolio/v2/hooks-v2.ts)
    - 통합 or 명확한 책임 분리 문서화
    - 영향: hooks를 import하는 컴포넌트 다수

---

## 비용

- 추가 비용: $0 (외부 API 호출 없음, 파일 시스템 조작만)
- 토큰: 진단 Phase A ~30k tokens 사용됨. Phase C (Tier 1) 예상 ~5k.

---

## Tier 1 실행 대기 목록 (Phase C)

Phase C는 이 문서 작성 직후 즉시 실행:
- [1] 루트 __pycache__ 고아 .pyc 삭제
- [2] 빈 " 2" 디렉토리 3개 삭제
- [3] 취준/ 루트 세션보고서 7개 → 취준/archive/ 이동
- [4] .gitignore에 `.bughunt-*` 추가

Tier 2/3 실행: CEO ACK 후 별도 작업으로 진행.
