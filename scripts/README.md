# PivoxQuant — `scripts/` cron & one-shot utilities

Operational scripts triggered by Claude Code scheduled-tasks (Max plan, $0)
or run on-demand by the CEO. Zero non-stdlib deps wherever practical.

## CAUS (Continuous Autonomous User Simulation)

**Spec**: [`docs/specs/continuous-user-sim-spec.md`](../docs/specs/continuous-user-sim-spec.md)

### `caus_daily_sweep.py`

Daily launcher for the simulated-user sweep. Phase 1 MVP — writes a per-day
report stub, posts a Slack heads-up, and gracefully no-ops when the session
file is missing (CEO has not yet onboarded the sim alias).

#### Local dry-run

```bash
cd /Users/seanbae/Desktop/취준/stockpilot
python3 scripts/caus_daily_sweep.py
```

Expected output (no `SLACK_WEBHOOK_URL`, no session file):

```
[caus] report stub: .../docs/qa/auto-sim-reports/YYYY-MM-DD.md
[slack-stub] info: daily sweep started · simN · day-K · ...
[slack-stub] warn: user `simN` session missing at `~/.pivoxquant-sim/sessions/simN.json` ...
```

Exit code is always `0` on missing session (graceful — cron must not flap).

#### Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `SLACK_WEBHOOK_URL` | No | Slack incoming webhook. Falls back to `SLACK_WEBHOOK_CAUS`. If neither is set, the script prints `[slack-stub]` lines to stdout (still exits 0). |

#### Claude Code scheduled-task registration

Register once via the `scheduled-tasks` MCP tool
(`mcp__scheduled-tasks__create_scheduled_task`) or the `/schedule` skill:

| Field | Value |
|-------|-------|
| `name` | `caus-daily-sweep` |
| `cron` | `0 18 * * *` (UTC) — equivalent to **03:00 KST** |
| `command` | `cd /Users/seanbae/Desktop/취준/stockpilot && python3 scripts/caus_daily_sweep.py` |
| `timeout_minutes` | 5 (Phase 1 launcher is fast; Phase 2 will increase) |

The task lives in Claude Code Max plan (no GitHub Actions billed minutes, no
external cron-as-a-service). See `feedback_no_extra_cost.md`.

#### D+0 CEO onboarding (one-time per sim alias)

CAUS uses Gmail aliases (`seanbae1521+sim1@gmail.com` ~ `+sim10@gmail.com`)
instead of `DEV_LOGIN_SECRET`. Gmail accepts `+anything` suffixes on a single
inbox — Google ToS-compliant and free.

> **Why not DEV_LOGIN_SECRET?** A 2026-05-10 security guard
> (`routes/__init__.py:97–102`, "M3") refuses prod boot when
> `FLASK_ENV=production` AND `DEV_LOGIN_SECRET` are both set. This guard is
> intentional and stays. Verified by failed Railway redeploy on 2026-05-13.

Per alias (~5 minutes):

1. Open `https://pivoxquant.com` in an incognito window. Enter `BETA_PASSWORD`.
2. Click Google login → "Use another account" → enter
   `seanbae1521+sim{N}@gmail.com` (password is the main Gmail password —
   alias inherits).
3. Complete the 20-question onboarding. Optionally vary answers per `simN` so
   personas (spec §5) diverge.
4. In Railway psql, mark the new user as simulated:
   ```sql
   UPDATE users SET is_simulated = TRUE
   WHERE email = 'seanbae1521+sim1@gmail.com';
   ```
5. Export cookies and `localStorage` via Claude in Chrome MCP, save to
   `~/.pivoxquant-sim/sessions/sim{N}.json`. Suggested shape:
   ```json
   {
     "cookies": [ { "name": "session", "value": "...", "domain": ".pivoxquant.com", "expiry": 1747000000 } ],
     "localStorage": { "pivoxquant.tier": "free" },
     "captured_at": "2026-05-13T12:00:00Z"
   }
   ```
6. From next cron tick on, `caus_daily_sweep.py` finds the file and (Phase 2)
   hands it to the `user-tester` agent.

The directory `~/.pivoxquant-sim/` is CEO-local only — gitignored, never
synced to iCloud/Dropbox. If the laptop is lost, force-reset the sim aliases
in the prod DB.

#### Refresh cadence

Google OAuth refresh tokens expire after **30 days** without activity. The
launcher will Slack-warn when a session file's mtime > 30 days. Repeat
steps 1–5 monthly for each active alias.

## Other cron scripts

| Script | Cadence | Purpose |
|--------|---------|---------|
| `check_price_alerts.py` | 15 min during KR/US market hours | 52W high/low + concentration sweep |
| `morning_brief.py` | Daily 06:00 KST | CEO morning brief artifact |
| `nightly/*.py` | Daily 02:00 KST | Aggregation, ticker health, endpoint smoke |
| `weekly_memo_blast.py` | Sunday 09:00 KST | Weekly memo email blast |
| `legal_monitor/*.py` | Daily 09:00 KST | Regulatory change scanner |

All run inside Claude Code scheduled-tasks (Max plan) — see
`docs/AUTONOMOUS_OPS.md` for the orchestration overview.
