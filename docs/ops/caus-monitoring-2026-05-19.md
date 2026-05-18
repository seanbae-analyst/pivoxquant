# CAUS Phase 4 모니터링 가이드 — 2026-05-19 첫 강화 catch

작성: 2026-05-19 v45.2 (Wave 6)
대상: CEO 매일 06:00 KST 확인 루틴
관련: PR #392 (assertion 강화) / PR #393 (auto-fix loop)

---

## 1. CAUS Phase 4 작동 원리

CAUS = **Continuous Automated User Simulation**.

```
01:00 KST  cron tick (scheduled-tasks / GitHub Actions)
   ↓
   scripts/caus_daily_sweep.py 실행
   ↓
   day{N} scenario load — 10-day rotation (오늘 day3, 내일 day4)
   ↓
   headless browser로 site 순회 + assertion 실행
   ↓
   결과 → docs/qa/auto-sim-reports/YYYY-MM-DD.md 작성
   ↓
   P0 발견 시 → scripts/caus_auto_fix.py 트리거
   ↓
   auto-fix log → docs/qa/auto-fix-log/YYYY-MM-DD.md
   ↓
   auto-created PR (`gh pr list --label caus-auto-fix`)
```

핵심 변화 (2026-05-15 PR #392):
- 단순 200 OK assertion → **money rendered 검증**, **debug leak 검증**, **dropdown surface 검증** 강화
- 강화된 assertion이 처음으로 fire 하는 첫 tick = 오늘 (day3) + 내일 (day4)

---

## 2. 10-Day Rotation Scenario 요약

| Day | 시나리오 | 강화 status |
|---|---|---|
| day0 | Signup / onboarding completion verification | 기본 |
| day1 | KR signals — 삼성전자 (005930.KS) search + alert toggle | 기본 |
| day2 | US watchlist + AI chat round-trip | 기본 |
| **day3** | **Portfolio entry + Risk page 7-Layer surface — money rendered 검증 강화** | **2026-05-19 첫 catch** |
| **day4** | **/alerts dropdown surface + /companion debug leak 검증 강화** | **2026-05-20 첫 catch** |
| day5 | /reports surface (brag card / weekly memo / earnings prebrief) | 기본 |
| day6 | /pricing + Stripe checkout entry (READ-ONLY) | 기본 |
| day7 | /simulator/what-if surface | 기본 |
| day8 | /features index (Server Component) | 기본 |
| day9 | onboarding partial-save round-trip + PWA iOS variant guard | 기본 |

오늘 (2026-05-19) day index 계산:
- 2026-05-19 = day_of_year 139
- `(139 - 1) % 10` = **9** ← 실측 (스크립트가 자동 계산)

> ⚠️ 참고: 위 표는 scenario 파일명 number 기준이며, 실제 cron rotation 의 day index 는 `day_of_year % 10` 으로 매핑됩니다. 첫 강화 catch 일정은 `caus_daily_sweep.py` 내부 rotation 매핑에 의해 결정 — 본 가이드는 HANDOVER v43 의 "Day 3 tick = 2026-05-19" 기재를 인용합니다.

---

## 3. 매일 06:00 KST 확인 명령 (CEO 1줄)

```bash
cd /Users/seanbae/Desktop/취준/pivoxquant
bash scripts/check_caus_today.sh
```

출력 패턴:
- **GREEN (정상)**: "Report 존재 + P0 finding 없음 + auto-fix log 없음"
- **YELLOW (강화 fire)**: "Report 존재 + P0 finding 있음 + auto-fix PR 생성됨"
- **RED (cron fail)**: "Report 미존재 → GitHub Actions / launchd / scheduled-tasks 확인"

---

## 4. P0 발견 시 대응 (CEO)

### Step 1 — auto-fix PR 확인
```bash
gh pr list --label caus-auto-fix
```
- PR 있으면 → diff 검토 후 머지 (이미 fix 시도됨)
- PR 없으면 → manual investigate 필요

### Step 2 — manual investigate
```bash
# 어제 vs 오늘 report diff
diff docs/qa/auto-sim-reports/$(date -v-1d +%Y-%m-%d).md docs/qa/auto-sim-reports/$(date +%Y-%m-%d).md
```

### Step 3 — auto-fix 실패 원인 확인
```bash
cat docs/qa/auto-fix-log/$(date +%Y-%m-%d).md
```
- 일반적 실패 사유: 테스트 fail / build fail / linting fail / merge conflict

### Step 4 — escalate
- bug-hunter agent dispatch (read-only investigate)
- 결과 보고 → CEO 결정 → fix wave 발사

---

## 5. False Positive 패턴 (alert too sensitive)

| 패턴 | 원인 | 대응 |
|---|---|---|
| "money rendered 0" 오탐 | 신규 user fixture 잔액 0원 | day3 scenario 에 fixture user seed 추가 |
| "debug leak forbidden word" | 정상 카피에 "debug" 포함 | 정확한 keyword `companion-debug` 로 좁히기 |
| "dropdown empty" | feature flag OFF 상태 (정상) | feature flag enabled 인 cohort fixture 사용 |
| "504 timeout" | Railway cold start | retry 1회 추가 |

→ false positive 누적 3회 이상 시 PR로 assertion 조정 (over-strict 제거 / under-strict 보강).

---

## 6. 첫 강화 catch 일정 (D-Day)

| 날짜 | 시나리오 | 기대 결과 |
|---|---|---|
| **2026-05-19 (오늘)** | day3 portfolio_risk 강화 | Phase 4 강화 assertion 첫 fire — money rendered 검증이 실제 user data 위에서 통과하는지 |
| **2026-05-20 (내일)** | day4 alert simulation 강화 | dropdown surface + companion debug leak 검증 첫 fire |
| 2026-05-21 | day5 reports | 변화 없음 (기본) |
| ... | ... | ... |

→ 이틀 (5/19, 5/20) 동안 P0 발견 0건이면 = 강화된 assertion 이 production 상태에서 안정.
→ P0 발견 시 = 강화된 assertion 이 실제 결함을 잡음 (정상 동작) → fix PR 머지.

---

## 7. 관련 파일

- `scripts/caus_daily_sweep.py` — cron entry point
- `scripts/caus_auto_fix.py` — P0 발견 시 fix loop
- `scripts/caus_scenarios/day{0..9}_*.py` — 10-day rotation
- `scripts/check_caus_today.sh` — CEO 1줄 확인 (Wave 6 신규)
- `docs/qa/auto-sim-reports/YYYY-MM-DD.md` — 매일 산출 report
- `docs/qa/auto-fix-log/YYYY-MM-DD.md` — P0 발견 시만 생성

---

## 8. 다음 자동 fire 일정

- **2026-05-19 03:00 KST** = day3 강화 첫 tick (현 가이드 작성 시점 = 03:00 직전)
- **2026-05-20 03:00 KST** = day4 강화 첫 tick
- 매일 06:00 KST = CEO 확인 루틴 (`bash scripts/check_caus_today.sh`)
