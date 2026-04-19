# Secrets Rotation Guide — PivoxQuant

**Last updated:** 2026-04-18
**Owner:** CEO (sole-op) — this is a manual-action checklist. Nothing here is automated.
**Audience:** Anyone with Railway + Vercel + GitHub admin access (today: just you).

---

## 1. Why this document exists

During the Wave 1 beta launch, the beta-gate password **`***REDACTED***`** was committed
to the public GitHub repository (`seanbae-analyst/pivoxquant`) across multiple
commits. Git history is effectively permanent; even if the file is removed from
the working tree, the value remains retrievable via:

```
git log --all -p -S '***REDACTED***'
```

Anyone who cloned the repo (including archive/mirror bots, fork tooling, and
GitHub's own search index) has the value. It must be rotated before any
user-facing traffic that is not the CEO's own machine.

This guide also inventories every other secret that is provisioned into the
running system, so there is a single place to check when "rotate everything"
becomes necessary (breach, former contractor, etc.).

---

## 2. Exposed secrets (confirmed)

| Secret | Scope of exposure | Severity |
|---|---|---|
| `BETA_PASSWORD=***REDACTED***` | Public GitHub commits (5+) | **MEDIUM** (gate only — no money, no PII behind it) |

### 2.1 Why it is only MEDIUM, not HIGH

- The beta gate protects a pre-launch UI. There is **no real brokerage order flow**
  behind it (KIS is read-only; Alpaca is paper). A leaked password grants UI
  access, not account compromise.
- Per-user auth is still enforced via Google/Kakao OAuth — the beta password
  is a pre-auth gate, not a session credential.

If a real user account is ever placed behind this gate (after launch), upgrade
this entry to HIGH and trigger Section 3.

---

## 3. Suspected but unverified exposures

Run these checks before declaring the repo clean:

```bash
# From /Users/seanbae/Desktop/취준/stockpilot
git log --all -p | grep -iE '(api[_-]?key|secret|password|token|bearer)' \
  | grep -viE '(example|placeholder|<your|YOUR_|_example)' \
  | head -200
```

If any non-placeholder value appears in the diff, add it to Section 2 and rotate.

Known files that **should never** be committed:

- `.env` (gitignored — verify: `git check-ignore -v .env`)
- `stockpilot.db`, `pivoxquant.db` (SQLite — may contain encrypted broker creds)
- `*.pem`, `*.key`, service-account JSONs

---

## 4. Full secret inventory (for "rotate everything" scenario)

Source of truth: `.env.example` at repo root. Every variable listed there is
a secret that lives in Railway (backend) or Vercel (frontend) — never in git.

### 4.1 Backend (Railway → Variables tab)

| Variable | Provider console URL | Rotation difficulty |
|---|---|---|
| `SECRET_KEY` | self-generate | trivial — invalidates sessions |
| `PIVOX_BROKER_ENCRYPTION_KEY` | self-generate | **DANGEROUS** — re-encrypts ALL stored KIS/Alpaca creds or they are lost |
| `CSRF_SECRET` | self-generate | trivial |
| `GOOGLE_CLIENT_SECRET` | <https://console.cloud.google.com/apis/credentials> | easy |
| `KAKAO_CLIENT_SECRET` | <https://developers.kakao.com/console/app> | easy |
| `ANTHROPIC_API_KEY` | <https://console.anthropic.com/settings/keys> | easy |
| `FMP_API_KEY` | <https://site.financialmodelingprep.com/developer/docs/dashboard> | easy |
| `FRED_API_KEY` | <https://fred.stlouisfed.org/docs/api/api_key.html> | easy |
| `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` | <https://app.alpaca.markets/paper/dashboard/overview> | easy |
| `KIS_APP_KEY` / `KIS_APP_SECRET` | <https://apiportal.koreainvestment.com/> | medium — re-issue app |
| `STRIPE_SECRET_KEY` | <https://dashboard.stripe.com/apikeys> | easy |
| `STRIPE_WEBHOOK_SECRET` | <https://dashboard.stripe.com/webhooks> | easy |
| `SENDGRID_API_KEY` | <https://app.sendgrid.com/settings/api_keys> | easy |
| `SENTRY_DSN` | <https://sentry.io/settings/projects> | easy |
| `BETA_PASSWORD` | self-choose | trivial (see Section 5) |
| `DATABASE_URL` | Railway auto-rotates on DB recreation | HIGH impact — avoid |

### 4.2 Frontend (Vercel → Project → Settings → Environment Variables)

Any `NEXT_PUBLIC_*` variable is baked into the client bundle and is **not a secret**
by definition. Do not store secrets there.

---

## 5. Rotate `BETA_PASSWORD` — step-by-step

### 5.1 Pick a new password

Choose one of these (or generate your own with `openssl rand -base64 18`):

```
betanxf-2026-gate-q2
pivoxquant-earlybird-7b2e
signalgate-launch-4a91c3
```

Guidelines:
- ≥ 16 chars
- No dictionary words tied to the project name
- Rotate again the day you flip to public GA

### 5.2 Update Railway

1. Railway dashboard → project `pivoxquant` → **Variables** tab
2. Find `BETA_PASSWORD`, click pencil, paste new value
3. Railway auto-redeploys (~90s). Verify via `/api/health` headers.

### 5.3 Update Vercel (if the gate is checked client-side)

1. Vercel dashboard → project `pivoxquant` → **Settings** → **Environment Variables**
2. If `BETA_PASSWORD` exists there too, update it **in all three environments**
   (Production, Preview, Development).
3. Trigger a redeploy (Deployments → latest → Redeploy).

### 5.4 Notify existing beta testers

- Private DM with the new value — **never** email it, **never** post in a channel
  that gets archived to a public search index.
- Record the rotation date in `MEMORY.md` under `# Brand`.

### 5.5 Update `CLAUDE.md` and memory

The memory file lists the current beta password as `***REDACTED***`. Update the
`# Brand` section to reflect the rotated value.

---

## 6. Optional: Git history cleanup (BFG Repo-Cleaner)

Removing the leaked value from git history is **defense-in-depth only** —
assume any public git history is already mirrored. Only do this if the password
value is embarrassing enough to justify rewriting every clone.

```bash
# Install BFG (once)
brew install bfg

# Fresh mirror clone (DO NOT do this on your working checkout)
cd /tmp
git clone --mirror https://github.com/seanbae-analyst/pivoxquant.git
cd pivoxquant.git

# Create a replacements file
cat > /tmp/bfg-replacements.txt <<'EOF'
***REDACTED***==>***REMOVED***
EOF

# Rewrite history
bfg --replace-text /tmp/bfg-replacements.txt
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Force push (DESTRUCTIVE — coordinate with anyone who has a clone)
git push --force
```

**Consequences:** every existing clone becomes orphaned; every open PR needs
rebase; every deploy pipeline that pins to commit SHAs breaks. Not worth it for
a MEDIUM-severity leak.

Recommended action: **rotate the secret, skip the rewrite.**

---

## 7. Rotation cadence (going forward)

| Secret class | Cadence |
|---|---|
| `BETA_PASSWORD` | Every 30 days while in beta, OR on any suspected leak |
| OAuth client secrets | Annually, OR on contractor departure |
| Broker API keys | Quarterly, AND on any suspected compromise |
| `PIVOX_BROKER_ENCRYPTION_KEY` | **Never rotate casually** — requires re-encrypting DB |
| Stripe keys | On key-list audit (Stripe flags anomalies automatically) |
| Anthropic / FMP / FRED | On vendor breach disclosure |

---

## 8. Incident log (append-only)

| Date | Event | Action taken |
|---|---|---|
| 2026-04-15 | `BETA_PASSWORD=***REDACTED***` committed publicly | PENDING — see Section 5 |
| | | |
