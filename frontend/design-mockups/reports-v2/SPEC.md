# /reports v2 — CFO Archive · Component Spec

> Single source of truth for the `/reports` route rebuild as the **CFO Archive**.
> Sibling spec to `home-v2/SPEC.md` and `signals-v2/SPEC.md`. All tokens reference
> `frontend/src/app/globals.css` (design system v3, locked 2026-04-27). Do **not**
> introduce new colors, fonts, or radii.

The current `/reports` route is the legacy "Dossier" page. v2 retires that name
and reframes the surface as the user's **published artifacts library** — Today's
Memo, Weekly Pulse, Earnings Pre-Brief, Brag Card, Year-End Letter, Quarterly Audit.
This is the user-facing manifestation of the **User as CFO** product concept
(memory: `product_concept_cfo.md`, 2026-04-19).

---

## 0. Page-level shell

| Region | Element | Source / Notes |
|---|---|---|
| Top nav | `<TopBar/>` | unchanged; `Archive` nav item gets `.active` |
| Top ticker | `<TopTicker/>` | **reuse** — full-bleed, hairline above + below |
| CFO status | `<LivingCFOStatusBar variant="reports">` | **reuse + variant** — see §1.1 |
| Hero | `<ArchiveHeroV2/>` | **NEW** — sibling of `TodayMemoHeroV2` / `SignalsHeroV2` |
| Latest artifact | `<LatestArtifactCard/>` | **NEW** — full-width 2-col card |
| Gallery | `<ArtifactKindsGrid/>` (3×2 of `<ArtifactKindCard/>`) | **NEW** — 6 kinds |
| Request box | `<ArtifactRequestBox/>` (3 tiles) | **NEW** |
| Year timeline | `<ArtifactYearTimeline/>` (12-month rows) | **NEW** |
| Disclaimer | `<DisclaimerBanner/>` | **reuse** — already in `(dashboard)/layout.tsx` |
| Foot | `<FootSignature/>` | **reuse**, eyebrow text "Archive · Volume IV" |

Container: `max-w-[1280px]` mx-auto, `px-6`. Body `--pq-ink`.

---

## 1. Hero — `ArchiveHeroV2`

| Prop | Type | Source |
|---|---|---|
| `eyebrow` | `string` (always `"Archive · CFO"`) | static |
| `headline` | `string` w/ `<span class="br">…</span>` accents on `published` and `artifacts` | static editorial copy (locked) |
| `body` | `string` | derived from `useArtifactStats()` — see §6 GAP |
| `counts` | `{ memos: number; briefs: number; bragCards: number }` | from `useArtifactStats()` |
| `loading` | `boolean` | combined SWR |

Visual rules (mockup §HERO):
- 80px top, 64px bottom padding. Hairline-bottom seal only.
- H1 Playfair 500 / 48px / 1.05 / `--pq-track-tight`.
- Bronze "br" italic: `published`, `artifacts`.
- Body Source Serif 4, max-width 720px, `rgba(245,240,232,0.82)`.
- Inline counts use `.num` mono tabular, ivory color.
- CTAs: `pq-cta` "Read today's memo" + `pq-link` "Search archive · ⌘K".
- Eyebrow caption: "Drafted by AI · Reviewed by you".

### 1.1 CFO status bar — variant copy

`<LivingCFOStatusBar variant="reports">`:
- `seg 1`: `CFO ROOM · OPEN`
- `seg 2`: `Library indexed · ${formatKST(latestIndexedAt)}`
- `seg 3`: `Next scheduled · ${nextScheduledType} · ${formatKST(nextScheduledAt)}`
- `seg 4` (right): `Lifetime artifacts ${total}  ·  YTD ${countYtd}`

Same `variant` prop introduced for signals (§1.1 of signals SPEC). Single switch
statement covers all three pages.

---

## 2. Latest artifact — `LatestArtifactCard`

Full-width 2-column card. Border `--pq-hairline`, hover bronze, padding 52/56.

**Left column:**
- Type pill (`Today's Memo` / `Weekly Pulse` / etc).
- "Pull quote" — Playfair 30px, weight 500, line-height 1.15. The artifact's `headline` text with optional bronze italic accents on key phrases.
- Body — Source Serif 4 14.5px, 1.65 line-height, ivory-soft. Two sentences max.

**Right column ("Mentioned"):**
- Eyebrow `Mentioned`, dim.
- 2–3 ticker rows. **종목명 main pattern enforced**:
  - Name (Playfair 18px ivory, weight 500) — top.
  - Ticker code (mono 10px `rgba(245,240,232,0.45)` letter-spacing 0.14em) — bottom.
  - Right-aligned mono `+/-X.XX%` in KR color.
- Bottom row: `pq-link` "Listen · 4:12" + "Download PDF".

Whole card is `<a href="/reports/{artifactId}">`. Corner CTA `Open full memo ›`.

Source: latest artifact from `useArtifacts({ limit: 1 })` — sorted by `sent_at desc` server-side. The mention list comes from `artifact.data_preview.mentioned_tickers` (already on the `Artifact` type — see `lib/types.ts` line 432).

---

## 3. Artifact kinds gallery — `ArtifactKindsGrid` + `ArtifactKindCard`

3-col × 2-row grid, gap 12px. 6 cards, **one per `ArtifactType`** enum value.

### Mapping to backend enum

The `ArtifactType` enum in `lib/types.ts` (verified 2026-04-27, line 414–421):

```ts
export type ArtifactType =
  | "weekly_memo"
  | "morning_brief"
  | "earnings_prebrief"
  | "monthly_brag"
  | "quarterly_review"
  | "risk_report"
  | "custom";
```

Card mapping (display-name + cadence):

| Card position | `ArtifactType` | Display name | Cadence label | Schedule |
|---|---|---|---|---|
| 1 | `morning_brief` | Today's Memo | `Daily` | Auto · 06:00 KST · Mon–Fri |
| 2 | `weekly_memo` | Weekly Pulse | `Weekly` | Auto · Sun 07:00 KST |
| 3 | `earnings_prebrief` | Earnings Pre-Brief | `Pre-Earnings` | On-demand · 24h before print |
| 4 | `monthly_brag` | Brag Card | `Quarterly` | Auto · End of quarter (note: backend enum says "monthly" but product cadence is quarterly per `product_concept_cfo.md`) |
| 5 | `custom` | Year-End Letter | `Annual` | Auto · 31 Dec |
| 6 | `quarterly_review` | Quarterly Audit | `Self-Audit` | Auto · End of quarter |

(`risk_report` is referenced from the request box §4 instead of the gallery; gallery
prioritizes the 6 user-facing CFO artifacts.)

### `ArtifactKindCard` composition

Each card:
- Type pill (`Daily` / `Weekly` / `Pre-Earnings` / `Quarterly` / `Annual` / `Self-Audit`).
- **Display name** Playfair 22px ivory weight 500 — 종목명 main pattern, except here the "name" is the artifact kind, not a ticker. The pattern still applies: editorial name on top, mono dim sub-line beneath.
- **Sub-line** mono 10px `rgba(245,240,232,0.45)` — the cadence (`Auto · 06:00 KST · Mon–Fri`).
- **Description** Source Serif 4 13.5px, 2-line summary.
- **Meta-row** (2-col, hairline above):
  - `Last published` + ISO date / human-readable.
  - `Next due` + ISO date / "Queued · AAPL · 30 Apr".

Whole card is `<a href="/reports?type={artifactType}">` to drill into that kind's archive.

Source: aggregate from `useArtifacts({ limit: 9999 })` grouped by `type`, plus a small
helper `useArtifactStats()` (GAP — see §6) for next-due dates.

---

## 4. Request box — `ArtifactRequestBox`

3 horizontal request tiles. On click: opens a confirmation modal, then POSTs to a
generation endpoint. **GAP: backend endpoint missing for on-demand generation.**

Tiles:

| Tile | What | Backend |
|---|---|---|
| Brag Card (current quarter) | Compose Q-to-date brag card | **GAP** — `POST /api/artifacts/generate` body `{ type: "monthly_brag" }` |
| Earnings Pre-Brief | Queue a pre-brief for `ticker` (autocomplete from book + watchlist) | **GAP** — `POST /api/artifacts/generate` body `{ type: "earnings_prebrief", ticker }` |
| Risk Note | Free-text request → custom artifact | **GAP** — `POST /api/artifacts/generate` body `{ type: "risk_report", topic }` |

> **2026-06-11 resolution** — `POST /api/artifacts/generate` shipped (synchronous; no
> job id — `status: "ready"` on resolve means the artifact row already exists) and the
> GAPs above closed with two contract corrections:
> 1. `ticker` rides under `params.ticker`, not top-level (the top-level field was
>    ignored by the backend → every Earnings Pre-Brief request 400'd).
> 2. The **Risk Note tile is now the Risk Board tile**. `type: "risk_report"` never
>    existed in the backend dispatch (dead on click), and a free-text personalized AI
>    memo is 투자자문-adjacent — parked pending counsel review (Q1–Q15). The tile posts
>    `{ type: "risk_board" }` (existing Pro deck: VaR, drawdown, tail ratio, sector
>    concentration — the content this tile advertised). `risk_report` survives
>    server-side only as a normalising alias for stale tabs. `topic` is gone from
>    `GenerateArtifactBody`; the sample `generateArtifact` later in this doc is
>    superseded by `src/lib/hooks.ts:generateArtifact`.

Tile composition:
- Display name (Playfair 20px) + sub-line (mono dim) — 종목명 main pattern.
- Description (Source Serif 13px).
- Bronze CTA `Generate now ›` / `Queue for AAPL ›` / `Open request ›`.

The existing `API.market.morningBriefGenerate = "/api/brief/generate-now"` already
exists for the morning brief; this is the architectural pattern. New endpoint
proposed: `API.artifacts.generate` returning a job id. Polling via existing
`useArtifacts` works (the new artifact appears when ready).

Avg. turnaround copy ("4 minutes") is illustrative — the real value should come
from the generation status hook.

---

## 5. Year timeline — `ArtifactYearTimeline`

12-month rolling list. Each row: `[Month abbrev] [Year mono] [Titles preview] [Count]`.

Grid columns: `80px 60px 1fr 90px`.

- `month-label` Playfair 22px ivory.
- `month-year` mono 10.5px ivory-mute letter-spacing 0.16em.
- `titles` Source Serif 4 13.5px ivory-soft, single-line truncated with `...`.
- `count` mono 13px right-aligned + small "artifacts" caption beneath.

Whole row clickable `<a href="/reports?month={YYYY-MM}">`. Hover bg `rgba(184,149,106,0.025)`.

Source: `useArtifactArchive(month)` — see §6 GAP. The unfiltered query
`useArtifacts({ limit: 9999 })` already gives all rows; client-side group-by-month
is acceptable until the backend ships per-month aggregates.

---

## 6. Hooks — verified against `lib/hooks.ts` (2026-04-27 grep)

### Existing hooks reused (verified by grep)

- `useArtifacts(options: UseArtifactsOptions)` — at line 128 of `hooks.ts`. Returns
  `{ artifacts, total, unreadCount, isLoading, error, mutate }`. Supports `type`,
  `since`, `limit` filters. Backed by `API.artifacts.list = "/api/artifacts/list"`.
- `useMorningBrief()` — at line 72. Backed by `API.market.morningBriefToday = "/api/brief/today"`.
- `useMorningBriefArchive()` — at line 80. Backed by `API.market.morningBriefArchive = "/api/brief/archive"`.

### NEW hooks required (GAP)

```ts
// frontend/src/lib/hooks.ts — append

export interface ArtifactStats {
  total: number;            // lifetime
  countYtd: number;
  countMemos: number;       // morning_brief
  countBriefs: number;      // earnings_prebrief
  countBragCards: number;   // monthly_brag
  decisionMoving: number;   // count flagged moved_a_decision = true
  byType: Record<ArtifactType, number>;
  nextScheduled: { type: ArtifactType; at: string } | null;
  latestIndexedAt: string;
}

export function useArtifactStats() {
  return useSWR<ArtifactStats>(
    API.artifacts.stats,            // NEW endpoint — see §7
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 60_000 },
  );
}

export interface ArtifactArchiveMonth {
  month: string;            // "2026-04"
  artifacts: Artifact[];
  count: number;
}

export function useArtifactArchive(month: string | null) {
  const key = month ? `${API.artifacts.byMonth}?month=${month}` : null;
  return useSWR<ArtifactArchiveMonth>(key, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 120_000,
  });
}

export interface GenerateArtifactBody {
  type: ArtifactType;
  ticker?: string;          // for earnings_prebrief
  topic?: string;           // for risk_report / custom
}

export async function generateArtifact(body: GenerateArtifactBody) {
  const r = await fetch(API.artifacts.generate, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.statusText);
  return r.json() as Promise<{ job_id: string; eta_seconds: number }>;
}
```

### Mistakes to avoid (home-v2 SPEC errata, repeated for visibility)

The home-v2 SPEC referenced these hooks that do **not** exist:
- ❌ `useArtifactQueue()` → real name: `useArtifacts({ limit: N })`.
- ❌ `useArtifactStats()` → does **not** exist; this page proposes it as GAP.
- ❌ `useTodayMemo()` → real name: `useMorningBrief()`.

Verify by grep before writing implementation:
```bash
grep -n "^export function use" frontend/src/lib/hooks.ts
```

---

## 7. Endpoints — verified against `lib/endpoints.ts` (2026-04-27 read)

| Use | Constant | Resolved URL |
|---|---|---|
| List all artifacts | `API.artifacts.list` | `/api/artifacts/list` |
| Download | `API.artifacts.download(id)` | `/api/artifacts/${id}/download` |
| HTML preview | `API.artifacts.preview(id)` | `/api/artifacts/${id}/preview` |
| Mark read | `API.artifacts.markRead(id)` | `/api/artifacts/${id}/read` |
| Today's morning brief | `API.market.morningBriefToday` | `/api/brief/today` |
| Brief archive | `API.market.morningBriefArchive` | `/api/brief/archive` |
| Generate brief now (existing) | `API.market.morningBriefGenerate` | `/api/brief/generate-now` |
| Watchlist (for ticker autocomplete in request box) | `API.watchlist.list` | `/api/watchlist` |

Verified at `endpoints.ts` lines 47–50 (`market` brief group), 213–217 (`artifacts` group), 98–103 (`watchlist`).

### NEW endpoints required (GAP)

| Constant (proposed) | URL | Method | Body | Returns |
|---|---|---|---|---|
| `API.artifacts.stats` | `/api/artifacts/stats` | GET | — | `ArtifactStats` (see §6) |
| `API.artifacts.byMonth` | `/api/artifacts/by-month` | GET | `?month=YYYY-MM` | `ArtifactArchiveMonth` |
| `API.artifacts.generate` | `/api/artifacts/generate` | POST | `GenerateArtifactBody` | `{ job_id, eta_seconds }` |
| `API.artifacts.jobStatus` | `/api/artifacts/job/${jobId}` | GET | — | `{ status: "queued"\|"running"\|"done"\|"error", artifact_id?: number }` |

Backend file targets:
- `routes/artifacts.py` — add `stats()`, `by_month()`, `generate()`, `job_status()`.
- `services/artifact_generator.py` — composes existing `services/morning_brief_generator.py` patterns. Most of the work is wiring; the generators themselves already exist for morning_brief and weekly memo.

---

## 8. Tokens used (NO new tokens)

| Token | Used by |
|---|---|
| `--pq-ink` | body |
| `--pq-ivory` | name-main, pull quote, kicker, month-label |
| `--pq-ivory-soft` | description, body-text, titles preview, ticker rows mid-line |
| `--pq-ivory-quiet` | inline counts secondary, status seg base |
| `--pq-ivory-mute` | ticker-sub price, meta lbl, month-year, lifetime caption, timestamp |
| `--pq-bronze` | eyebrow, "br" italic, hover border, type-pill text, CTA bronze, month-year accent |
| `--pq-bronze-light` | CTA hover |
| `--pq-bronze-deep` | strength-bar gradient (signals overlap), CTA gradient stop |
| `--pq-bronze-08` | hover bg, ghost CTA hover |
| `--pq-bronze-15` | pq-link border-bottom |
| `--pq-hairline` | card border, meta-row top border, month-row bottom border |
| `--pq-hairline-2` | type-pill border, disclaimer dashed border |
| `--pq-positive` (#dc2626) | mention row +N% (KR up = red) |
| `--pq-negative` (#2563eb) | mention row -N% (KR down = blue) |
| `--pq-text-h1` (48px) | hero |
| `--pq-text-h2` (40px → 30px clamp) | block headers |
| `--pq-text-eyebrow` + `--pq-track-eyebrow` | every kicker |
| `--pq-radius-card` (4px) | every card / row |
| `--pq-radius-cta` (2px) | CTA, type-pill |

Banned: any new hex, any radius >4px, any non-Playfair/Source Serif/JetBrains Mono/Pretendard font.

---

## 9. Banned UI strings (legal — same as home-v2 / signals-v2)

The following must NEVER appear in any v2 component or in API response bodies:

- `BUY`, `SELL`, `HOLD`
- `recommend`, `recommendation`, `advice`, `advise`, `advisory`
- `추천`, `조언`
- `AI Coach`, `투자 코치`

Allowed signal vocabulary: **`POSITIVE`, `NEGATIVE`, `NEUTRAL` only.**

Critically: **artifact bodies (memo content, brief text) must also be scanned.**
The morning-brief generator and the new artifact-generator endpoints in `services/`
need a banned-vocab linter on their output. Recommended: extend
`tests/test_no_hardcoded_samples.py` to crawl `services/morning_brief_generator.py`
and any new generator. CI legal-guard (`.github/workflows/legal-guard.yml`) already
covers source code; runtime-generated text needs an additional check inside the
generator before persisting.

`DisclaimerBanner` is mounted once by `(dashboard)/layout.tsx`. The page-level
disclaimer block in the mockup is illustrative for review; production wiring uses
the layout banner with `variant="reports"` copy.

---

## 10. 종목명 main pattern (CEO directive 2026-04-26)

Verified applied at every name surface in this page:

| Surface | Display | Source |
|---|---|---|
| Latest artifact "Mentioned" rows | `Apple Inc.` (Playfair 18 ivory) + `AAPL · NASDAQ` (mono 10 dim) | `Artifact.data_preview.mentioned_tickers[].{name, ticker, exchange}` — backend must return both name and code |
| Gallery cards | `Today's Memo` (Playfair 22 ivory) + `Auto · 06:00 KST · Mon–Fri` (mono 10 dim) | static display map (§3) |
| Request tiles | `Earnings Pre-Brief` (Playfair 20 ivory) + `Apple Inc. · AAPL · 30 Apr` (mono 10 dim) | static + ticker autocomplete |
| Year timeline rows | `Apr` (Playfair 22 ivory) + `2026` (mono 10.5 dim) — month/year as the editorial pair | `month` + `year` from query |

**Backend touchpoint:** `Artifact.data_preview.mentioned_tickers` must contain
`{ticker, name}` pairs. Today's `Artifact` type only declares `data_preview` as
`Record<string, unknown>` — the schema needs documentation. **GAP**: tighten the
`MentionedTicker` interface in `lib/types.ts` and ensure
`services/morning_brief_generator.py` emits both fields.

---

## 11. Responsive breakpoints

| Breakpoint | Layout |
|---|---|
| `≥1280px` (`xl`) | Latest 2-col 56px gap; gallery 3×2; year row 80/60/1fr/90 |
| `1024–1279px` (`lg`) | Latest unchanged; gallery 3×2 with reduced 24px padding; year row unchanged |
| `768–1023px` (`md`) | Latest stacks (left then right); gallery 2-col × 3-row; year row 70/50/1fr/80 |
| `<768px` (mobile) | Latest stacks, padding 32/24; gallery 1-col × 6-row; request box 1-col × 3-row; year row 60/auto/1fr/72 |

Mobile concrete numbers:
- Pull-quote 22px (was 30).
- Gallery card name 18px (was 22), padding 20.
- Year-row month-label 18px (was 22).

---

## 12. A11y checklist

- [ ] Heading order: H1 (hero) → H2 ("Just out.") → H2 ("Kinds.") → H2 ("Ask the desk.") → H2 ("The year, briefly.").
- [ ] All cards / rows are real `<a>` with `aria-label="${displayName} — open archive"` or `${month} ${year} — ${count} artifacts`.
- [ ] Type-pill text carries the cadence semantically; color is decorative only.
- [ ] Bronze on Vantablack confirmed 6.94:1 (AA normal / AAA large).
- [ ] Color is never the only signal in mention rows: `+`/`-` glyph paired with the red/blue color.
- [ ] Focus rings: existing `:focus-visible { outline: 1px solid var(--pq-bronze); outline-offset: 3px; }`.
- [ ] Reduced-motion: card hover transitions wrapped in `@media (prefers-reduced-motion: no-preference)`.
- [ ] Request tile activation: keyboard `Enter` opens the same modal as click.
- [ ] Live region for "generating" status when a request returns a job id: `aria-live="polite"` toast.
- [ ] PDF download links use `<a download>` plus `aria-describedby` for screen readers.

---

## 13. GAP summary (action items for engineering)

Order: **bigger** than signals-v2 — there are real backend additions here, not
just a label-mapper. None block visual sign-off; gallery and timeline render
fine with the existing `useArtifacts` until the new endpoints land.

1. **`useArtifactStats()` hook + `/api/artifacts/stats` endpoint** — aggregates lifetime, YTD, by-type, by-decision-moved, next-scheduled. Read-only join.
2. **`useArtifactArchive(month)` hook + `/api/artifacts/by-month` endpoint** — server-side groupby for the year timeline. (Optional — client-side group from `useArtifacts({ limit: 9999 })` works as a stopgap.)
3. **`generateArtifact(body)` action + `/api/artifacts/generate` endpoint + job-status poll** — the request-box. New `services/artifact_generator.py` composes existing morning-brief / weekly-memo generators.
4. **`<LivingCFOStatusBar variant="reports">`** — copy variant. Trivial.
5. **`<ArchiveHeroV2/>`, `<LatestArtifactCard/>`, `<ArtifactKindsGrid/>`, `<ArtifactKindCard/>`, `<ArtifactRequestBox/>`, `<ArtifactYearTimeline/>`** — all net-new components, CSS-only, no chart lib.
6. **Tighter `MentionedTicker` type + backend emission** — ensure `Artifact.data_preview.mentioned_tickers[].{ticker, name, exchange?}` is the contract.
7. **Banned-vocab linter on artifact generator output** — extend the legal-guard CI to scan generator outputs in tests.
8. **Search Archive (⌘K)** — out of scope for this v2; ships behind its own feature flag in a later wave.
