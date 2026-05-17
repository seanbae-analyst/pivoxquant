# PivoxQuant — Autonomous Operations

Last updated: 2026-04-24

This document is the single source of truth for PivoxQuant's automated
quality gates. The goal is a platform that finds its own bugs, files
its own tickets, and proposes its own fixes — so the 1-person CEO can
sleep, travel, and focus on product.

## Unified schedule (KST)

| Time (KST) | Workflow | File | Cadence | Purpose |
|---|---|---|---|---|
| 02:00 | Nightly Bug Hunt | `.github/workflows/nightly-bug-hunt.yml` | daily | Probe 50 tickers, critical endpoints (9×5 min), pytest on main, open Issue |
| 05:00 Mon | Weekly Security Scan | `.github/workflows/weekly-security-scan.yml` | weekly | Dep vulns, secret scan, SAST |
| 06:00 | Daily API Smoke | `.github/workflows/daily-api-smoke.yml` | daily | `/api/health`, `/api/agent/status` kill-switch assertions, KOSPI range check |
| 09:00 | **Morning Triage (Layer B)** | `.github/workflows/morning-triage.yml` | daily | Read overnight issues, Claude root-cause analysis as comment |
| 09:15 | Daily Legal Scan | `.github/workflows/daily-legal-scan.yml` | daily | Fast grep: EN/KR forbidden tokens in routes/services/frontend |
| 10:00 | **Legal Risk Monitor** | `.github/workflows/legal-risk-monitor.yml` | daily | Deep: full canonical list drift, HTML/PDF sample scan, scrub-coverage audit |
| every 2h | **Self-Healing (Layer C)** | `.github/workflows/self-healing.yml` | every 2h (UTC) | Scan Railway logs for recurring errors, propose fix patches, optional Draft PR |
| PR/push | Regression Guards | `.github/workflows/regression-guards.yml` | PR/push | Tier guards, broken-link, contract tests |
| PR/push | Legal Guard | `.github/workflows/legal-guard.yml` | PR/push | Hardcoded sample ticker/$ check (ubuntu GNU grep) |
| PR/push | CI | `.github/workflows/ci.yml` | PR/push | pytest + lint |
| post-deploy | Post-Deploy Canary | `.github/workflows/post-deploy-canary.yml` | on release | Post-deploy smoke + canary |
| per commit | API Health | `.github/workflows/api-health.yml` | on push | Quick endpoint probe |

The three workflows in **bold** are the subject of this document — they
are the "sleep-through-it" layer added 2026-04-24.

## Three-layer architecture

```
        nightly-bug-hunt (Layer A — detection)
                │
                ▼  opens Issue with evidence
        morning-triage  (Layer B — diagnosis)
                │
                ▼  comments root-cause analysis
   self-healing        (Layer C — remediation, every 2h)
                │
                ├─► protected path? → escalation Issue
                ├─► circuit breaker tripped? → escalation Issue
                └─► generate patch → pytest → Draft PR (AUTO_PR=1 only)

   legal-risk-monitor  (orthogonal compliance lane, daily 10:00 KST)
```

### Layer A — Detection (already shipped)
`nightly-bug-hunt.yml` is the existing reconnaissance pass. It opens one
`nightly-bug-hunt` Issue per day with ticker probes, endpoint probes,
and pytest output. No new changes in this rollout.

### Layer B — Diagnosis (new)
`morning-triage.yml` calls Claude (Sonnet) on each open
`nightly-bug-hunt` Issue:

- Input: issue title + body + first 1500 chars of each referenced repo
  file + `git log -n 1` on each referenced file.
- Output: a markdown comment with `Root Cause`, `Confidence`, `Fix
  proposal (max 3 lines)`, `Verification`.
- **Advisory only**: never modifies code, never opens PRs.
- Budget: 3 issues/run × ~$0.08/issue Sonnet → ~$7/month.
- Dedup: once per issue per UTC day (checks for
  `<!-- morning-triage -->` comment marker).

### Layer C — Remediation (new)
`self-healing.yml` runs every 2 hours:

1. `scripts/self_healing/scan_railway_logs.py` — Fetches the last 60
   minutes of Railway logs (via `railway logs` CLI if
   `RAILWAY_TOKEN` secret is set; otherwise falls back to the fixture
   at `scripts/self_healing/fixtures/railway_sample.log` so the
   workflow still succeeds in dry-run/CI).
2. Groups traceback occurrences by `(file, line, exception_class)` and
   emits a JSONL of patterns with count ≥ 3.
3. `scripts/self_healing/propose_fix.py` — For each non-protected hot
   pattern (max 2/run), calls Claude with the surrounding 80 lines of
   source. Claude emits a unified diff or `INSUFFICIENT_EVIDENCE`.
4. Only when `workflow_dispatch.inputs.dry_run=false` **AND**
   `inputs.auto_pr=true`: the patch is applied on a new branch, pytest
   runs, and if green a Draft PR is opened. Scheduled runs always dry.

**Protected paths (never auto-patched):**
`autotrader.py`, `risk_defense.py`, `services/legal_filter.py`,
`services/legal/`, `services/agents/legal_gate.py`, `billing/`,
`routes/auth*`, `security.py`, `migrations/`. Hits on these paths open
an escalation Issue labeled `self-healing,escalation`.

**Circuit breaker:** 3 failed auto-fix attempts on the same
fingerprint within 24 hours (tracked in
`self_healing_artifacts/history.json` on the runner) stops retries and
files an escalation Issue.

### Compliance lane — Legal Risk Monitor
`legal-risk-monitor.yml` runs daily at 10:00 KST (1 hour after
`daily-legal-scan.yml` so a pre-existing advisory-term regression is
caught by the cheaper workflow first). What it adds:

| Check | Kind | Severity if found |
|---|---|---|
| HTML sample (`samples/artifacts/*.html`) contains canonical forbidden term | artifact_sample | **critical** |
| PDF sample (`samples/pdf/*.pdf`) contains canonical forbidden term | pdf_sample | **critical** |
| Expected artifact service (`services/artifacts/*_service.py`, `ai_service.py`, `morning_brief_service.py`, `alert_service.py`) does NOT call `scrub_text` / `safe_scrub` / `scrub_signal` | missing_scrub | **high** |
| Canonical term from `FORBIDDEN_DIRECTIVE_TERMS` appears in production source (routes/services/frontend/src) without a negation marker | source_drift | **medium** |
| Runtime DB scan via admin endpoint (if `DB_SCAN_URL`+`DB_SCAN_TOKEN` set) | runtime_db | **critical** |

Severity rollup = max of all findings. `critical` triggers Slack
notification (if `SLACK_WEBHOOK_URL` set). `none` auto-closes stale
Issues labeled `legal-monitor`.

## SLA + escalation

| Severity | First response | Channel | Ownership |
|---|---|---|---|
| critical | immediate (Slack + Issue) | `@seanbae-analyst` | CEO |
| high | same business day | GH Issue | CEO |
| medium | within 72 h | GH Issue | CEO |
| low / advisory | weekly review | GH Issue (no ping) | CEO |

All escalations for the new layers use the label prefix
`self-healing,escalation` or `legal-monitor`. Weekly retro should grep
these labels to inform the next sprint.

## Cost budget

| Item | Per run | Monthly |
|---|---|---|
| morning-triage (3 × Sonnet call) | ~$0.24 | ~$7.2 |
| self-healing (2 × Sonnet call × 12 runs/day) | ~$0.16 | ~$96 (cap) |
| legal-risk-monitor (no LLM) | $0 | $0 |
| **Total new monthly cost** | | **~$105 (worst case)** |

In practice self-healing will mostly hit `INSUFFICIENT_EVIDENCE` and
skip the call, so the realistic month-1 spend is $15–30. If the
Railway log source is unconfigured (no `RAILWAY_TOKEN`), self-healing
consumes $0 — it simply exits with 0 hot patterns.

**Cap enforcement:** `SELF_HEALING_MAX_PATTERNS` (default 2) is the
hard per-run cap. Raising it requires editing the workflow — no
dynamic scaling. If spend spikes, set `DRY_RUN=1` in the repo variables
to freeze all LLM calls.

## Secrets + variables checklist (CEO action)

### Required secrets (GitHub → Settings → Secrets and variables → Actions)
- [ ] `ANTHROPIC_API_KEY` — new. Sonnet access. Used by morning-triage + self-healing.
- [x] `GITHUB_TOKEN` — GitHub auto-provides, no action.
- [x] `DEV_LOGIN_SECRET` — already set (used by nightly-bug-hunt).
- [ ] `RAILWAY_TOKEN` — optional. Without it, self-healing falls back to the fixture and surfaces 1 pattern for testing.
- [ ] `SLACK_WEBHOOK_URL` — optional. Without it, Slack step is skipped silently.
- [ ] `DB_SCAN_URL`, `DB_SCAN_TOKEN` — optional. Enables runtime DB
  legal scan via an admin endpoint.

### Optional repo variables
- `RAILWAY_SERVICE` — Railway service name (default `web`).

## First-run checklist

All three new workflows default to **dry-run** when triggered by their
scheduled cron:

- `morning-triage.yml`: `TRIAGE_DRY_RUN=1` when `inputs.dry_run != 'false'`.
- `self-healing.yml`: `SELF_HEALING_DRY_RUN=1` and `AUTO_PR=0` when
  scheduled. Only `workflow_dispatch` with explicit `dry_run=false` +
  `auto_pr=true` can open a PR.
- `legal-risk-monitor.yml`: Issue creation skipped when
  `inputs.dry_run == 'true'`. The scheduled cron has no inputs, so
  scheduled runs **do** create Issues. Flip to dry-run manually only if
  the first scheduled run floods the tracker.

Graduation path:
1. **Week 1** — observe dry-run comments + artifact uploads. Confirm no
   false positives on morning-triage analysis quality.
2. **Week 2** — flip morning-triage to live by editing the scheduled
   cron input (or adding `env.TRIAGE_DRY_RUN: '0'` directly to the
   workflow). It will now start posting Claude analyses as comments.
3. **Week 3** — enable self-healing Draft PRs by running
   `workflow_dispatch` with `dry_run=false`, `auto_pr=true`. Review
   each Draft PR manually; do **not** enable auto-merge yet.
4. **Month 2+** — once a pattern of good PRs is established, consider
   `AUTO_MERGE=1` via a separate workflow (not shipped in this batch —
   see Deferred).

## Local dev smoke tests

```bash
# 2026-05-17 wave 13: 경로 갱신 — repo relocated to ~/projects/pivoxquant
cd ~/projects/pivoxquant

# morning-triage dry-run — prints prompts but no API calls
TRIAGE_DRY_RUN=1 GITHUB_REPOSITORY=seanbae-analyst/pivoxquant \
  python3 scripts/triage/morning_triage.py

# self-healing scan against fixture
SELF_HEALING_DRY_RUN=1 \
  python3 scripts/self_healing/scan_railway_logs.py
cat self_healing_artifacts/railway_patterns.jsonl

SELF_HEALING_DRY_RUN=1 \
  python3 scripts/self_healing/propose_fix.py

# legal-risk-monitor (no LLM — always safe to run locally)
python3 scripts/legal_monitor/monitor.py
cat legal_monitor_artifacts/report.md
```

## Deferred / out of scope

1. **Regulatory RSS ingestion** — FSC / KOFIA / KRX notices ingested
   into Issues. Requires feed parsing + dedup + classifier. Estimated
   2-day effort, tracked as a standalone item.
2. **Sentry integration** — `repository_dispatch: sentry.issue` is
   already wired into `self-healing.yml`, but we have no Sentry
   project yet. Once Sentry is provisioned, set the webhook URL to
   `https://api.github.com/repos/<owner>/<repo>/dispatches` with the
   event type `sentry.issue`.
3. **AutoMerge for self-healed PRs** — intentionally not built. Every
   auto-generated fix is a Draft PR awaiting human review. The CEO
   decides when (and whether) to enable `auto-merge` per-PR.
4. **Multi-patch-per-run for self-healing** — current flow pushes only
   the last applied branch. Fine for initial deploys; revisit once we
   see >1 hot pattern per run consistently.
5. **Cross-workflow deduplication** — if `daily-legal-scan` and
   `legal-risk-monitor` both open Issues on the same drift the same
   morning, there will be two separate Issues. They use different
   labels (`autopilot,legal` vs `legal-monitor`) so they don't
   collide on comment updates.
6. **Cost alerting on ANTHROPIC_API_KEY usage** — currently visible
   only in the Anthropic dashboard. Consider adding a monthly cost
   report once spend stabilizes.

## Failure mode reference

| Symptom | Likely cause | Fix |
|---|---|---|
| morning-triage comments say `[ERROR] ANTHROPIC_API_KEY not set` | Secret missing | Add secret, re-run workflow |
| morning-triage posts but with `[DRY_RUN]` text | Scheduled run with default dry-run | Expected. Flip via `workflow_dispatch` |
| self-healing exits with 0 patterns | No recurring errors, or `RAILWAY_TOKEN` unset + no fixture hits | Check Railway logs manually; fixture ships a known pattern for CI smoke |
| legal-risk-monitor always `pdftotext not installed` medium finding | System lacks poppler-utils | Workflow installs it; for local, `brew install poppler` |
| Draft PR not created despite `auto_pr=true` | pytest failed, or `check` / apply step refused patch | Inspect artifact `self-healing-<runid>` |
