# Brand Cleanup Audit — 2026-04-24
## Target: "stockpilot / StockPilot / Stock Pilot / stock-pilot / stock_pilot"
## Scope: frontend/src/, routes/, services/, models/, templates/, scripts/, docs/, reports/, migrations/, tests/

---

## Phase 1: Full Grep Results

### Scan Coverage
| Directory | File Types | Result |
|-----------|-----------|--------|
| `frontend/src/` | .tsx, .ts | 0 hits |
| `routes/` | .py | 0 hits |
| `services/` | .py | 0 hits |
| `models/` | .py | 0 hits |
| `services/artifacts/` | .html | 0 hits |
| `migrations/` | all | 0 hits |
| `tests/` | .py | 1 hit |
| `scripts/` | .py | 1 hit |
| `frontend/` | .json, .ts, .md | 1 hit (.claude/launch.json) |
| `docs/` | .md | 10 hits |
| `reports/` | .md | 3 hits |
| Root `.md` files | .md | 7 hits |
| `.claude/agents/` | .md | ~50 hits |

**Total raw hits: ~74**

### Hit Classification

#### LEGIT (skip) — directory path references, historical archive, rule-text
All hits fall into one of these sub-categories:

**A. Directory path references (intentional — directory named `stockpilot/`)**

| File | Line | String |
|------|------|--------|
| `CLAUDE.md` | 45 | `stockpilot/` (dir structure diagram) |
| `CLAUDE.md` | 107, 110 | `cd /Users/seanbae/Desktop/취준/stockpilot ...` |
| `HANDOVER.md` | 100, 108, 169 | `/Users/.../stockpilot/.env` |
| `TODO.md` | 14, 211 | `/Users/.../stockpilot/.env` |
| `LEGAL_CONSULT_PACKAGE.md` | 47–438 (multiple) | `/Users/.../stockpilot/...` file paths |
| `BUG_SWEEP_2026-04-23.md` | 91 | `stockpilot/ai_service.py` |
| `agent_worker/SETUP.md` | 110 | `cd /Users/.../stockpilot` |
| `scripts/run_benchmark_backtest.py` | 47 | `ROOT = Path("/Users/.../stockpilot")` |
| `tests/test_quant.py` | 17 | `cd stockpilot && python3 ...` (comment) |
| `frontend/.claude/launch.json` | 7 | `cd /Users/.../stockpilot/frontend` |
| `docs/archive/BETA_READINESS_PLAN.md` | 289–295 | `/Users/.../stockpilot/...` paths |
| `docs/archive/deploy-guide.md` | 20 | `cd /path/to/stockpilot` |
| `docs/launch/SECRETS_ROTATION_GUIDE.md` | 54 | `# From /Users/.../stockpilot` |
| `docs/launch/SECRETS_ROTATION_GUIDE.md` | 65 | `stockpilot.db` (historical — file does NOT exist on disk; `pivoxquant.db` is the actual db) |
| `docs/launch/AUTO_SYNC_TECH_PLAN.md` | 13, 84 | `stockpilot/kis_service.py` path ref |
| `reports/audit/FIELD_MAPPING_AUDIT_2026-04-23.md` | 6, 665, 674 | `/Users/.../stockpilot` |
| `reports/vercel-redirect-fix.md` | 39 | `stockpilot-frontend` (historical Vercel project name note) |

**B. Archive/historical documents (docs/archive/ — intentional historical record)**

| File | Line | Content |
|------|------|---------|
| `docs/archive/SESSION_2026-04-16.md` | 67 | Rebrand event log: "`stockpilot` → `pivoxquant` 53개 파일" |
| `docs/archive/rebranding-candidates.md` | 11, 673 | Brand planning discussion, `stockpilot.com` domain analysis |
| `docs/archive/env-setup.md` | 59 | Old Railway URL `stockpilot-backend-production.up.railway.app` |
| `docs/archive/ux-innovation-research.md` | 314 | `스톡파일럿의 파일럿` — archived UX research persona name |

**C. Agent rule instruction text (meta-reference — rule says "NOT stockpilot")**

| Pattern | Occurrence count |
|---------|-----------------|
| `Brand: PivoxQuant (NOT stockpilot) — 모든 출력 통일.` | ~48 agent .md files |
| `Stripe Product/Customer metadata에 stockpilot 잔존 금지` | 1 (stripe-billing.md) |
| `From/Reply-To/Subject에 stockpilot 잔존 시 즉시 치환` | 1 (email-deliverability.md) |

These are branding enforcement rules that reference the old name in a "do not use" context. Correct as-is.

**D. Legal document historical note**

| File | Line | Content |
|------|------|---------|
| `LEGAL_CONSULT_PACKAGE.md` | 20 | `구 StockPilot, 2026-04-15 리브랜딩` — accurate legal provenance record |

---

### STALE BRAND — User-exposed UI/copy/title/meta/email strings

**Count: 0**

No hits found in:
- `frontend/src/**/*.tsx` — page titles, meta tags, OG tags, UI copy
- `frontend/src/**/*.ts` — manifest, sitemap, robots, API routes
- `routes/*.py` — Flask route handlers
- `services/**/*.py` — service layer including email sending
- `services/artifacts/**/*.html` — PDF/report HTML templates
- `models/**/*.py` — SQLAlchemy models

---

### INTERNAL — Variable/function/DB column names

**Count: 0**

No code-level internal identifiers containing `stockpilot` found.

---

## Phase 2: STALE BRAND Auto-fix

**No fixes required.** Zero user-exposed brand strings found.

Files changed: **0**

---

## Phase 3: INTERNAL Report (no migration needed)

**No internal variable/function/column names found.**

---

## Phase 4: Verification

### TypeScript compilation
Not re-run — no .ts/.tsx files were modified.

### Build
Not re-run — no source files were modified.

### pytest
Not re-run — no source files were modified.

---

## Summary

| Category | Count | Action |
|----------|-------|--------|
| LEGIT (path refs, archive, rule text) | ~74 | No change |
| STALE BRAND (UI-exposed) | 0 | N/A |
| INTERNAL (var/func/column names) | 0 | N/A |

**Conclusion: Codebase is clean. All stockpilot brand strings in UI-facing code, templates, meta tags, email copy, and route handlers were removed in the 2026-04-15 rebrand. Only intentional directory-path references and archived historical documents remain.**
