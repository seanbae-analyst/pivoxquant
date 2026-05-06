# Nightly Autonomous Dev — 운영 가이드

매일 03:00 KST에 GitHub Actions가 작업 큐(label `auto-eligible`)에서 1개 issue를 픽업해 Claude Code에게 구현을 맡기고 Draft PR + Slack alert를 만든다.

- 워크플로우: [`/.github/workflows/nightly-autonomous-dev.yml`](../.github/workflows/nightly-autonomous-dev.yml)
- 명세 출처: `archive/sessions-2026-05/AUTOMATION_STRATEGY_2026-05-01.md` Phase 3A
- Anthropic 추론: `anthropics/claude-code-action@v1` + `CLAUDE_CODE_OAUTH_TOKEN` (Max 플랜 OAuth) — Anthropic API 직접 호출 0건
- 추가 비용: **$0** (Max 플랜 + GitHub Actions free tier)

---

## 1. 최초 활성화 (사용자가 직접 1회)

### A. Repo variable로 kill switch ON

```bash
# 워크플로우 진짜로 도는 모드 (1=ON)
gh variable set NIGHTLY_AUTO_DEV --body "1" --repo seanbae-analyst/pivoxquant

# 정지하려면
gh variable set NIGHTLY_AUTO_DEV --body "0" --repo seanbae-analyst/pivoxquant
```

워크플로우가 `kill-switch` job에서 이 값을 읽고 `1`이 아니면 즉시 중단한다. 7일 검토 기간 동안 한 번이라도 회로차단기가 발동하면 이걸 `0`으로 돌려라.

### B. 필수 secrets

| Secret | 용도 | 설정 방법 |
|--------|------|-----------|
| `CLAUDE_CODE_OAUTH_TOKEN` | Max 플랜 OAuth (이미 morning-triage 등에서 사용중) | 이미 존재. `claude setup-token` 절차는 [`CLAUDE_CODE_OAUTH_SETUP.md`](./CLAUDE_CODE_OAUTH_SETUP.md) |
| `SLACK_WEBHOOK_URL` | 작업 시작/완료/실패/회로차단 알림 | 이미 존재. `gh secret list` 로 확인 |
| `GITHUB_TOKEN` | issue/PR/branch 조작 | GitHub Actions가 자동 주입 (별도 설정 X) |

확인:

```bash
gh secret list --repo seanbae-analyst/pivoxquant | grep -E "CLAUDE_CODE_OAUTH_TOKEN|SLACK_WEBHOOK_URL"
```

---

## 2. 작업 큐 채우기 (사용자 매일 또는 주간)

워크플로우는 다음 조건을 모두 만족하는 issue를 픽업한다:

- state = `open`
- label `auto-eligible` **있음**
- label `difficulty:low` **있음**
- label `do-not-automate` **없음**
- label `blocked` **없음**

우선순위: `priority:high` > `priority:medium` > `priority:low`, 같은 등급은 가장 오래 열린 issue.

### 라벨 셋업 (1회)

```bash
gh label create auto-eligible --color "00ff00" --description "nightly-autonomous-dev queue pickup OK"
gh label create do-not-automate --color "ff0000" --description "block from autonomous dev"
gh label create difficulty:low --color "c2e0c6" --description "self-contained, <30 files"
gh label create priority:high --color "d93f0b"
gh label create priority:medium --color "fbca04"
gh label create priority:low --color "0e8a16"
gh label create auto-failed-3x --color "5319e7" --description "circuit-breaker fired"
```

### 큐에 issue 추가 예시

```bash
gh issue create \
  --title "Fix typo in dashboard footer" \
  --body "footer.tsx 30번째 줄 'Pivxoquant' → 'PivoxQuant'" \
  --label "auto-eligible,difficulty:low,priority:low"
```

좋은 candidate 예시:
- 단순 typo / copy fix (UI 문구, 주석)
- 작은 helper 함수 추가 + 단위 테스트
- 명확한 lint 위반 정리
- 누락된 docstring 추가
- 단일 파일 수준 small refactor

**나쁜** candidate (라벨 안 붙임):
- DB 마이그레이션
- 새 의존성 추가 필요
- 보호 경로 (`autotrader/`, `risk_defense/`, `billing/`, `auth/`, `security/`, `migrations/`, `alembic/`)
- 30개 파일 초과 예상

---

## 3. 안전장치 (5중 락)

| Layer | 어디서 | 무엇 |
|-------|--------|------|
| 1 | `kill-switch` job | repo variable `NIGHTLY_AUTO_DEV != "1"` 이면 종료 |
| 2 | Claude prompt | 보호 경로 prompt 차원에서 명시적 차단 |
| 3 | `Safety gate — protected paths` step | `git diff --name-only` 결과를 grep, 매치 시 abort |
| 4 | `Safety gate — diff size` step | 변경 파일 ≤ 30. 초과시 abort (`feedback_pr_workflow` rule #3) |
| 5 | `Safety gate — pytest` step | `pytest -x -q --maxfail=1 --timeout=120` 실패 시 PR 생성 차단 |
| 6 | PR 자체 | `gh pr create --draft` — 사람이 명시적으로 ready 시켜야 머지 가능 |
| 7 | Branch protection (사용자 측) | "Require draft conversion before merge" 룰 켜둘 것 |

추가:
- **회로차단기**: 같은 issue가 24h 안에 3회 실패하면 `auto-eligible` 라벨 자동 제거 + `auto-failed-3x` 부착 + Slack escalation. `.github/autonomous-dev-failures.json`에 24h 윈도 기록.
- **Concurrency**: `concurrency: nightly-autonomous-dev`로 동시에 한 번만 도는 보장. 이전 run 실행중이면 새 trigger는 무시.

---

## 4. 트리거 경로

### A. cron (정상 경로)
`schedule: '0 18 * * *'` — 18:00 UTC = 03:00 KST.

### B. workflow_dispatch (수동)
GitHub Actions 탭에서 "Run workflow" → 옵션:
- `issue_number`: 강제 픽업 (비우면 큐 자동)
- `dry_run`: `true` 면 큐 픽업까지만 (PR 생성 X). 첫 검증 시 사용.

### C. repository_dispatch (CC scheduled task에서 호출)
외부에서 호출 가능:

```bash
gh api repos/seanbae-analyst/pivoxquant/dispatches \
  -F event_type=cc_autonomous_dev \
  -F client_payload[issue_id]=142
```

CC 세션 안에서 `mcp__scheduled-tasks__create_scheduled_task` 로 등록한 태스크가 매일 03:30 KST에 발화하도록 만들고, 그 태스크 안에서 위 `gh api` 명령을 호출하면 같은 워크플로우가 돈다. cron이 이미 03:00에 도는 이상 보통 필요 없지만, "큐 픽업 로직을 CC가 더 똑똑하게 한 다음 워크플로우는 트리거만"같은 응용을 원할 때 쓴다.

---

## 5. 첫 7일 검토 절차

1. **매일 아침** 09:00 KST 즈음에:
   - Slack `#auto-dev` (또는 webhook 라우팅된 곳) 확인
   - 새 Draft PR 검토 (PR 본문의 체크리스트 항목 모두 확인)
   - 회로차단기 발동 메시지 있으면 즉시 분석
2. **회로차단기 1회라도 발동**:
   - 즉시 `gh variable set NIGHTLY_AUTO_DEV --body "0"` (워크플로우 정지)
   - `.github/autonomous-dev-failures.json` 분석 → 원인 파악 → prompt/안전장치 보강 → 재활성화
3. **PR 머지 후**:
   - 해당 issue는 `Closes #<num>` 으로 자동 close됨
   - main 머지 후 `post-deploy-canary` 워크플로우 결과 확인 (regression 감지)

---

## 6. 비용 검증

| 항목 | 예상 사용 | Free tier 한도 | 상태 |
|------|----------|----------------|------|
| Anthropic API 직접 호출 | 0회 | — | OAuth 전용 |
| Claude Code (Max OAuth) | nightly 1 session × 30 = 30 sessions/mo | Max 플랜 quota 안 | OK |
| GitHub Actions 분 | ~10 min × 30 = 300 min/mo | 2000 min/mo | OK (15%) |
| Slack webhook | 1-3 호출/run × 30 = ~90/mo | 무제한 | OK |

**추가 결제 0원**. 만약 cc-implement 단계가 평균 30분 이상 걸린다면 GitHub Actions 사용량 모니터링 필요 (`Actions → Usage`).

---

## 7. 비활성화 / 영구 정지

```bash
# 일시 정지 (큐는 그대로, 워크플로우만 안 돔)
gh variable set NIGHTLY_AUTO_DEV --body "0"

# 영구 정지 (워크플로우 파일 자체 비활성)
gh workflow disable nightly-autonomous-dev --repo seanbae-analyst/pivoxquant

# 큐 전부 비우기
gh issue list --label auto-eligible --state open --json number -q '.[].number' \
  | xargs -I{} gh issue edit {} --remove-label auto-eligible
```

---

## 8. 참고 메모리 룰

- `feedback_no_extra_cost.md` — Anthropic API 직접 호출 금지, Max 플랜 + Actions free tier 안에서 처리
- `feedback_pr_workflow.md` — alembic heads / worktree freshness / >30 files / spot check
- `feedback_no_false_reports.md` — PR 본문에 추측 금지, grep 결과만 인용
- `feedback_thorough_fixes.md` — 한 번 손대면 유사 패턴 전수 점검 (Claude prompt에 reflect됨)

추가로, Iron Rules:
1. 보호 경로 위반 시 abort (3중 안전장치)
2. PR Draft only — 사람 spot check 필수
3. 회로차단기 발동 = 즉시 정지 + 분석
