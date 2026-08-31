# Agent Upgrade Proposals — 2026-08-30

**Agents scanned**: 23
**Issues found**: 53
**Reference HANDOVER**: v9 (2026-04-25)

## HIGH (11)
- **cache-poisoning-sentinel** — no_verify_policy
  → reference verify-policy for background launch decisions
- **frozen-file-diff-guard** — no_verify_policy
  → reference verify-policy for background launch decisions
- **fx-consistency-guard** — no_verify_policy
  → reference verify-policy for background launch decisions
- **investigate-bug** — no_verify_policy
  → reference verify-policy for background launch decisions
- **migration-guard** — no_verify_policy
  → reference verify-policy for background launch decisions
- **motion-designer** — no_verify_policy
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

## LOW (42)
- **brand-voice** — stale_handover
  → reference HANDOVER v9
- **brand-voice** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **bug-hunter** — stale_handover
  → reference HANDOVER v9
- **bug-hunter** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **bug-hunter** — tool_inflation
  → agent has 16 tools — consider scoping down
- **cache-poisoning-sentinel** — stale_handover
  → reference HANDOVER v9
- **cache-poisoning-sentinel** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **data-freshness-monitor** — stale_handover
  → reference HANDOVER v9
- **data-freshness-monitor** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **design** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **devops** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **email-deliverability** — stale_handover
  → reference HANDOVER v9
- **email-deliverability** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **engineering** — stale_handover
  → reference HANDOVER v9
- **engineering** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **frozen-file-diff-guard** — stale_handover
  → reference HANDOVER v9
- **frozen-file-diff-guard** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **fx-consistency-guard** — stale_handover
  → reference HANDOVER v9
- **fx-consistency-guard** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **investigate-bug** — stale_handover
  → reference HANDOVER v9
- **investigate-bug** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **legal** — stale_handover
  → reference HANDOVER v9
- **legal** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **motion-designer** — stale_handover
  → reference HANDOVER v9
- **motion-designer** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **persona-quant-domain** — stale_handover
  → reference HANDOVER v9
- **product** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **qa** — stale_handover
  → reference HANDOVER v9
- **qa** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **security** — stale_handover
  → reference HANDOVER v9
- **security** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **verify-api** — stale_handover
  → reference HANDOVER v9
- **verify-api** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **verify-data** — stale_handover
  → reference HANDOVER v9
- **verify-data** — missing_phrase:거짓 보고 금지
  → add `거짓 보고 금지` mandate
- **verify-design** — stale_handover
  → reference HANDOVER v9
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
- **verify-ux** — tool_inflation
  → agent has 13 tools — consider scoping down

## Apply
```bash
python scripts/agent_ops/propose_upgrades.py --apply
# review diff, then commit
```