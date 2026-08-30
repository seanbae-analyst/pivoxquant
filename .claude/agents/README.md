# PivoxQuant Agent System

> 2026-08-30 재편. **59개 → 25개.** 나머지 33개는 삭제가 아니라
> `.claude/agents/archive/` 로 이동 — 필요하면 언제든 되돌린다.

## 왜 줄였나

agent 의 `description` 은 **매 턴 시스템 프롬프트에 로드된다.** 개수가 곧
고정 토큰 비용이다. 59개 시절 description 총량은 12,066 bytes 였고, 그중
다수가 *출시 대비* 감시/게이트 agent 였다 — 그런데 출시는 이뤄지지 않았고
백엔드 prod 는 내려가 있어 감시 대상 자체가 없다. 유지 비용만 남은 셈.

재편 후 description 총량 약 **3.6KB (-70%)**.

## 활성 25개

### 핵심 작업 (7)
`engineering` `qa` `design` `product` `devops` `security` `legal`

### 검증 — 실측 강제 (5)
`verify-api` `verify-data` `verify-design` `verify-security` `verify-ux`

> CLAUDE.md 중요원칙 §1 "최신 정보 파악" 의 집행 계층. 기억이 아니라
> 실제 호출/클릭으로 확인하고, 증거 없으면 PASS 를 찍지 않는다.

### 버그 (2)
`bug-hunter` (모르는 버그 발굴) · `investigate-bug` (알려진 증상 근본원인)

### 데이터 무결성 가드 (3)
`fx-consistency-guard` · `data-freshness-monitor` · `cache-poisoning-sentinel`

> ⚠️ 처음 재편 때 아카이브했다가 **되돌렸다.** `tests/test_data_integrity_gates.py::
> test_three_data_integrity_agents_defined` 가 이 3개 파일의 실재를 강제한다 —
> `.claude/workflows/wave-data-integrity.md` 가 호출하는 전제조건이기 때문. 사고 전력도
> 근거다: FX 일관성 P0 2회(+52,281% / 700배), 캐시 크로스유저 PII 유출 2회.
> 새 제품도 원화·달러 혼재 포트폴리오를 다루므로 FX 가드는 계속 필요하다.
> **셋 중 하나라도 옮기면 테스트가 깨진다.**

### 디자인 (2)
`motion-designer` · `brand-voice`

> `.claude/workflows/wave-design-polish.md` 가 `agent:` 로 직접 호출한다. 재구축에서
> 디자인 작업이 계속되므로 워크플로와 함께 유지.

### 도메인 — 대체 불가 (6)
| agent | 남긴 이유 |
|---|---|
| `legal-kr-fintech` | 자본시장법 §17 등 한국 금융규제. 일반 `legal` 보다 깊고, 이 제품의 존폐 이슈 |
| `persona-quant-domain` | 8 페르소나 / 40 퀀트모델 도메인 |
| `migration-guard` | Alembic P0 사고 2건 전력 (BigInteger 26 test fail, alembic 035 prod 미적용) |
| `frozen-file-diff-guard` | CLAUDE.md Iron Rule — 검증된 퀀트 코어 동결 집행 |
| `email-deliverability` | 주간 리포트 발송이 제품 핵심 가치. Brevo cascade 운영 |
| `agent-ops` | agent 체계 자체의 점검·재편 |

## 아카이브 33개

되살리려면 파일을 `archive/` 밖으로 옮기기만 하면 된다.

```bash
mv .claude/agents/archive/<name>.md .claude/agents/
```

분류별:
- **부서 일반** (10) — analytics, audit, customer, docs, finance, growth,
  integrations, marketing, pitch, strategy. 범용이라 인라인으로 대체 가능.
- **출시/감시** (9) — launch-coordinator, launch-runner, release-coordinator,
  compliance-gatekeeper, regulatory-monitor, autopilot-monitor,
  beta-onboarding-monitor, cost-monitor, secrets-rotator.
  감시 대상(prod)이 내려가 있어 현재 무의미. **백엔드 복구 시 우선 복원 후보.**
- **디자인 세분화** (5) — visual-designer, onboarding-designer,
  pdf-report-designer, mobile-pwa-optimizer, ux-researcher.
- **1회성 가드** (2) — pwa-cache-validator, prod-migration-sync-verifier.
- **결제** (2) — stripe-billing, billing-incident-handler. 결제 게이트로 비활성.
- **기타** (5) — artifact-qa, frontend-test-runner, verify-policy,
  bkit-orchestrator, investment-research.

## 유지 규칙

새 agent 를 추가할 때는 **기존 20개로 안 되는 이유**를 먼저 적는다.
`description` 은 라우팅에 필요한 트리거만 (2줄 이내). 사고 이력·상세 절차는
본문에 쓴다 — 본문은 그 agent 가 실제로 호출될 때만 로드되므로 공짜다.

## 아카이브 전 확인 (2026-08-30 교훈)

agent 를 옮기기 전에 **그 파일명을 참조하는 테스트·워크플로가 있는지 먼저 grep 한다.**

```bash
grep -rn "<agent-name>" tests/ .claude/workflows/ scripts/
# 워크플로는 `agent: <name>` 선언만 실제 계약이다 — 산문 속 단어는 오탐:
grep -rn "^\s*agent:" .claude/workflows/*.md | sort -u
```

첫 재편에서 이걸 건너뛰어 데이터 무결성 3인방을 옮겼고, 전체 pytest 에서
`test_three_data_integrity_agents_defined` 가 깨져서야 발견했다. agent 디렉터리는
문서가 아니라 **실행 계약의 일부**다.

## 워크플로 ↔ agent 계약 (2026-08-30 정합)

| 워크플로 | agent 참조 | 상태 |
|---|---|---|
| `wave-data-integrity.md` | fx-consistency-guard · data-freshness-monitor · cache-poisoning-sentinel | ✅ |
| `wave-design-polish.md` | design · verify-design · motion-designer · brand-voice | ✅ |
| `wave-bug-hunt.md` | bug-hunter · verify-data · qa | ✅ |
| `archive/wave-launch-prep.md` | (아카이브 agent 4개) | 워크플로째 보류 — 출시 무기한 |

같은 날 고친 것: 세 워크플로 전부 죽은 `~/dev/pivoxquant` 절대경로를 참조하고 있었고
(훅 2건과 동일한 원인), `wave-bug-hunt` 는 실재한 적 없는 `audit-code` 를 호출했다.
경로는 **레포 상대경로로 전환** — 절대경로를 다시 박으면 트리가 움직일 때 똑같이 썩는다.
