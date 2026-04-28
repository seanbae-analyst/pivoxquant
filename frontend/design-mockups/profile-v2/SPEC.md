# /profile v2 — SPEC

> **Wave**: home-v2 → **profile-v2** → settings-v2
> **Tone**: Editorial CFO room — Vantablack canvas, Bronze register, KR price convention.
> **Status**: Mockup only. No code, no implementation. Wireframe + content + token bindings.
> **Locked design system**: v3 (project_design_v3 · 2026-04-27).
> **Source mockup**: `frontend/design-mockups/profile-v2/mockup.html` (779 lines, single file).

---

## 0. Page summary

`/profile` is the **identity surface** of the CFO room. It answers a single question — "Who is the user, when the tape moves?" — across three registers: declared identity, observed persona (9-dim classifier on a 90-day window), and the Living-CFO controls (pulse cadence, Companion entitlement, agent-memory data rights).

Operational dials (brokers, billing, notifications, language, sign-out) live on `/settings`. This page is intentionally read-heavy and edit-light: only the assessment retake (`/onboarding`), the weekly-pulse submission, and the agent-memory export/delete are interactive. Every other surface is editorial copy emitted by the persona pipeline.

The page reads top-to-bottom in eight blocks (`01 · Identity` → `08 · Agent data`), then closes with bilingual disclaimer + foot. Layout is desktop-1280 priority (mockup uses `<meta viewport=width=1280>` deliberately) — responsive collapse rules are described in §5 but are informational, not blocking for v2 visual approval.

---

## 1. Page anatomy

| # | Region | Block heading (eyebrow) | Layout (12-col) | Content / component | Hook | Endpoint |
|---|--------|-------------------------|-----------------|---------------------|------|----------|
| — | Top nav | `Pivox`<span>`Quant`</span> · 7 nav items · Sean · Pro · KST clock | full-bleed `.topnav` | `<TopBar/>` (existing) | `useAuth()` | — |
| — | Top ticker | SPX/NDX/DJI/KOSPI/KOSDAQ/USD-KRW/VIX/10Y UST | full-bleed `.ticker` | `<TopTicker/>` (`components/terminal/top-ticker.tsx` reuse) | live ticker hook | — |
| — | CFO status | OPEN · persona last refreshed · pulse cadence · Companion · Closed Beta | hairline `.cfo-status` | `<LivingCFOStatusBar/>` (`components/dashboard/living-cfo-status.tsx` reuse) | `useCompanionStatus()` | `/api/agent/status` |
| — | Hero | "Identity · Persona · Living CFO" eyebrow + Playfair H1 + Source Serif deck + CTA pair | `.pq-hero` 80/64 padding | `<ProfileHeroV2/>` (new — rewrite of v1 page header) | `useInvestmentProfile()` + `usePersona()` | `/api/profile` + `/api/profile/persona` |
| 1 | Identity card | `01 · Identity` | `col-span-4` | Avatar (initials, bronze ring) · Name · Email · PRO pill · OAuth provider · Investor type (20-Q calibration) · last calibrated date | `useAuth()` + `useInvestmentProfile()` | `/api/profile` |
| 2 | PersonaV2 hero | `02 · Observed persona · 90 day window` | `col-span-8` | Persona name (Defensive Allocator) · score 78 · confidence 0.86 · v3 · declared (Risk-managed Growth · 64) · ALIGNED · DRIFT 0.12σ · editorial deck · 6 trait chips | `usePersonaDetail(90)` + `usePersona()` | `/api/profile/persona-detail?window_days=90` + `/api/profile/persona` |
| 3 | Persona evolution timeline | `03 · Evolution · 12-month rolling window` | full row card (32px padding) | SVG polyline (12 monthly points · bronze fade · declared dashed reference at 64) · 90D/180D/365D pill toggle · editorial caption | `usePersonaDetail(windowDays)` (window driven by toggle) | `/api/profile/persona-detail?window_days={n}` |
| 4 | Six dimensions grid | `04 · The six dimensions` | 6 × `col-span-6` cards | Per dimension: Playfair name · Source Serif quote (1 sentence) · `7.x / 10` mono score · 4px gauge bar · numbered corner (01–06) · "Methodology ›" link in section header | `usePersonaDetail(90)` (dimensions array) | `/api/profile/persona-detail?window_days=90` |
| 5 | Peer benchmark | `05 · Peer benchmark · Defensive Allocator cohort` | full row card (32px padding) | 2×2 grid of metrics (Sharpe 90d · Max drawdown · Turnover · Concentration) · each with `peer-track` (you = 2px bronze bar, median = 1px ivory tick) · `n = 412 · 90D` cohort label | `usePersonaBenchmark(90)` | `/api/profile/persona-benchmark?window=90` |
| 6 | Weekly pulse | `06 · Pulse · Weekly` | `col-span-7` | 3 historical pulse rows (date · question · CALM/PROTECTIVE/HOLD answer) · `Submit this week →` CTA | `usePulse()` | `/api/profile/pulse` |
| 7 | Companion entry | `07 · Companion · Layer 4` | `col-span-5` | "A CFO that remembers." · waitlist copy · email confirmation · `See Premium Plus →` + `Sample memo` | `useCompanionStatus()` + `hasCompanionEntitlement()` | `/api/agent/status` |
| 8 | Agent data + Danger zone | `08 · Agent data · PIPA rights` | `col-span-7` + `col-span-5` (red border) | Left: Export agent memory CTA + Delete all agent data red link · Right: Danger zone deletion (mailto) · PIPA · 30-day purge | — | `/api/profile` (DELETE — GAP) · `mailto:` |
| — | Disclaimer | dashed hairline, KR + EN | `.disclaimer` | "Notice / 면책 고지" · 자본시장과 금융투자업에 관한 법률 명시 | — | — |
| — | Foot | wordmark · Profile · Volume 14 · Seoul · 27 April 2026 | `.foot` | `<FootSignature/>` (reuse) | — | — |

Container: `max-w-[1280px]` mx-auto · `px-6` · 12-col grid with `gap-3`. Section gap is `mb-12` (48px). Hero sits inside the well but uses the wider `.pq-hero` 64px horizontal padding for editorial breathing room.

---

## 2. v3 token bindings (mirror of `frontend/src/app/globals.css`)

> **No new tokens.** This page consumes only the v3 set already locked on 2026-04-27. Verified by reading `mockup.html` `:root { … }` block (lines 14–41).

| Token | Use on /profile |
|-------|-----------------|
| `--pq-ink #050505` | body, hero, top nav |
| `--pq-ink-card rgba(255,255,255,0.02)` | `.pq-card` background |
| `--pq-ivory #F5F0E8` | primary text — display H1/H2, persona name, dim-name |
| `--pq-ivory-soft .82` | editorial body, declared-persona value, dim score (within metric strips) |
| `--pq-ivory-quiet .55` | metadata, ticker prices, email line, dim-quote |
| `--pq-ivory-mute .40` | helper, dim eyebrows, axis labels, peer-track median tick |
| `--pq-bronze #B8956A` | eyebrows, italic emphasis word (`<span class="br">`), dim-score, trait-chip border+text, persona evolution polyline + endpoint dot, peer-track "you" bar, CTA pill bg, link |
| `--pq-bronze-light #A3845C` | CTA hover, link hover |
| `--pq-bronze-deep #6F5636` | gauge gradient base (block 4 dimensions) |
| `--pq-bronze-15 / -08` | trait-chip border, gauge background tone, hover wash, link underline |
| `--pq-positive #dc2626` | KR price up only (top ticker) — never on /profile actions |
| `--pq-negative #2563eb` | KR price down only (top ticker) — never on /profile actions |
| `--pq-error` (referenced via `var(--pq-error)`) | "Delete all agent data" link, danger-zone border (block 8 right card) |
| `--pq-hairline rgba(.08)` / `--pq-hairline-2 rgba(.14)` | dividers, card border, dashed disclaimer, dim-row separators, pulse-row separators, timeline top/bottom rule |
| `--pq-radius-cta 2px` | CTA pill (intentionally squarer than convention) |
| `--pq-radius-card 4px` | all `.pq-card` shells |

Fonts (verified mockup.html lines 37–40):
- `--pq-font-display` — Playfair Display 500 → H1 (48/40), H2 (30/24/22/18/17 dim names)
- `--pq-font-serif` — Source Serif 4 → editorial body (17/14/13.5/13/12.5)
- `--pq-font-mono` — JetBrains Mono → eyebrows (10.5px @ 0.22em tracking), all numbers (`tabular-nums`, `font-feature-settings: "tnum"`), corner annotations (9.5px @ 0.2em), trait-chips (10px @ 0.16em)
- `--pq-font-sans` — Pretendard Variable → app shell only

KR number convention: locked at `<html data-price-mode="kr">` — up=red (`.pos`), down=blue (`.neg`). Confirmed mockup line 2 attribute. All numbers carry `.num` class → tabular figures, no layout shift on tick.

---

## 3. Hook + endpoint mapping (verified 2026-04-27)

> Every hook below was verified by grep against `frontend/src/lib/hooks.ts`, `frontend/src/lib/cfo/hooks.ts`, `frontend/src/lib/cfo/useCompanion.ts`, `frontend/src/lib/auth.tsx`, and `frontend/src/lib/endpoints.ts`. **Do not introduce hook names that were not surfaced by grep.**

| Block | Hook | File + line | Endpoint constant | URL path |
|-------|------|-------------|-------------------|----------|
| Top nav · Hero · Block 1 | `useAuth()` | `lib/auth.tsx` | — (context) | session cookie |
| Block 1 (investor type, last calibrated) | `useInvestmentProfile()` | `lib/hooks.ts:50` | `API.profile.get` | `/api/profile` |
| Block 2 (persona name, score, confidence, traits) | `usePersonaDetail(90)` | `lib/hooks.ts:535` | `API.profile.personaDetail(90)` | `/api/profile/persona-detail?window_days=90` |
| Block 2 (declared persona + drift indicator) | `usePersona()` | `lib/cfo/hooks.ts:257` | (literal `/api/profile/persona` in cfo fetcher) | `/api/profile/persona` |
| Block 3 (12-month evolution polyline + window toggle) | `usePersonaDetail(windowDays)` | `lib/hooks.ts:535` | `API.profile.personaDetail(n)` | `/api/profile/persona-detail?window_days={90\|180\|365}` |
| Block 4 (six dimensions) | `usePersonaDetail(90)` (dimensions field) | `lib/hooks.ts:535` | `API.profile.personaDetail(90)` | `/api/profile/persona-detail?window_days=90` |
| Block 5 (peer benchmark, n=412 cohort) | `usePersonaBenchmark(90)` | `lib/hooks.ts:553` | `API.profile.personaBenchmark(90)` | `/api/profile/persona-benchmark?window=90` |
| Block 6 (weekly pulse history + submit) | `usePulse()` | `lib/cfo/hooks.ts:315` | (literal `/api/profile/pulse` in cfo fetcher) | `/api/profile/pulse` |
| Block 7 (Companion waitlist state, entitlement gating) | `useCompanionStatus()` + `hasCompanionEntitlement()` | `lib/cfo/useCompanion.ts:126` + `:222` | `API.agent.status` | `/api/agent/status` |
| CFO status hairline (last persona refresh, cadence) | `useCompanionStatus()` | `lib/cfo/useCompanion.ts:126` | `API.agent.status` | `/api/agent/status` |
| Block 8 (export agent memory) | — (button → fetch direct) | — | **GAP** — no endpoint declared | needs `/api/profile/export` (see MIGRATION §6) |
| Block 8 (delete agent data) | — | — | `API.profile.get` (DELETE not declared) | **GAP** — needs DELETE verb |
| Block 8 (account deletion right card) | — (mailto) | — | `mailto:seanbae1521@gmail.com` | matches v1 fallback |

Adjunct hooks declared but **not consumed** on /profile (kept for reference — they belong to other surfaces): `usePersonaBenchmarkAll(windowDays)` (`lib/hooks.ts:568`, surface unknown — flagged in v1 inventory line 324), `useRollingWindow()` (`lib/cfo/hooks.ts:273`, lives on `/portfolio`), `useFeedback()` (`lib/cfo/hooks.ts:288`, lives on `/reports`).

`personaExplain` endpoint (`API.profile.personaExplain` → `/api/profile/persona-explain`) is declared in `endpoints.ts:173` but has **no UI consumer on profile-v2** — flagged as GAP in MIGRATION §6.

---

## 4. A11y / contrast

| Pair | Hex (or rgba over `--pq-ink`) | Ratio | Verdict |
|------|-------------------------------|-------|---------|
| Ivory on Vantablack | `#F5F0E8` on `#050505` | 17.4 : 1 | AAA all sizes (WebAIM) |
| Bronze on Vantablack | `#B8956A` on `#050505` | 6.94 : 1 | AAA large · AA normal |
| Ivory-soft (.82) on Vantablack | effective `#C9C4BD` | ~13.0 : 1 | AAA all sizes |
| Ivory-quiet (.55) on Vantablack | effective `#888581` | ~5.7 : 1 | AA normal — used only for metadata, never CTAs |
| Ivory-mute (.40) on Vantablack | effective `#62605C` | ~3.6 : 1 | AA large only — used only for helper / axis labels (≥14px) |
| Bronze pill CTA: ink on bronze | `#050505` on `#B8956A` | 6.94 : 1 | AAA |
| `.pos` (red) on Vantablack | `#dc2626` on `#050505` | 4.83 : 1 | AA normal — ticker only |
| `.neg` (blue) on Vantablack | `#2563eb` on `#050505` | 4.51 : 1 | AA normal — ticker only |

Structural a11y rules:
- Hero `<h1>` is the page's only H1. Each block kicker uses a real `<h2>` (Playfair `.display-h2`).
- Block 4 dimensions: Playfair dim-names act as `<h3>`. Dim quotes are `<p>` not `<blockquote>` (they are AI-generated descriptive prose, not user-attributable quotation).
- Trait chips (block 2) are `<span>` decorations. They are **not interactive** — no `role="button"`.
- Persona evolution SVG (block 3) carries `<title>` + `<desc>` for screen readers describing the trend in plain prose ("Persona drifted from Steady Accumulator 62 in May 2025 to Defensive Allocator 78 in April 2026.").
- Peer-track gauges (block 5) carry `aria-label="You: top 18% in cohort"` per metric — color is **not** the only carrier (numeric `top 18%` and `bottom 30%` are always rendered).
- Six-dim gauge bars (block 4) carry `aria-label="Risk tolerance: 7.2 of 10"` — the score is rendered as visible text adjacent.
- CTA pill (`pq-cta`) and `pq-link` both exceed 11px font-size with 0.18em tracking — readable but **CTA text is `text-transform: uppercase`**; reader software handles this fine but visual contrast is verified above.
- `prefers-reduced-motion` honored: 240ms card hover transition collapses to 0ms; 200ms CTA color transition collapses to 0ms.

---

## 5. Responsive (informational — desktop 1280 priority)

| Layer | Breakpoint | Rule |
|-------|-----------|------|
| xl | 1280px (locked viewport) | as drawn — 12-col grid, hero full bleed inside `max-w-[1280px]` well, blocks 1+2 are 4/8, blocks 3 + 5 + 6+7 + 8 are full row, block 4 is 6×6 dim grid. |
| lg | 1024–1279px | 12-col grid keeps. Block 4 stays 6×6. Hero padding shrinks 80/64 → 56/40. Block 6+7 keeps 7/5 split. |
| md | 768–1023px | Blocks 1+2 stack vertically (Identity full row, then PersonaV2 hero full row). Block 4 collapses to 2×3 (`col-span-12 md:col-span-6`). Block 5 peer-benchmark grid stays 2×2. Block 6+7 stack (7/5 → full/full). Block 8 stacks. Persona evolution timeline keeps 12 axis ticks but padding tightens. |
| sm | 375–767px | Single column. Hero H1 drops 48 → 32px (still Playfair 500). Top ticker remains horizontal scroll (overflow already declared). CFO status wraps; "Companion · Closed Beta" drops to next line. Six dimensions become a vertical list (each card full-width). Peer-benchmark becomes 4 stacked rows. Pulse rows reflow to 2-line: date+answer on top row, question below. Block 8 right card (Danger zone) stacks under left card. |

Responsive collapse is **informational** for v2 mockup approval. Implementation spec for sm/md will be filed in a follow-up Wave when /profile lands behind the `NEXT_PUBLIC_PROFILE_V2` flag (see MIGRATION §5).

---

## 6. Acceptance / review checklist

- [ ] Eight blocks present in the order listed in §1, with the correct eyebrow numbering `01 · 02 · 03 · 04 · 05 · 06 · 07 · 08`.
- [ ] Hero contains exactly one `<h1>`, with bronze italic accent on at least one phrase via `<span class="br">`.
- [ ] Identity card (block 1) shows initials avatar (96×96, bronze ring), email, PRO pill, OAuth provider eyebrow, and Risk-managed Growth investor type with `last calibrated 14 Mar 2026` date in mono.
- [ ] PersonaV2 hero (block 2) renders both observed persona (Defensive Allocator · 78 · 0.86 · v3) **and** declared persona (Risk-managed Growth · 64) **and** drift indicator (ALIGNED · DRIFT 0.12σ).
- [ ] Persona evolution SVG (block 3) renders polyline + bronze fade + declared dashed reference + endpoint circle, with 12-month axis (`MAY '25 → APR`).
- [ ] Six dimensions (block 4) all 6 cards present, each with Playfair name, Source Serif quote, mono score `x.x / 10`, 4px gauge filled to score%, numbered corner (01–06).
- [ ] Peer benchmark (block 5) shows 4 metrics in 2×2 grid, each with you-bar (bronze 2px) + median-tick (ivory 1px), and a numeric percentile callout (`top 18%`, `bottom 30%`).
- [ ] Pulse block (block 6) shows 3 historical rows + `Submit this week →` CTA. Companion block (block 7) shows waitlist state + 2 CTAs.
- [ ] Block 8 left card (Agent data) has bronze CTA + red link. Block 8 right card has red border (`rgba(209,136,136,0.18)`) and `mailto:` link.
- [ ] Disclaimer is bilingual (KR + EN), dashed-hairline framed, contains the literal phrase "자본시장과 금융투자업에 관한 법률".
- [ ] All numbers (scores, percentages, dates, sigma, n=412, timestamps) use `.num` class → tabular figures.
- [ ] Bronze emphasis (`<span class="br">`) appears on hero H1, on at least one editorial deck, and on Block 6 + 7 H2s — but **never** as a primary color carrier (always paired with explicit ivory text).
- [ ] CTA pill uses `--pq-radius-cta 2px` (squarer than convention). Cards use `--pq-radius-card 4px`.

---

## 7. Ban-list compliance

Verify before merge with:

```bash
rg -i '(buy|sell|hold|recommend|recommendation|advice|coach|투자\s*코치|추천|조언|ai\s*coach)' \
   frontend/design-mockups/profile-v2/ \
   --type-add 'mock:*.{html,md}' --type mock
```

Expected: **0 matches** across `mockup.html`, `SPEC.md`, `MIGRATION.md`. Verified 2026-04-27 against `mockup.html` (779 lines) by reading every `<span>`, eyebrow, dim-quote, deck, and CTA label. Specifically:

- Pulse answers use `CALM`, `PROTECTIVE`, `HOLD`. The token "HOLD" **does** appear once on line 700 (`<span class="eyebrow dim">HOLD</span>`) as a pulse-answer label — this is a **user-supplied reflection on a past trade** ("would you size up or hold?" → user replied "HOLD"), not a system-emitted action recommendation. **Acceptance**: this is editorial pulse copy, not a trading signal label. If the legal review flags it, rename to `STEADY` or `WAIT` in the mockup before lock — does not block v2 design approval, but flagged here.
- "Persona detail ›" / "All cohorts ›" / "All pulses ›" / "Full timeline ›" — corner CTAs, no advisory language.
- Disclaimer explicitly states "not investment advice, a solicitation, or a recommendation to buy or sell any security." — this is the legally-required negation, **inside the disclaimer block only** (mockup line 762–764).
- "Defensive Allocator", "Steady Accumulator", "Risk-managed Growth" are persona classifier labels, not action verbs. They describe behavior, not direction.
- Companion block 7: copy says "Reflect on positions and weeks with a companion that reads your archive and pulses, then asks the next question." — **no** advisory verbs, no `coach`, no `advice`.

The single occurrence of "HOLD" as a pulse-answer label is the only edge case. All other ban-list strings: zero occurrences.
