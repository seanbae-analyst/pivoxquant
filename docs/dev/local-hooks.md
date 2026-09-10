# Local Git Hooks — Migration from GitHub Actions

**Status**: ACTIVE (2026-05-19, v45.4 마무리 wave)
**Reason**: GitHub Actions billing 결제 차단 (카드 미등록) + `feedback_no_extra_cost` 룰 영구 준수.
**Owner**: CEO + frozen-file-diff-guard agent + release-coordinator.

## 왜 (Why)

PivoxQuant는 GitHub free plan + private repo + 카드 미등록 상태.
GitHub Actions가 매 push마다 fail 알림을 보냈고 (`No payment method on file`),
이는 `feedback_no_extra_cost.md` 룰 ("Max + 도메인 + Railway 외 신규 비용 0원")에
직접 위배. CEO 결정: **로컬 git hooks로 이전, GitHub Actions 영구 OFF**.

카드 등록 → workflows 재활성화는 출시 후 별도 의사결정.

## 어떻게 (How)

저장소 clone 또는 pull 직후, **단 한 번**만 실행:

```bash
git config core.hooksPath .githooks
```

검증:

```bash
git config --get core.hooksPath
# → .githooks
```

`.githooks/` 디렉터리는 git에 commit되어 있으므로 모든 dev가 동일 hook 사용.
단 `core.hooksPath` 설정은 **per-clone repo-local** 이므로 위 명령은 각 dev가 직접 실행.

## 각 Hook이 무엇을 검사하는가

### `.githooks/pre-commit` (FAST, blocking)

| # | 검사 | 출처 / 대체 |
|---|-----|-----|
| 1 | Forbidden file extensions (.env, .db, .pem 등 staging) | `.gitignore` 보완 |
| ~~2~~ | ~~`market-ticker.tsx` SNAPSHOT_DATE > 14일 stale~~ — **2026-09-10 제거.** 지키던 상수가 2026-05-15 에 폐기(정적 스냅샷 → `/api/public/market-snapshot`)돼 4개월간 발화 불가였는데 이 표에는 살아있는 방어선으로 적혀 있었다. | — |
| 3 | Pattern scan: beta-password regex / Sentry DSN / Anthropic / AWS / Stripe key | `secret-scan.yml` |
| 4 | **Legal-guard**: BUY/SELL/HOLD/recommend/advice/추천/조언 (시그널 enum 화이트리스트) | `legal-guard.yml` |
| 5 | **Frozen-file diff guard**: `.claude/frozen_files.yaml` `hard_frozen` 7건 변경 시 BLOCK + escape token 검사 | v45.4 G3 agent |
| 6 | **Ruff check**: staged `.py` lint (ruff 미설치 시 skip) | `ci.yml` lint job |
| 7 | **Extended secret scan**: ghp_ / ghs_ / OAUTH_CLIENT_SECRET / DEV_LOGIN_SECRET 값 | `secret-scan.yml` |

### `.githooks/pre-push` (SLOWER OK, blocking)

| # | 검사 | 출처 / 대체 |
|---|-----|-----|
| 1 | **Alembic head guard**: heads 2개 이상 BLOCK | `alembic-head-guard.yml` |
| 2 | **Regression guards**: `scripts/check_regression_guards.py` (9 bug pattern SoT) | `regression-guards.yml` |
| 3 | **Pytest sanity**: 변경 routes/services 매칭 test + core regression test | `ci.yml` (subset) |
| 4 | **Pytest smoke**: `@pytest.mark.smoke` 3건 (health / auth-required / login→portfolio), ~1.3s | `daily-api-smoke.yml` |

전체 pytest는 시간이 길어서 pre-push에서 skip. nightly 또는 출시 전 별도 실행.

#### smoke 게이트는 차단이 기본 (2026-08-30 변경)

`[4/4]` 는 원래 warn-only 였다 — 실패해도 경고만 찍고 push 가 통과했다. GitHub Actions
28개가 전부 `.disabled` 인 현재 **이 훅이 origin 과 깨진 auth 경로 사이의 유일한 게이트**라,
빨간 smoke 가 스크롤에 묻혀 그대로 올라갈 수 있었다. 1.3초짜리 검사에 그만한 위험을
감수할 이유가 없어 기본값을 뒤집었다.

```bash
PIVOX_PREPUSH_BLOCK=0 git push   # WIP 브랜치 등 의도적 우회
git push --no-verify             # 훅 전체 우회 (최후 수단)
```

**CI 가 살아나면 이 기본값을 되돌릴지 재검토할 것** — CI 가 같은 검사를 우회 불가하게
수행하면 로컬 훅은 빠른 피드백 역할로 물러나도 된다.

### `.githooks/post-checkout` (INFORMATIONAL, never blocks)

브랜치 체크아웃 시 `.claude/frozen_files.yaml`이 변경되었으면 1줄 알림. 차단 X.

## Escape Tokens (frozen-file 변경 시)

`services/quant/*.py` 또는 `services/ai/models.py` 등 hard_frozen 7건을
정당한 사유로 변경해야 할 때, **commit message**에 다음 중 하나 포함:

| Token | 적용 대상 | Precedent |
|-------|----------|-----------|
| `cache-poisoning-sentinel approved` | `services/ai/models.py` (cache poisoning fix) | v44.9 PR #488 / v45.3 commit `69b583af` |
| `fx-consistency-guard approved` | `services/quant/portfolio.py` (FX 통화 일관성 fix) | v44.9 PR #484 / v45.3 commit `eea051e5` |
| `legal-kr-fintech approved` | `services/ai/models.py` (prompt injection / KR fintech 법규) | v45.3 commit `22bf5496` |
| `CEO override: <reason>` | 임의 hard_frozen path (긴급) | CEO 명시 승인 |

Hook 동작: pre-commit이 `.git/COMMIT_EDITMSG` 파일을 grep — escape token
없으면 BLOCK + 메시지 출력. token이 있으면 통과.

## Bypass (사용 금지 원칙)

위급 상황에서만:

```bash
git commit --no-verify
git push --no-verify
```

CI 미러가 없으므로 bypass = 검증 0. 사용 시 본인이 모든 위반 책임.

## GitHub Actions 복원 방법 (카드 등록 후)

1. Vercel/Railway 결제와 별개로 GitHub Settings → Billing → Add payment method
2. `.github/workflows/` 디렉터리에서 .disabled 복원:

   ```bash
   cd .github/workflows
   for f in *.yml.disabled; do
     # 본 wave에서 OFF한 14 + 기존 1 (vercel-deploy-canary 신규)
     git mv "$f" "${f%.disabled}"
   done
   git commit -m "ci: re-enable GitHub Actions after billing setup"
   git push
   ```

3. 단 `*.disabled.disabled` 같은 이중 .disabled 파일은 원래 의도적으로 비활성화된
   workflow이므로 (예: agent-health-weekly, morning-brief, nightly-* 등) 복원하지 말 것.
   복원 대상은 **`*.yml.disabled` 형태에서 정확히 한 번만 disabled된 14건** + neue
   3건 (alembic-head-guard / daily-regression-gate / vercel-deploy-canary).
4. 복원 후 push → Actions 탭에서 workflow 실행 확인 + 본 문서 status를 INACTIVE로 갱신.

## 활성 / 비활성 workflows 인벤토리 (2026-05-19 기준)

- 활성 (`*.yml`): **0개**
- 비활성 (`*.yml.disabled`): **28개**
  - 본 wave에서 OFF: 15개 (alembic-head-guard, api-health, artifact-qa, ci, daily-regression-gate, db-nightly-dump, design-safety-guards, frontend-tests, legal-deep-scan, legal-guard, pdf-lint, regression-guards, secret-scan, ssl-expiry-check, vercel-deploy-canary)
  - 기존 OFF (.disabled로 유지): 13개 (agent-health-weekly, agent-upgrades-monthly, daily-api-smoke, daily-legal-scan, legal-risk-monitor, morning-brief, morning-triage, nightly-autonomous-dev, nightly-bug-hunt, post-deploy-canary, self-healing, weekly-memo-mon-0900-kst, weekly-security-scan)

## Future Considerations

- 출시 후 카드 등록 시 P0 3건 (alembic-head-guard / daily-regression-gate / vercel-deploy-canary)부터 우선 복원 권고
- ci.yml은 PR 단위 검증이라 카드 등록 후 즉시 복원 권장
- 로컬 hooks는 카드 등록 후에도 dev 머신 빠른 피드백 용도로 유지
- pre-commit framework (https://pre-commit.com/) 채택 검토는 **추가 의존성 발생**으로 본 wave에서 보류

## 참고

- 인수인계서: `HANDOVER.md` v45.4 → v45.5 prepend (별도 wave)
- SoT: `.claude/frozen_files.yaml`
- 9 bug pattern SoT: `~/.claude/projects/-Users-seanbae-Desktop---/memory/feedback_bug_fix_patterns.md`
- 비용 룰: `~/.claude/projects/-Users-seanbae-Desktop---/memory/feedback_no_extra_cost.md`
