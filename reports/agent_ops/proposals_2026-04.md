# Agent Upgrade Proposals — 2026-04-25

**Agents scanned**: 35
**Issues found**: 63
**Reference HANDOVER**: v9 (2026-04-25)

## HIGH (10)
- **autopilot-monitor** — no_verify_policy
  → reference verify-policy for background launch decisions
- **bkit-orchestrator** — no_verify_policy
  → reference verify-policy for background launch decisions
- **frontend-test-runner** — no_verify_policy
  → reference verify-policy for background launch decisions
- **investigate-bug** — no_verify_policy
  → reference verify-policy for background launch decisions
- **migration-guard** — no_verify_policy
  → reference verify-policy for background launch decisions
- **persona-quant-domain** — no_verify_policy
  → reference verify-policy for background launch decisions
- **verify-api** — no_verify_policy
  → reference verify-policy for background launch decisions
- **verify-data** — no_verify_policy
  → reference verify-policy for background launch decisions
- **verify-security** — no_verify_policy
  → reference verify-policy for background launch decisions
- **verify-ux** — no_verify_policy
  → reference verify-policy for background launch decisions

## MEDIUM (1)
- **audit** — missing_delegation
  → delegate to specialist `agent-ops`

## LOW (52)
- **analytics** — stale_handover
  → reference HANDOVER v9
- **analytics** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **artifact-qa** — stale_handover
  → reference HANDOVER v9
- **artifact-qa** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **audit** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **bkit-orchestrator** — stale_handover
  → reference HANDOVER v9
- **brand-voice** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **bug-hunter** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **bug-hunter** — tool_inflation
  → agent has 16 tools — consider scoping down
- **customer** — stale_handover
  → reference HANDOVER v9
- **customer** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **design** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **devops** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **docs** — stale_handover
  → reference HANDOVER v9
- **docs** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **email-deliverability** — stale_handover
  → reference HANDOVER v9
- **email-deliverability** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **engineering** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **finance** — stale_handover
  → reference HANDOVER v9
- **finance** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **growth** — stale_handover
  → reference HANDOVER v9
- **growth** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **integrations** — stale_handover
  → reference HANDOVER v9
- **integrations** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **investigate-bug** — stale_handover
  → reference HANDOVER v9
- **investigate-bug** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **legal** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **marketing** — stale_handover
  → reference HANDOVER v9
- **marketing** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **pdf-report-designer** — stale_handover
  → reference HANDOVER v9
- **pdf-report-designer** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **persona-quant-domain** — stale_handover
  → reference HANDOVER v9
- **pitch** — stale_handover
  → reference HANDOVER v9
- **pitch** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **product** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **qa** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **regulatory-monitor** — stale_handover
  → reference HANDOVER v9
- **regulatory-monitor** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **security** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **strategy** — stale_handover
  → reference HANDOVER v9
- **strategy** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **stripe-billing** — stale_handover
  → reference HANDOVER v9
- **stripe-billing** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **verify-api** — stale_handover
  → reference HANDOVER v9
- **verify-api** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **verify-data** — stale_handover
  → reference HANDOVER v9
- **verify-data** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **verify-design** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **verify-security** — stale_handover
  → reference HANDOVER v9
- **verify-security** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **verify-ux** — stale_handover
  → reference HANDOVER v9
- **verify-ux** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate

## Apply
```bash
python scripts/agent_ops/propose_upgrades.py --apply
# review diff, then commit
```