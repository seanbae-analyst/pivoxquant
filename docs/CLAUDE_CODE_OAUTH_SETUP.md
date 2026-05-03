# Claude Code OAuth — GitHub Actions Setup

> **Goal**: Run PivoxQuant's automation workflows on the Claude Max **subscription** (already paid)
> instead of the per-token Anthropic API. Saves ~$10–30/month at current cron cadence.
>
> **Scope**: 2 workflows that today call `from anthropic import Anthropic` —
> `morning-triage.yml` and `self-healing.yml`. The other 4 workflows
> (`legal-risk-monitor`, `agent-health-weekly`, `agent-upgrades-monthly`, `post-deploy-canary`)
> do not invoke Claude and are unaffected.

---

## Background — why OAuth, why this action

The Anthropic SDK has two auth modes:

| Mode | Token format | Where it works | Who pays |
|---|---|---|---|
| **API key** | `sk-ant-api03-…` | `Anthropic(api_key=…).messages.create(…)` (Messages API) | Per-token billing on the API account |
| **OAuth** | `sk-ant-oat01-…` | **Only Claude Code SDK / CLI / Action** — rejected by the Messages API | Claude Pro/Max subscription quota |

The OAuth token is generated locally with `claude setup-token` (Claude Pro/Max subscription required).
Once stored as a GitHub secret named `CLAUDE_CODE_OAUTH_TOKEN`, the
[`anthropics/claude-code-action@v1`](https://github.com/anthropics/claude-code-action) workflow
step authenticates against your subscription and runs Claude Code in the runner.

**Trade-off you should understand**: the OAuth token does **not** work with raw
`anthropic.Anthropic(api_key=…)` Python SDK calls (the Messages API rejects it).
That's why this migration replaces the Python `import anthropic` step with the
GitHub Action — the action wraps Claude Code, which accepts OAuth.

---

## One-time setup (you do this once, ~5 min)

### 1. Generate the OAuth token locally

```bash
claude setup-token
```

Authenticates via browser (opens login.anthropic.com), then prints a token like:

```
sk-ant-oat01-pHl7…<long string>…vQ
```

Token is valid **1 year**. Re-run when it expires (you'll see auth failures in workflow logs).

### 2. Save the token as a GitHub repo secret

```bash
# Pipe straight from the command — token never lives in shell history
claude setup-token | gh secret set CLAUDE_CODE_OAUTH_TOKEN \
    --repo seanbae-analyst/pivoxquant
```

Or via the web UI:

1. Go to <https://github.com/seanbae-analyst/pivoxquant/settings/secrets/actions>
2. **New repository secret**
3. Name: `CLAUDE_CODE_OAUTH_TOKEN`
4. Value: paste the `sk-ant-oat01-…` token
5. Save

### 3. Verify the secret is registered

```bash
gh secret list --repo seanbae-analyst/pivoxquant | grep CLAUDE_CODE_OAUTH_TOKEN
```

Should print: `CLAUDE_CODE_OAUTH_TOKEN  Updated 2026-…`

### 4. Test it on the smaller workflow first

```bash
# Dry-run morning-triage so it doesn't post any GitHub comments
gh workflow run morning-triage.yml \
    --repo seanbae-analyst/pivoxquant \
    -f dry_run=true
gh run watch --repo seanbae-analyst/pivoxquant
```

Look for the `Run Claude Code Action` step — it should show "OAuth authenticated" and
finish without `ANTHROPIC_API_KEY` errors. If anything fails, recheck the secret value
(no trailing whitespace, full `sk-ant-oat01-…` string).

---

## Renewing the token (every ~12 months)

You'll know renewal is needed when workflows start failing with:

```
Error: 401 Unauthorized — OAuth token expired
```

Just re-run the same one-time setup:

```bash
claude setup-token | gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo seanbae-analyst/pivoxquant
```

The new token replaces the old one immediately. Next workflow run picks it up.

---

## What stayed on `ANTHROPIC_API_KEY` (and why)

### `agent_worker/` — Slack integration (deferred to Phase 2)

`agent_worker/` runs as a **long-lived process** (not a CI job). It connects to Slack via the
Slack Events API and proxies messages to Claude using the Messages API directly. The OAuth
token does not work with the Messages API, so this path still requires `ANTHROPIC_API_KEY`.

Two options going forward, pick when convenient:

1. **Defer** — keep `agent_worker/` disabled in production until you decide whether the
   Slack ↔ Claude bridge is worth keeping. PivoxQuant's primary surface is the web app,
   not Slack.
2. **Conditional activation** — set `AGENT_WORKER_ENABLED=1` only when `ANTHROPIC_API_KEY`
   is present. The worker already short-circuits on missing key (see
   `agent_worker/run_worker.py` startup check), so no code change is required — leaving
   `ANTHROPIC_API_KEY` empty in production is sufficient to keep the worker dormant.

This document and the migrated workflows assume **option 1** (defer). Re-enable when
the time comes by populating `ANTHROPIC_API_KEY` in the Railway service env.

---

## What this migration changed (architectural note)

| Before | After |
|---|---|
| `pip install anthropic>=0.39.0` in workflow | Removed |
| `ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}` env | Replaced by `claude_code_oauth_token` action input |
| `python3 scripts/triage/morning_triage.py` runs orchestration **and** the Claude call | Workflow uses `claude-code-action@v1` for the Claude call; the existing Python script's `TRIAGE_DRY_RUN` mode is reused for issue selection / data prep |
| Python script imports `anthropic` and calls `client.messages.create(…)` | Python script unchanged. The yml-level Anthropic invocation is what migrated |

The Python scripts (`morning_triage.py`, `propose_fix.py`) are **not deleted** — they
still drive the data-preparation logic and remain runnable locally with
`ANTHROPIC_API_KEY` for testing. Only the production CI path migrated to OAuth.

---

## Cost expectations after migration

| Workflow | Cron | Approx API cost (before) | Cost (after) |
|---|---|---|---|
| morning-triage | daily 09:00 KST, ~3 issues | ~$0.24/run × 30 ≈ $7/mo | **subscription-included** |
| self-healing | every 12h, dry-run by default | ~$0/mo (dry-run) → ~$5/mo if AUTO_PR=1 | **subscription-included** |
| **Total avoided** | | **~$7–12/mo** | |

Numbers from the script docstrings; verify against your actual Anthropic console
billing once a full month has elapsed post-migration.

---

## Troubleshooting

### "OAuth token expired"
Re-run `claude setup-token | gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo …`. See
"Renewing the token" above.

### "Claude Code Action: no prompt provided"
The action requires a `prompt` input when triggered by `schedule:` or `workflow_dispatch:`
(it auto-detects only on issue/PR comment events). Check the workflow file's
`uses: anthropics/claude-code-action@v1` step has a `with: prompt: …`.

### "anthropic SDK missing" in Python smoke test
That's expected — `pip install anthropic` was removed from the workflow. To run the
Python script locally, install it manually: `pip install anthropic>=0.39.0` and set
`ANTHROPIC_API_KEY` in your local `.env`.

### Workflow accidentally falls back to ANTHROPIC_API_KEY
Run `gh secret list` and confirm `ANTHROPIC_API_KEY` is **not** set as a repo secret.
If it is, the migrated workflow should still prefer `CLAUDE_CODE_OAUTH_TOKEN`, but
removing the old secret avoids surprise charges if a workflow is mistakenly reverted.

```bash
# Optional — only after migration is confirmed working
gh secret delete ANTHROPIC_API_KEY --repo seanbae-analyst/pivoxquant
```

---

## Reference

- [Claude Code GitHub Actions docs](https://code.claude.com/docs/en/github-actions)
- [`anthropics/claude-code-action`](https://github.com/anthropics/claude-code-action) repo
- [`claude setup-token` reference](https://docs.claude.com/en/docs/claude-code/cli-reference) (Pro/Max subscribers only)
