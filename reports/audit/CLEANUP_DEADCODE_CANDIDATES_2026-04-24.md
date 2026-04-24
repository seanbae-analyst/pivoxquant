# Dead Code Candidates — 2026-04-24

## Summary

| Category | Count |
|---|---|
| Frontend orphan landing components (direct) | 0 |
| Frontend orphan landing components (transitively dead: pivox-hero cluster) | 3 |
| Frontend orphan dashboard component (persona-card) | 1 |
| Frontend orphan chart component (interactive-bar-chart) | 1 |
| Frontend orphan report components (artifact-card, preview-modal) | 2 |
| Frontend unused hooks | 0 |
| Frontend unused types | 0 |
| Frontend unused npm packages | 2 |
| Backend orphan services | 0 |
| Backend orphan models | 0 |
| Untracked files (unregistered in git) | 4 (analysis below) |
| `home 2/` directory | 1 empty directory (0 files) |

---

## Category 1: HIGH CONFIDENCE (0 imports, 0 string refs, 0 comment refs)

### Frontend Components

| File | Evidence | Proposed Action |
|---|---|---|
| `frontend/src/components/landing/pivox-hero.tsx` | grep=0 imports in `src/` — no page or component imports `PivoxHero`. CSS comment in globals.css (line 715) is cosmetic only. | DELETE |
| `frontend/src/components/landing/artifact-stack-mockup.tsx` | grep=0 imports in `src/` — only imported by `pivox-hero.tsx` which is itself orphaned. | DELETE (with pivox-hero) |
| `frontend/src/components/landing/stat-strip.tsx` | grep=0 imports in `src/` — only imported by `pivox-hero.tsx` which is itself orphaned. | DELETE (with pivox-hero) |
| `frontend/src/components/charts/interactive-bar-chart.tsx` | grep=0 imports in `src/`. CSS comment in globals.css (line 1381) names it but no TSX/TS file imports it. | DELETE |
| `frontend/src/components/dashboard/persona-card.tsx` | grep=0 imports in `src/app/` and `src/components/`. `PersonaCard` appears only in self-definition + comments in `persona-evolution.tsx` and `persona-glyph.tsx` — neither imports it. | DELETE |
| `frontend/src/components/reports/artifact-card.tsx` | grep=0 `from "@/components/reports/artifact-card"` in entire `src/`. Both `reports/page.tsx` (line 78) and `admin/preview/page.tsx` (line 232) define their **own local** `ArtifactCard` function inline — the shared component is dead. | DELETE |
| `frontend/src/components/reports/preview-modal.tsx` | grep=0 `from "@/components/reports/preview-modal"` in entire `src/`. `admin/preview/page.tsx` (line 328) defines its own local `PreviewModal` inline — the shared component is dead. | DELETE |

### Frontend NPM Packages

| Package | Evidence | Proposed Action |
|---|---|---|
| `@base-ui/react` | grep=0 `from.*"@base-ui/react"` in entire `frontend/src/`. Not imported anywhere. | REMOVE from package.json |
| `class-variance-authority` | grep=0 `from.*"class-variance-authority"` and grep=0 `cva(` in entire `frontend/src/`. Not imported anywhere. | REMOVE from package.json |

---

## Category 2: MEDIUM (0 direct imports, but indirectly referenced or uncertain)

| File | Evidence | Proposed Action |
|---|---|---|
| `frontend/src/components/landing/fade-up.tsx` | grep=0 `from.*"@/components/landing/fade-up"` in pages. Grep for `FadeUp` in `src/components/landing/` returns only the file's own self-definition. However, globals.css has `.pq-fade-up` class at line 2655 which `fade-up.tsx` generates. No TSX consumer found. | REVIEW — likely orphan; CSS class alone does not prove usage |
| `frontend/src/components/landing/companion-teaser.tsx` | grep=0 `from.*"@/components/landing/companion-teaser"` in all pages. Not imported by `landing-v2.tsx`. CSS uses `id="pq-companion-teaser"` but that is self-declared in the component. | REVIEW — likely orphan |
| `frontend/src/components/landing/pdf-stack-mockup.tsx` | grep=0 imports in `src/`. No consumer found. | REVIEW — likely orphan |
| `frontend/src/components/landing/parallax-layer.tsx` | grep=0 imports in `src/`. No consumer found. | REVIEW — likely orphan |
| `frontend/src/components/landing/sticky-scrub-section.tsx` | grep=0 imports in `src/`. No consumer found. | REVIEW — likely orphan |
| `frontend/src/components/landing/flip-landing-shell.tsx` | grep=0 `from.*"@/components/landing/flip-landing-shell"` in pages/app. CSS (globals.css) has `FlipLandingShell` comment block. `flip-page.tsx` imports from it, but `flip-page.tsx` is itself orphaned (see below). | REVIEW — dead if flip-page is deleted |
| `frontend/src/components/landing/flip-page.tsx` | grep=0 `from.*"@/components/landing/flip-page"` in all pages. `splash-page.tsx` comment says it "is purely presentational" inside `FlipLandingShell` but `splash-page.tsx` does NOT import `FlipPage`. | REVIEW — likely orphan |

---

## Category 3: IN USE — Keep

### Landing Components (verified transitively used via `landing-v2` → `app/page.tsx`)

| File | Why Keep |
|---|---|
| `landing-v2.tsx` | Direct import in `app/page.tsx` line 6 |
| `hero.tsx` | Imported by `landing-v2.tsx` |
| `splash-page.tsx` | Imported by `landing-v2.tsx` |
| `marquee-logos.tsx` | Imported by `landing-v2.tsx` |
| `personas-preview.tsx` | Imported by `landing-v2.tsx` |
| `top-nav.tsx` | Imported by `landing-v2.tsx` and `feature-page-shell.tsx` |
| `mobile-drawer.tsx` | Imported by `top-nav.tsx` |
| `hero-spotlight.tsx` | Imported by `hero.tsx` |
| `hero-aurora.tsx` | Imported by `hero.tsx` and `home/today-hero.tsx` |
| `hero-typography.tsx` | Imported by `hero.tsx` |
| `hero-particles.tsx` | Dynamic import in `hero.tsx` |
| `hero-data-stream.tsx` | Dynamic import in `hero.tsx` |
| `report-flip-deck.tsx` | Dynamic import in `hero.tsx` |
| `market-ticker.tsx` | Dynamic import in `hero.tsx` |
| `film-grain.tsx` | Imported by `home/today-hero.tsx` and `home/dossier-desk.tsx` |
| `cta-ink-bleed.tsx` | Imported by `home/today-hero.tsx` |
| `feature-page-shell.tsx` | Imported by 6 feature pages |
| `three-layers.tsx` | Imported by `features/engine/page.tsx` |
| `living-cfo-loop.tsx` | Imported by `features/engine/page.tsx` |
| `engine-models-drawer.tsx` | Imported by `features/engine/page.tsx` |
| `korea-us-desk.tsx` | Imported by `features/global-desk/page.tsx` |
| `deposition-teaser.tsx` | Imported by `features/pre-trade/page.tsx` |
| `persona-showcase.tsx` | Imported by `features/personas/page.tsx` |
| `report-flip-card.tsx` | Imported by `features/reports/page.tsx` |

### Home Components (all in use)

| File | Why Keep |
|---|---|
| `artifact-queue.tsx` | Imported by `home/page.tsx` |
| `dossier-desk.tsx` | Imported by `signals/page.tsx`, `portfolio/page.tsx`, `market/page.tsx` |
| `paper-document.tsx` | Imported by `signals/page.tsx`, `portfolio/page.tsx`, `market/page.tsx` |
| `persona-glyph.tsx` | Imported by `dashboard/persona-card.tsx` (even if persona-card itself is orphaned, persona-glyph is referenced via `@/components/home/persona-glyph`) |
| `positions-ledger-paper.tsx` | Used in home context |
| `signal-paper.tsx` | Used in signals context |
| `this-morning-paper.tsx` | Uses `count-up` and `tick-number` |
| `today-hero.tsx` | Used in home context |

### Dashboard Components (all in use)

| File | Why Keep |
|---|---|
| `living-cfo-status.tsx` | Imported by `home/page.tsx` |
| `persona-evolution.tsx` | Imported by `settings/page.tsx` |
| `rolling-window.tsx` | Imported by `portfolio/page.tsx` |
| `upsell-plus.tsx` | Imported by `home/page.tsx` |
| `weekly-pulse.tsx` | Imported by `home/page.tsx` and `settings/page.tsx` |

### lib/ files (all in use)

| File | Why Keep |
|---|---|
| `api.ts` | Imported by 20+ files |
| `auth.tsx` | Imported by 15+ files |
| `cfo/hooks.ts` | Imported by 8+ components |
| `cfo/useCompanion.ts` | Imported by 6+ components |
| `consent.ts` | Imported by `cookie-consent.tsx` |
| `endpoints.ts` | Imported by 25+ files |
| `format.ts` | Imported by 8+ files |
| `hooks.ts` | Imported by 10+ files |
| `locale.tsx` | Imported by 10+ files |
| `market-hours.ts` | Imported by 6+ files |
| `push.ts` | Imported by `push-permission.tsx` and `settings/page.tsx` |
| `realtime.tsx` | Imported by `providers.tsx` |
| `types.ts` | Imported by 15+ files |
| `useFocusTrap.ts` | Excluded per instructions (new file this session) |
| `utils.ts` | Imported by 30+ files |

### NPM Packages (all in use)

| Package | Evidence |
|---|---|
| `clsx` | Used via `lib/utils.ts` |
| `cmdk` | Used in `terminal/command-palette.tsx` |
| `lightweight-charts` | Used in `terminal/candlestick-chart.tsx` |
| `lucide-react` | Used in 3+ components |
| `motion` | Used via `motion/react` in 5+ files |
| `next` | Framework |
| `react` / `react-dom` | Framework |
| `recharts` | Used in `simulator/what-if/what-if-chart.tsx` |
| `sonner` | Used in `lib/api.ts` and `what-if-result.tsx` |
| `swr` | Used in `lib/hooks.ts` and `lib/realtime.tsx` |
| `tailwind-merge` | Used in `lib/utils.ts` |
| `tw-animate-css` | Imported via CSS at `globals.css` line 2 |

---

## Untracked 4 Files Analysis

### 1. `scripts/briefing.py`

**Status:** Untracked (not in git). Standalone script.

**Summary:** CEO briefing emailer via SendGrid. Sends a noon-slot HTML email to `seanbae1521@gmail.com` from `autopilot@pivoxquant.com`. Reads `autopilot_log.md` from Claude memory, reads `.env` for `SENDGRID_API_KEY`. Has hardcoded action items dated `2026-04-23` (stale). Single slot implemented (`noon`); `slot` argument is parsed but other values fall back to noon format.

**Import dependencies:** `requests` (runtime), stdlib only. No Flask/SQLAlchemy imports.

**Usage:** Not imported by any other Python file in the project. Intended to be called directly as `python scripts/briefing.py noon`. May be triggered by `scheduled-tasks` cron.

**Proposed action:** ADD TO GIT if actively scheduled; otherwise REVIEW staleness of hardcoded action items.

---

### 2. `services/artifacts/data_source_resolver.py`

**Status:** Untracked (not in git). Fully integrated into the codebase.

**Summary:** Single source of truth for artifact data-source provenance. Exposes `resolve_user_data_sources()` (Wave 5, returns `list[str]`) and `resolve_user_data_lineage()` (Wave 6, returns `list[dict]`). Guards against hardcoded broker claims in Jinja templates by querying actual `BrokerConnection` rows.

**Import count:** Imported by 13 files:
- `services/artifacts/weekly_memo_service.py`
- `services/artifacts/brag_card_service.py`
- `services/artifacts/burn_rate_service.py`
- `services/artifacts/self_audit_service.py`
- `services/artifacts/kpi_dashboard_service.py`
- `services/artifacts/risk_board_service.py`
- `services/artifacts/portfolio_segment_service.py`
- `services/artifacts/quarterly_self_report_service.py`
- `services/artifacts/earnings_prebrief_service.py`
- `services/artifacts/monthly_finance_service.py` (imports `_has_active_alpaca`)
- `services/morning_brief_service.py` (imports `_has_active_alpaca`)
- `tests/test_data_source_resolver.py`
- `tests/test_no_hardcoded_samples.py` (reference in comments)

**Proposed action:** ADD TO GIT immediately. This file is load-bearing — removing it would break 10+ artifact services.

---

### 3. `tests/test_data_source_resolver.py`

**Status:** Untracked (not in git). Legitimate test file.

**Summary:** 16 test cases covering both `resolve_user_data_sources` (Wave 5) and `resolve_user_data_lineage` (Wave 6). Tests all branches: `user_id=None`, connected/disconnected Alpaca/KIS, DB failure fallback, journal flag, manual ledger flag, copy-not-reference invariant, KIS read-only label. Uses `monkeypatch` on `_has_active_alpaca` / `_has_active_kis` directly — no Flask app boot required.

**Proposed action:** ADD TO GIT immediately. Provides compliance-critical coverage for 표시광고법 §3 guard.

---

### 4. `tests/test_no_hardcoded_samples.py`

**Status:** Per task brief: "already confirmed, legit, maintain". Confirmed in scope.

**Summary:** Guards against hardcoded sample tickers or money amounts leaking into Jinja templates (legal guard). Referenced by `.github/workflows/legal-guard.yml`. Passes in CI on ubuntu-latest (GNU grep). macOS requires `pytest` as documented in `CLAUDE.md`.

**Proposed action:** ADD TO GIT (if not already). KEEP.

---

## Orphan Directory

| Path | Status |
|---|---|
| `frontend/src/components/home 2/` | Empty directory (0 files). Created as an OS copy artifact. Safe to delete (`rmdir` only — no files at risk). |
