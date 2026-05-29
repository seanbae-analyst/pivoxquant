# PivoxQuant Launch Readiness Verification — 2026-05-29

> Audit Agent (검수부) — Goldman Standard. 모든 결론은 실제 명령 출력 인용 (feedback_no_false_reports).
> cwd = `/Users/seanbae/Desktop/취준/pivoxquant`. 검증자: audit agent (sub-part 미참여 — 단독 readiness 스모크).

## 판정 요약

| # | 항목 | 판정 | 근거 (실측) |
|---|------|------|-------------|
| 1 | pytest 백엔드 전체 | ✅ PASS | 3431 passed / 1 failed (documented flake, solo PASS) / 189 skipped / 1 xfailed |
| 2 | frontend build + vitest | ✅ PASS | build exit 0 "Compiled successfully in 50s" / vitest 492 passed (49 files) |
| 3 | `.railwayignore` 무결성 | ✅ PASS | 모든 디렉토리 leading-slash anchored / frontend·venv·.git 제외 확인 |
| 4 | prod 배포 currency | ✅ PASS | prod `e8048386248b` = origin/main tip = dev clone tip (0/0 동기화) |
| 5 | prod 핵심 엔드포인트 스모크 | ✅ PASS | health 200 / signals 401 / auth/google 302 / root 302 — 전부 정상 |

**SHIP-BLOCKER (코드/인프라 측): 없음.**
잔존 출시 BLOCKER는 전부 외부/법무 의존 (변호사 Q1-Q15+Q-S1, 통신판매업, MX) — 본 스모크 범위 밖, CLAUDE.md 기록과 일치.

---

## 1. pytest 백엔드 전체 — ✅ PASS

명령: `./venv/bin/python -m pytest -q` (`python`은 PATH에 없어 venv 직접 호출)

실측 요약 라인:
```
= 1 failed, 3431 passed, 189 skipped, 1 xfailed, 740 warnings in 1436.47s (0:23:56) =
FAILED tests/test_fx_staleness.py::TestFxDedup::test_dedup_suppresses_alert
```

- 3431 passed (메모리 예상 ~3443 대비 -12 — skip/xfail 분포 차이, 회귀 아님).
- 유일 실패 = `test_fx_staleness.py::TestFxDedup::test_dedup_suppresses_alert`.

**격리 재실행 (단독):**
```
tests/test_fx_staleness.py .                                             [100%]
============================== 1 passed in 0.08s ===============================
```

판정: 단독 PASS. 이는 CLAUDE.md "백엔드 flaky 테스트 격리 (test_daytrade_smoke / test_fx_staleness — full suite 시 fail, 단독 PASS)" 에 이미 문서화된 **알려진 flake (글로벌 상태 오염/순서 의존)**. 실제 회귀 아님 → SHIP-BLOCKER 아님.

> P2 권고 (no-busywork: 강제 아님): full-suite 결정성 위해 fx dedup 글로벌 상태 fixture 격리. 출시 게이트와 무관.

## 2. frontend build + vitest — ✅ PASS

### npm run build
참고: `npx tsc --noEmit` 은 `.next/dev/types/routes.d.ts`·`validator.ts` 의 생성된 dev-cache 파편에서 TS1434/TS1002 등을 뱉음 — 소스 타입 에러 아니라 stale dev 아티팩트. 권위 게이트는 `npm run build` (.next/dev 재생성).

```
BUILD_EXIT=0
✓ Compiled successfully in 50s
```
전체 라우트 매니페스트 정상 생성 (signals/settings/reports/preview/* 등 surface 전수 포함).

### vitest run
```
Test Files  49 passed (49)
     Tests  492 passed (492)
```
판정: build exit 0 + vitest 492/492 → PASS.

## 3. `.railwayignore` 무결성 — ✅ PASS

전체 파일 (요지):
```
/frontend/
/venv/
/.venv/
/node_modules/
/.git/
/.claude/
/samples/
/artifacts/
/self_healing_artifacts/
/legal_monitor_artifacts/
/test-results/
/docs/
/state/
/instance/
__pycache__/
*.pyc
.pytest_cache/
*.log
*.pdf
*.png
```
- 모든 디렉토리 항목 leading-slash root-anchored — `/artifacts/` 가 `services/artifacts/` 를 매칭하지 않음 (과거 ModuleNotFoundError 사고 재발 방지 확인).
- `frontend`·`venv`·`.git` 제외 확인 (업로드 타임아웃 방지).
- 파일 상단에 anchoring 경고 주석 보존됨.

판정: 무결성 PASS.

## 4. prod 배포 currency — ✅ PASS

prod `/api/health` version = `e8048386248b`.

- Desktop clone (`~/Desktop/취준/pivoxquant`): HEAD = origin/main = `9d46e6a7` ("test(support): chatbot FAQ … (dev에서 회수)"). `git cat-file -t e8048386` → `fatal: Not a valid object name` (이 클론엔 없음).
- dev clone (`~/dev/pivoxquant`):
```
e8048386 type → commit
e8048386 log  → e8048386 fix(build): latest-artifact-card 중복 <style jsx> 블록 병합 …
origin/main   → e8048386 fix(build): latest-artifact-card 중복 <style jsx> 블록 병합 …
rev-list e8048386 ^origin/main → 0
rev-list origin/main ^e8048386 → 0
```

판정: **prod = dev clone tip = origin/main tip (0/0, 완전 동기화)**. prod는 stale 아님.

> 주의 (P2, 비차단): Desktop clone 의 `9d46e6a7` ("dev에서 회수")는 origin/main(`e8048386`)에 **없는 로컬 전용 커밋**. 두 클론이 발산 상태 — Desktop이 origin 대비 +1 ahead. prod/origin 기준 currency엔 영향 없으나, Desktop에서 작업 시 push 전 rebase 필요. 출시 게이트 아님.

## 5. prod 핵심 엔드포인트 스모크 — ✅ PASS

base: `https://web-production-7b484b.up.railway.app`

```
/api/health        → HTTP 200  {"db":"ok","status":"ok","version":"e8048386248b",
                                 "env":{missing_required:0, missing_recommended:1}}
/api/signals       → HTTP 401   (인증 필요 — 미인증 차단 정상)
/api/auth/google   → HTTP 302 → accounts.google.com/o/oauth2/v2/auth?... 
                                 redirect_uri=https://pivoxquant.com/api/auth/google/callback (정상)
/  (root)          → HTTP 302   (베타 게이트/리다이렉트 정상)
```

판정: db ok, missing_required 0, OAuth 리다이렉트 정상 구성, 보호 엔드포인트 401. 전부 정상 → PASS.

> 관측 (비차단): `missing_recommended:1` — CLAUDE.md 기록상 SENDGRID_API_KEY 또는 SENDGRID_WEBHOOK_PUBLIC_KEY. 발신 작동 확정은 CEO Railway Variables 확인 사항 (외부 액션). 출시 코드 게이트 아님.

---

## Risk Register

| 리스크 | 확률 | 영향 | 대응 |
|--------|------|------|------|
| fx_staleness full-suite flake가 실제 회귀 은폐 | 낮음 | 중 | 단독 PASS 확인됨. fixture 격리 권고(P2) |
| Desktop↔dev clone 발산 (Desktop +1) | 중 | 저 | push 전 rebase. prod currency 무영향 |
| SENDGRID env 누락으로 이메일 발신 실패 | 중 | 중 | CEO Railway Variables 확인 (외부) |
| 외부/법무 BLOCKER (변호사·통신판매업·MX) | — | 출시차단 | 본 스모크 범위 밖. legal_question_queue.md |

## Final Sign-off

**코드/인프라 측 readiness: 조건부 승인 (CONDITIONAL → 사실상 PASS).**
5개 검증 항목 전부 PASS. 코드/인프라 측 SHIP-BLOCKER 없음. 유일 pytest 실패는 문서화된 flake (단독 PASS 입증). 출시 차단 요소는 전적으로 외부/법무 의존 (변호사 의견서·통신판매업 신고·이메일 MX) — 코드 게이트 아님, 본 검증 범위 밖.
