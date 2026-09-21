# PivoxQuant Agent System

> 2026-08-30 재편. **59개 → 25개.** 나머지 33개는 삭제가 아니라
> `.claude/agents/archive/` 로 이동 — 필요하면 언제든 되돌린다.
> 2026-09-21 — 25개 본문을 현재 제품(멈춤 → 기록 → 거울, AI·퀀트·아티팩트 삭제, Render 호스팅)에 맞춰 갱신.

## 왜 줄였나

agent 의 `description` 은 **매 턴 시스템 프롬프트에 로드된다.** 개수가 곧
고정 토큰 비용이다. 59개 시절 description 총량은 12,066 bytes 였고, 그중
다수가 *출시 대비* 감시/게이트 agent 였다 — 출시는 이뤄지지 않았고 무료 클로즈드
베타만 돈다. 유지 비용만 남은 셈.

## 활성 25개

### 핵심 작업 (7)
`engineering` `qa` `design` `product` `devops` `security` `legal`

### 검증 — 실측 강제 (5)
`verify-api` `verify-data` `verify-design` `verify-security` `verify-ux`

> CLAUDE.md 중요원칙 "최신 정보 파악" 의 집행 계층. 기억이 아니라
> 실제 호출/클릭으로 확인하고, 증거 없으면 PASS 를 찍지 않는다.
> 시세 표시는 기본 꺼져 있다 (`MARKET_DATA_DISPLAY_ENABLED`) — `/api/market/*` 503 은 설계다.

### 버그 (2)
`bug-hunter` (모르는 버그 발굴) · `investigate-bug` (알려진 증상 근본원인)

### 데이터 무결성 가드 (3)
`fx-consistency-guard` · `data-freshness-monitor` · `cache-poisoning-sentinel`

> `.claude/workflows/wave-data-integrity.md` 가 `agent:` 로 직접 호출한다. 사고 전력:
> FX 일관성 P0 2회(+52,281% / 700배), 캐시 크로스유저 PII 유출 2회 (사고 코드는 삭제됐지만
> 원화·달러 혼재 포트폴리오와 cache 사이트는 남아 있다). **셋 중 하나라도 옮기면 워크플로가 깨진다.**

### 디자인 (2)
`motion-designer` · `brand-voice`

> `.claude/workflows/wave-design-polish.md` 가 `agent:` 로 직접 호출한다.

### 도메인 — 대체 불가 (6)
| agent | 남긴 이유 |
|---|---|
| `legal-kr-fintech` | 자본시장법 §17 등 한국 금융규제. 일반 `legal` 보다 깊고, 이 제품의 존폐 이슈 |
| `persona-quant-domain` | 거울 도메인 — 선언 벡터(5문항→9축) vs 관찰 9축, 점수·라벨 없음 불변식 |
| `migration-guard` | Alembic P0 사고 2건 전력 (BigInteger 26 test fail, alembic 035 prod 미적용) |
| `frozen-file-diff-guard` | `.claude/frozen_files.yaml` 집행 — legal_filter · behavior · pre_trade · ledger · migrations · 약관 |
| `email-deliverability` | 인증·온보딩·리텐션 메일 + 월간 거울 알림. Brevo cascade 운영 |
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
  beta-onboarding-monitor, cost-monitor, secrets-rotator. 출시 무기한 보류.
  본문은 Railway·AI·아티팩트 시절 것이라 **되살릴 때 먼저 고쳐라.**
- **디자인 세분화** (5) — visual-designer, onboarding-designer,
  pdf-report-designer, mobile-pwa-optimizer, ux-researcher.
- **1회성 가드** (2) — pwa-cache-validator, prod-migration-sync-verifier.
- **결제** (2) — stripe-billing, billing-incident-handler. 결제 게이트(503)로 비활성.
- **기타** (5) — artifact-qa, frontend-test-runner, verify-policy,
  bkit-orchestrator, investment-research.

## 유지 규칙

새 agent 를 추가할 때는 **기존 25개로 안 되는 이유**를 먼저 적는다.
`description` 은 라우팅에 필요한 트리거만 (2줄 이내). 사고 이력·상세 절차는
본문에 쓴다 — 본문은 그 agent 가 실제로 호출될 때만 로드되므로 공짜다.
본문의 경로·숫자는 **측정 날짜와 함께** 적고, 삭제된 표면(services/ai · services/quant ·
services/artifacts · Railway · 페르소나 라벨 · 요금제)을 다시 적지 마라.

## 아카이브 전 확인 (2026-08-30 교훈)

agent 를 옮기기 전에 **그 파일명을 참조하는 테스트·워크플로가 있는지 먼저 grep 한다.**

```bash
grep -rn "<agent-name>" tests/ .claude/workflows/ scripts/
# 워크플로는 `agent: <name>` 선언만 실제 계약이다 — 산문 속 단어는 오탐:
grep -rn "^\s*agent:" .claude/workflows/*.md | sort -u
```

(2026-09-21 측정: tests/ 에 agent 파일명을 강제하는 테스트는 없다. 계약은 워크플로 3개뿐.)
agent 디렉터리는 문서가 아니라 **실행 계약의 일부**다.

## 워크플로 ↔ agent 계약 (2026-09-21 재확인)

| 워크플로 | agent 참조 | 상태 |
|---|---|---|
| `wave-data-integrity.md` | fx-consistency-guard · data-freshness-monitor · cache-poisoning-sentinel | ✅ |
| `wave-design-polish.md` | verify-design · motion-designer · brand-voice · design | ✅ |
| `wave-bug-hunt.md` | bug-hunter · verify-data · qa | ✅ |
| `archive/wave-launch-prep.md` | (아카이브 agent 4개) | 워크플로째 보류 — 출시 무기한 |

경로는 **레포 상대경로**로 쓴다 — 절대경로(`~/dev/pivoxquant` 사고)를 다시 박으면 트리가 움직일 때 썩는다.
