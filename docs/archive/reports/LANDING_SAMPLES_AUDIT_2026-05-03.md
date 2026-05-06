# Landing Samples Audit — 2026-05-03

CEO complaint: "양식 다 옛날 거 같다" (the sample artifacts look old).

## Verdict

**STALE.** All static PDF samples in `frontend/public/samples/` are dated **Apr 27 2026** — generated *before* the v3 design CSS overhaul on **May 1 2026** (`services/artifacts/templates/_*_v3_css.html`) and the email-template refresh on **May 3 2026** (`*_email.html`). The current design lives in:

1. **WeasyPrint PDF templates** — `services/artifacts/templates/{slug}.html` + `_{slug}_v3_css.html` (May 1)
2. **Live React previews** — `frontend/src/app/sample-reports/[slug]/page.tsx` rendering `frontend/src/components/reports/templates/<slug>.tsx` (the React port that backs `/reports/preview/<slug>` for auth users)

The React previews at `/sample-reports/<slug>` are the public, no-auth, current-design surface. They render the same Vantablack + Bronze + Playfair templates as the email/PDF outputs.

## Sample References Found (grep counts)

| Location | Type | Current href | Decision |
|---|---|---|---|
| `frontend/src/components/landing/hero.tsx:226` | "See a sample" CTA | `/samples/weekly_memo.pdf` | UPDATE → `/sample-reports/weekly-memo` |
| `frontend/src/components/landing/personas-preview.tsx:50,58,66,74` | 4 persona cards | `/samples/weekly_memo.pdf` (all 4) | UPDATE → `/sample-reports/weekly-memo` |
| `frontend/src/components/landing/persona-showcase.tsx:252` | "View sample report →" | `/samples/weekly_memo.pdf` | UPDATE → `/sample-reports/weekly-memo` |
| `frontend/src/app/features/explorer/page.tsx:18,19,25,26,27` | 5 sample tile links | `/samples/{slug}.pdf` | UPDATE → `/sample-reports/<slug>` |
| `frontend/src/app/features/reports/page.tsx:29,49,69,89,109` | 5 "View sample" links | `/samples/{slug}.pdf` | UPDATE → `/sample-reports/<slug>` |
| `frontend/src/components/landing/reports-gallery.tsx:94` | 16-card gallery | `/reports/preview/<slug>` (auth-gated dashboard) | UPDATE → `/sample-reports/<slug>` (public route works for landing visitors) |
| `frontend/src/app/(dashboard)/reports/_v1/page-v1.tsx:100` | dashboard catalog `/samples/{slug}.pdf` | dashboard-only legacy page (`_v1`) | LEAVE — not landing |
| `frontend/src/app/(dashboard)/detail/[ticker]/page.tsx:588` | comment only | n/a | LEAVE |
| `frontend/public/samples/*.pdf` (18 files) | static PDFs | n/a | LEAVE in repo (used by `_v1` catalog + dashboard download). Not regenerating in this PR — out of scope and needs WeasyPrint pipeline. Flag for follow-up. |

## Plan

1. Replace all landing-surface `/samples/<x>.pdf` hrefs with `/sample-reports/<slug>` (the live React preview that always reflects current design).
2. Update CTA copy where it explicitly says "PDF" to neutral "sample" wording, since target is now an in-browser preview (not a downloadable PDF).
3. Fix `reports-gallery.tsx` so unauth visitors don't get bounced to `/login`.
4. Leave the static PDF files in `public/samples/` for now — the dashboard `_v1` page still references them and removing them is out of scope. Follow-up task: regenerate PDFs from current templates via WeasyPrint, then either delete `public/samples/` or keep as cache.

## Out of scope (deferred)

- PDF regeneration from current templates (needs WeasyPrint runtime)
- Dashboard `_v1` reports page cleanup
- Removing the 18 stale PDF files from `public/samples/`
