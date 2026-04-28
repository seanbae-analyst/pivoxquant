# /reports v2 — Migration Plan (CFO Archive)

> Companion to `mockup.html` and `SPEC.md`. Describes how to land the v2 archive
> without breaking the existing `/reports` Dossier route or any existing artifact
> consumers (home Card 6, sidebar badge, etc).

---

## 1. Impact summary

| Area | Change | Risk |
|---|---|---|
| Route `/reports` | Replaced behind feature flag | Low — flag default `false` until QA |
| Home page Card 6 (`Companion · Archive`) | Reuses new shared atoms (`<ArtifactKindCard/>`); visual no-op via flag | Zero |
| Sidebar `Reports` nav badge (unread count) | Unchanged. Still consumes `useArtifacts().unreadCount` | Zero |
| Backend `/api/artifacts/list` | **Unchanged** | Zero |
| Backend NEW: `/api/artifacts/stats`, `/api/artifacts/by-month`, `/api/artifacts/generate`, `/api/artifacts/job/:id` | Additive only | Low — new endpoints, no schema migration |
| `Artifact.data_preview.mentioned_tickers` | **Schema tightened** — must always contain `{ticker, name, exchange?}` | Low — backfill optional; legacy rows keep working with fallback to ticker code only |
| Type contracts | Additive — `ArtifactStats`, `ArtifactArchiveMonth`, `MentionedTicker`, `GenerateArtifactBody` | Zero (no removals) |

---

## 2. New components (files to create)

| File | Responsibility |
|---|---|
| `frontend/src/app/(dashboard)/reports/page.tsx` | New page shell. Wraps current /reports with feature flag |
| `frontend/src/components/reports/archive-hero.tsx` | `<ArchiveHeroV2/>` |
| `frontend/src/components/reports/latest-artifact-card.tsx` | `<LatestArtifactCard/>` |
| `frontend/src/components/reports/artifact-kinds-grid.tsx` | `<ArtifactKindsGrid/>` + `<ArtifactKindCard/>` |
| `frontend/src/components/reports/artifact-request-box.tsx` | `<ArtifactRequestBox/>` + 3 tiles |
| `frontend/src/components/reports/artifact-year-timeline.tsx` | `<ArtifactYearTimeline/>` + `<MonthRow/>` |
| `frontend/src/components/reports/mention-row.tsx` | shared 종목명-main row used in latest card and home Card 6 |

All components use existing token surface in `globals.css` — **no new tokens introduced**.

---

## 3. New hooks + types (additive)

Append to `frontend/src/lib/types.ts`:

```ts
export interface MentionedTicker {
  ticker: string;          // "AAPL", "005930.KS"
  name: string;            // "Apple Inc.", "Samsung Electronics"
  exchange?: string | null;// "NASDAQ", "KOSPI"
  change_pct?: number | null;
}

export interface ArtifactStats {
  total: number;
  countYtd: number;
  countMemos: number;
  countBriefs: number;
  countBragCards: number;
  decisionMoving: number;
  byType: Record<ArtifactType, number>;
  nextScheduled: { type: ArtifactType; at: string } | null;
  latestIndexedAt: string;
}

export interface ArtifactArchiveMonth {
  month: string;           // "2026-04"
  artifacts: Artifact[];
  count: number;
}

export interface GenerateArtifactBody {
  type: ArtifactType;
  ticker?: string;
  topic?: string;
}
```

Append to `frontend/src/lib/endpoints.ts` inside the `artifacts` group:

```ts
artifacts: {
  list: "/api/artifacts/list",
  download: (id: number) => `/api/artifacts/${id}/download`,
  preview: (id: number) => `/api/artifacts/${id}/preview`,
  markRead: (id: number) => `/api/artifacts/${id}/read`,
  // v2 additions ↓
  stats: "/api/artifacts/stats",
  byMonth: "/api/artifacts/by-month",
  generate: "/api/artifacts/generate",
  jobStatus: (jobId: string) => `/api/artifacts/job/${jobId}`,
},
```

Append to `frontend/src/lib/hooks.ts`:

```ts
export function useArtifactStats() { … }              // SWR wrapper on API.artifacts.stats
export function useArtifactArchive(month: string | null) { … }
export async function generateArtifact(body: GenerateArtifactBody) { … }  // mutating action, not a hook
```

No existing exports change. `useArtifacts` continues to work unchanged (line 128 of `hooks.ts`).

---

## 4. Backend changes (additive only)

### 4.1 New routes

`routes/artifacts.py`:

```python
@bp.route("/api/artifacts/stats", methods=["GET"])
@login_required
def stats():
    return jsonify(artifact_stats_service.compute(current_user.id))

@bp.route("/api/artifacts/by-month", methods=["GET"])
@login_required
def by_month():
    month = request.args.get("month")  # "YYYY-MM"
    return jsonify(artifact_archive_service.fetch_month(current_user.id, month))

@bp.route("/api/artifacts/generate", methods=["POST"])
@login_required
def generate():
    body = request.get_json(force=True)
    job_id = artifact_generator.enqueue(current_user.id, body)
    return jsonify({"job_id": job_id, "eta_seconds": 240})

@bp.route("/api/artifacts/job/<job_id>", methods=["GET"])
@login_required
def job_status(job_id):
    return jsonify(artifact_generator.status(current_user.id, job_id))
```

### 4.2 New services

| File | Responsibility |
|---|---|
| `services/artifact_stats.py` | Aggregates `Artifact` rows: count, by-type, ytd, decision-moved flag |
| `services/artifact_archive.py` | Server-side group-by-month query |
| `services/artifact_generator.py` | Composes existing `morning_brief_generator`, `weekly_memo_generator`, etc. Job queue is in-memory dict for MVP, can move to RQ/Redis later |

### 4.3 Schema tightening — `Artifact.data_preview.mentioned_tickers`

Schema is tightened but enforcement is best-effort:
- Generators emit `{ticker, name, exchange}` going forward.
- Frontend `<MentionRow/>` falls back to `ticker` if `name` missing — visual graceful-degrade, not a crash.
- Backfill of existing rows is optional (a one-shot script `scripts/backfill_artifact_mentions.py` joins against `securities` table for missing names).

### 4.4 Banned-vocab linter on generator output

Extend `tests/test_no_hardcoded_samples.py` (or add `tests/test_artifact_vocab.py`) to:
1. Fixture-generate one of each `ArtifactType`.
2. Scan the rendered `body_md` / `body_html` / `body_text` for `BUY|SELL|HOLD|recommend|advice|advisory|추천|조언`.
3. Fail the test on any hit.

This closes the runtime-text gap that source-code-only legal-guard misses.

---

## 5. Feature flag

```ts
// frontend/src/lib/flags.ts (add)
export const FF_REPORTS_V2 = process.env.NEXT_PUBLIC_FF_REPORTS_V2 === "1";
```

Inside `app/(dashboard)/reports/page.tsx`:

```tsx
import LegacyDossierPage from "@/components/reports/legacy-dossier-page";
import ReportsV2Page from "@/components/reports/reports-v2-page";
import { FF_REPORTS_V2 } from "@/lib/flags";

export default function Page() {
  return FF_REPORTS_V2 ? <ReportsV2Page /> : <LegacyDossierPage />;
}
```

**v1 preservation:** Existing `/reports/page.tsx` body is moved verbatim to
`components/reports/legacy-dossier-page.tsx`. No code deleted. Roll-back = flip
env var.

`.env.local` for dev: `NEXT_PUBLIC_FF_REPORTS_V2=1`. Production stays `=0` until
QA + design review pass.

---

## 6. Rollout sequence

1. **PR 1 — types + read-only hooks (no UI).**
   - Add `MentionedTicker`, `ArtifactStats`, `ArtifactArchiveMonth`, `GenerateArtifactBody` to `lib/types.ts`.
   - Add `API.artifacts.stats`, `byMonth`, `generate`, `jobStatus` to `lib/endpoints.ts`.
   - Add `useArtifactStats()`, `useArtifactArchive(month)` to `lib/hooks.ts`.
   - Backend: `services/artifact_stats.py`, `services/artifact_archive.py`, two routes.
   - Tests: `tests/test_artifact_stats.py`, `tests/test_artifact_archive.py`.
   - Ship.
2. **PR 2 — generation pipeline.**
   - `services/artifact_generator.py` + 2 routes (`generate`, `job_status`).
   - `generateArtifact()` action in `hooks.ts`.
   - Banned-vocab linter on generator output.
   - Tests: `tests/test_artifact_vocab.py`, `tests/test_artifact_generation_e2e.py`.
   - Ship.
3. **PR 3 — shared atoms.**
   - `<MentionRow/>`, `<ArtifactKindCard/>` (used by both v2 reports and home Card 6).
   - Refactor home Card 6 to consume `<ArtifactKindCard/>` for the bottom-3-quotes block — visual no-op behind home-v2 flag.
   - Ship.
4. **PR 4 — v2 page behind flag.**
   - `<ArchiveHeroV2/>`, `<LatestArtifactCard/>`, `<ArtifactKindsGrid/>`, `<ArtifactRequestBox/>`, `<ArtifactYearTimeline/>`.
   - Mount under flag. Default `off`.
   - QA on staging with flag `on` — full request flow exercised end-to-end (generate → poll → render).
5. **PR 5 — flip flag + delete `legacy-dossier-page.tsx`.**
   - After 2 weeks of stable QA + design review sign-off, flag default flips to `on`.
   - Legacy file deleted in same PR (kept in git history for rollback).
6. **PR 6 (optional, post-launch) — Search Archive (⌘K).**
   - Out of scope for the initial v2; behind its own feature flag.

---

## 7. Disclaimer banner — already mounted

`DisclaimerBanner` mounts once via `app/(dashboard)/layout.tsx`. Verify single
instance still renders below the year timeline. The mockup's footer-disclaimer
block is illustrative; production wiring uses the layout banner with
`variant="reports"` copy:

> "PivoxQuant produces editorial memos, briefs, and analytical artifacts for the
> user's own record-keeping. Nothing in this archive constitutes investment
> advice…"

Same `variant` prop introduced for signals (`variant="signals"`) and home
(`variant="home"`).

---

## 8. Tests / CI

- [ ] `tests/test_no_hardcoded_samples.py` — already covers source files.
- [ ] `tests/test_artifact_vocab.py` — NEW. Fixture-generates each `ArtifactType` and asserts no banned vocabulary in rendered bodies.
- [ ] `tests/test_artifact_stats.py` — NEW. Asserts `/api/artifacts/stats` returns the contract documented in `SPEC.md §6`.
- [ ] `tests/test_artifact_generation_e2e.py` — NEW. Full path: POST `/generate` → poll `/job/:id` → list. Marks the in-memory queue as a known limitation.
- [ ] Visual regression (Playwright) — capture `/reports` at flag `on`. Add to `frontend-tests.yml`.
- [ ] `axe-core` a11y — heading order, all rows have `aria-label`, request tile keyboard-activates.
- [ ] Storybook stories — each `ArtifactType` for `<ArtifactKindCard/>`; latest card with 0 / 1 / 3 mentions.

---

## 9. Migration metrics (record after PR 5 lands)

- Time-to-first-card-render: target ≤700ms p75 on cold cache.
- Generation request → job-done median: ≤4 minutes (matches user-facing copy).
- A11y score: 100/100 on `axe`.
- Zero instances of banned vocabulary in any rendered DOM **or in any artifact body** (Playwright + linter assert both).

---

## 10. Open questions for engineering

1. Job queue: in-memory dict (single-process) or Redis-backed RQ? MVP can ship with the dict; Railway autoscaling later forces RQ. Decide before PR 2.
2. Backfill of `data_preview.mentioned_tickers` for legacy rows — do we run it once before v2 launch, or accept fallback rendering forever? Recommendation: run once, cheap.
3. Search Archive (⌘K) UX — own page or modal command palette inside the archive? Defer to design wave 3.
4. Stripe gating — Brag Card and Year-End Letter are Pro/Premium tier features per `project_biz_plan.md`. Confirm gate location: at request-box tile (greyed out + lock icon for Free) or at generation endpoint (silently 402)? Recommendation: both — visual gate at the tile + server-side enforcement.
