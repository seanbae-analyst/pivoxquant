# /risk v2 — "Risk Board" · Component Spec

> Single source of truth for implementation. Tokens reference
> `frontend/src/app/globals.css` (design system v3, locked 2026-04-27).
>
> **Hook accuracy note**: every hook-name in this document was checked
> against `grep -n "^export function use" frontend/src/lib/hooks.ts` on
> 2026-04-27. Risk hooks do **NOT** exist yet in `hooks.ts` — they are
> all GAP. Backend endpoints, however, mostly exist (verified in
> `endpoints.ts` lines 124–131 and 252–255).

---

## 0. Page-level shell

| Region | Element | Source / Notes |
|---|---|---|
| Top nav | `<TopBar/>` | reuse |
| Top ticker | `<TopTicker/>` | reuse |
| CFO status | `<LivingCFOStatusBar/>` | reuse |
| Hero | `<RiskHeroV2/>` (NEW) | editorial hero, mirrors home-v2 + portfolio-v2 hero rhythm |
| Block 1 — 4 KPI gauges | `<BigGaugeCard/>` × 4 in 2×2 grid (NEW) | each ~240px tall |
| Block 2 — 7-Layer Defense | `<DefenseLayerList/>` (NEW), 7 stacked rows | derived from `risk_defense.py` (already complete on backend) |
| Block 3 — Concentration table | `<ConcentrationTable/>` (NEW) | top-5 positions with weight bars |
| Block 4 — Sector exposure | `<SectorDonutLg/>` + `<SectorLeaderTable/>` (NEW), 2-col | mirrors portfolio-v2 sector card but at 220px donut + leader names |
| Block 5 — Risk timeline | `<RiskTimelineChart/>` (NEW) | 30-day composite line chart |
| Disclaimer | `<DisclaimerBanner/>` | reuse — but on this page extend the copy with the "VaR is probabilistic, not a guarantee" line |
| Foot | `<FootSignature/>` | reuse |

Container: `max-w-[1280px]` mx-auto, `px-6`. Outer body is `--pq-ink`.

---

## 1. Hero — `RiskHeroV2`

| Prop | Type | Source |
|---|---|---|
| `eyebrow` | `string` | derived: `"Risk · 7-Layer Defense · ${weekday}"` |
| `headline` | `string` | static: `"Risk <br>board.</br>"` |
| `body` | `string` | composed from `useRiskSummary()` (GAP — see §6) |
| `posture` | `'composed'\|'strained'\|'breached'` | derived from layer states |
| `breachedCount` | `number` | count of layers with `status === 'NEGATIVE'` (the loudest signal call-out) |
| `lastObservedAt` | `string` (ISO) | from summary endpoint |

**Visual rules**:
- Same hero scaffolding as portfolio-v2 / home-v2 (80px / 64px padding, hairline-bottom seal, no border).
- H1 Playfair 500 / 48px. Bronze italic accent on `board.` and on the words `observed`, `composed`, `posture` inside the deck.
- Two CTAs:
  - Primary `pq-cta` "Open layers ↓" — anchor-link to Block 2.
  - Secondary `pq-cta.outline` "Stress test" — opens stress-test panel (post-MVP, can ghost-link for now).

**Posture vocabulary** (legal-safe):
- `composed` ↔ POSITIVE-leaning
- `attentive` ↔ mixed (1–2 NEGATIVE)
- `strained` ↔ NEGATIVE-leaning
- `breached` ↔ a hard threshold crossed

Never use: "buy", "sell", "exit", "reduce", "dump", "cut" — all are action language.

---

## 2. Block 1 — `BigGaugeCard` × 4

A reusable card. Four instances laid out in a 2×2 grid with 12px gutter.

| Prop | Type | Source |
|---|---|---|
| `eyebrow` | `string` | static label (e.g. "VaR · 95% / 1-day") |
| `value` | `number \| string` | from `useRiskSummary()` (GAP) |
| `unit` | `'%' \| 'idx' \| 'ratio' \| undefined` | static per gauge |
| `range` | `string` | static label (e.g. "Normal range −2.0 ↔ −3.5%") |
| `gaugePct` | `number` | 0–100, position along the gradient bar |
| `marks` | `[string, string, string]` | left/mid/right anchor labels |
| `posture` | `'POSITIVE'\|'NEGATIVE'\|'NEUTRAL'` | from layer status |

**Four instances**:

| # | eyebrow | value (mock) | range copy | marks | posture |
|---|---|---|---|---|---|
| 1 | VaR · 95% / 1-day | −2.34% | Normal range −2.0 ↔ −3.5% | Calm / Strained / Breach | NEUTRAL |
| 2 | Concentration · HHI | 0.184 | Threshold < 0.25 · Tech 41.0% | Diffuse / Tilted / Breach | NEGATIVE |
| 3 | Correlation · 90-day avg | 0.42 | Cluster max 0.71 · NVDA ↔ AMD | Independent / Clustered / Synced | NEGATIVE |
| 4 | Tail · Component ES | −4.12% | 99th percentile · 1-day | Thin / Heavy / Fat | POSITIVE |

**Visual rules**:
- 240px min-height. Padding 28px.
- Eyebrow at top.
- Big value: mono 44px tabular-nums, with `%` rendered at 26px ivory-mute alongside.
- Range copy: mono 11px tracked, ivory-quiet.
- Linear gauge bar (NOT a circular arc — keep CSS-only and consistent with home-v2 `.gauge`):
  - Track: `rgba(245,240,232,0.06)` 6px tall.
  - Fill: linear gradient `var(--pq-bronze-deep)` → `var(--pq-bronze)`, width = `gaugePct`%.
- 3 anchor marks below the bar (mono 9.5px ivory-mute).
- Posture line at bottom: mono uppercase 10.5px, color = positive/negative/neutral token.

**Why linear, not circular**: the home-v2 mockup uses linear `.gauge` for the same metric class. Keeping the same primitive avoids a new chart shape and stays editorial.

---

## 3. Block 2 — `DefenseLayerList`

7 rows inside a single `pq-card`. The visual primitive is identical for each layer; only the data differs.

| Prop | Type | Source |
|---|---|---|
| `layers` | `DefenseLayer[]` | `useRiskLayers()` (GAP — see §6); endpoint exists at `RISK_LAYERS = "/api/risk/layers"` (line 253 of `endpoints.ts`) |

```ts
interface DefenseLayer {
  num: 1|2|3|4|5|6|7;
  name: string;
  description: string;       // one-line serif body
  status: 'POSITIVE'|'NEGATIVE'|'NEUTRAL';
  value: string;             // pre-formatted (mono)
  threshold: string;         // pre-formatted comparison
  observedAtKst: string;     // "21:30 KST"
}
```

**Row layout** (`grid-template-columns: 56px 1fr 110px 130px 110px 140px`):
1. **Layer number**: Playfair 22px bronze (e.g. "01" .. "07")
2. **Name + description**: Playfair 18px ivory + Source Serif 4 12.5px ivory-quiet
3. **Status**: mono uppercase eyebrow, color by token
4. **Value**: mono 16px ivory
5. **Threshold**: mono 11.5px ivory-quiet
6. **Observed at**: mono 10.5px ivory-mute, right-aligned

**Hairline-bottom dividers between rows; last row no border.**

**The 7 layers** (mirrors backend `risk_defense.py`):

| # | name | description | data path |
|---|---|---|---|
| 01 | Value at Risk | 95% / 99% one-day, 90-day window | `risk_defense.var_95`, `var_99` |
| 02 | Correlation matrix | Pairwise 90-day; Ledoit-Wolf shrunk | `risk_defense.correlation` |
| 03 | VIX gauge | Spot vs. 30-day mean; regime classifier | `risk_defense.vix` (joined with `useMacro()` if needed) |
| 04 | Component Expected Shortfall | Tail loss attributed to each position | `risk_defense.component_es` |
| 05 | Daily drawdown | Distance from peak NAV today | `risk_defense.daily_drawdown` |
| 06 | Sector concentration | HHI on sector weights | `risk_defense.sector_hhi` |
| 07 | Cash buffer | Idle cash share of NAV | `risk_defense.cash_pct` |

---

## 4. Block 3 — `ConcentrationTable`

Top-5 positions by weight. Each row uses the **종목명 main pattern** (CEO 2026-04-26 directive).

| Prop | Type | Source |
|---|---|---|
| `top` | `ConcentrationEntry[]` | `useConcentration()` (GAP). Backend has `RISK_CORRELATION` (line 254) but no dedicated `concentration` endpoint — derive from `usePortfolioPositions()` if needed (sort by weight desc, take 5). |

```ts
interface ConcentrationEntry {
  rank: number;
  name: string;          // "Apple Inc."
  ticker: string;        // "AAPL"
  exchange: string;      // "NASDAQ"
  weightPct: number;     // 14.2
}
```

**Row layout** (`grid-template-columns: 32px 1fr 120px 1fr`):
1. Rank (Playfair 22px bronze)
2. Name (Playfair 18px ivory) + ticker line (mono 10.5px ivory-mute)
3. Weight % (mono 18px ivory)
4. Weight bar (4px tall, bronze-deep → bronze gradient)

**Note on ticker placement**: ticker line lives BELOW the name as a small `<small>` element. Never lead with the ticker. The name is always the visual 1순위.

---

## 5. Block 4 — Sector exposure 2-col

### 5.1 `SectorDonutLg`

| Prop | Type | Source |
|---|---|---|
| `sectors` | `{ name: string; pct: number; color: string }[]` | derived from `usePortfolioPositions()` (EXISTS), grouped server-side or client-side |
| `count` | `number` | distinct sector count |
| `cashPct` | `number` | from `usePortfolioSummary()` (EXISTS — needs the field added per portfolio-v2 SPEC §6) |

- 220×220 SVG donut (larger than portfolio-v2's 160×160).
- 7 ring segments using the same color ramp as portfolio-v2 (bronze, bronze-light, bronze-deep, then 4 ivory tints).
- Center: "SECTORS" eyebrow + count in Playfair 32px.
- Below the donut: eyebrow dim "Cash buffer 18.4%" — restated for emphasis since cash is its own ring segment.

### 5.2 `SectorLeaderTable`

The right card. **종목명 main pattern** in the leader column.

| Column | Width | Type |
|---|---|---|
| Sector | min-content | mono uppercase eyebrow, color matched to donut segment (bronze ramp top-3, ivory-mute for the rest) |
| Leader | flex | Playfair 16px ivory + mono 10px ticker dim below |
| Weight | min-content | mono tabular-nums, right-aligned |

**Leader logic**: for each sector in the donut, the largest position by `weight` becomes the row's leader. For Cash, "Idle balance" stands in.

---

## 6. Block 5 — `RiskTimelineChart`

| Prop | Type | Source |
|---|---|---|
| `series` | `{ t: string; score: number }[]` | `useRiskTimeline(days)` (GAP). Backend has `RISK_ROLLING_VAR` (line 255) — could feed the series, or a new `/api/risk/timeline` endpoint composes the 0–100 composite score. |
| `days` | `30 \| 90 \| 180` | local state, default 30 |
| `today` | `number` | `series[series.length-1].score` |
| `avg30` | `number` | rolling mean |
| `max30` | `number` | rolling max |
| `daysAboveStrain` | `number` | count of days above the 60 threshold |

**Visual rules**:
- 200px tall SVG, viewBox `0 0 1200 200`.
- Soft red wash on the top band (y=0..80) to mark the "STRAIN > 60" zone — `rgba(220,38,38,0.04)` (very subtle, KR-positive token at low alpha so it reads as "warning" not "loss").
- Dashed strain line at y=80 (`rgba(245,240,232,0.08)`).
- Polyline: bronze 1.6px stroke + bronze fill gradient `rgba(184,149,106,0.16)` → 0.
- Threshold label "STRAIN · 60" mono 10px ivory-mute, top-right.
- Below the chart: 4-up mini-KPI strip (Today / 30-day avg / 30-day max / Days above strain).

---

## 7. Hook & endpoint mapping

### Hooks that EXIST

| Hook | Used by | Note |
|---|---|---|
| `usePortfolioSummary()` | hero deck (cash %, NAV) | needs `cashPct` field added (also flagged in portfolio-v2 SPEC §6) |
| `usePortfolioPositions()` | concentration table, sector donut, sector leader | derive top-5 + sector grouping client-side |
| `useMacro()` | VIX cross-reference if backend doesn't include it in `risk_defense.vix` | optional |

### Hooks that DO NOT EXIST — all GAP

| Hook (proposed) | Endpoint | Endpoint exists? |
|---|---|---|
| `useRiskSummary()` | `/api/risk/summary` (`RISK_SUMMARY`, line 252 of `endpoints.ts`) | YES (constant exported, route exists) |
| `useRiskLayers()` | `/api/risk/layers` (`RISK_LAYERS`, line 253) | YES |
| `useConcentration()` | derive from `usePortfolioPositions()` OR add `/api/risk/concentration` | NO (derive client-side first; add backend route later if needed) |
| `useRiskTimeline(days)` | `/api/risk/rolling-var` (`RISK_ROLLING_VAR`, line 255) — or new `/api/risk/timeline` for the composite score | PARTIAL — rolling VaR exists but composite-score timeline may need a small backend addition |
| `useSectorExposure()` | derive from `usePortfolioPositions()` | NO (derive client-side; backend has no dedicated sector endpoint for risk) |

### Field gaps on existing endpoints

`PortfolioSummary` (hooks.ts:179–187) lacks `cashPct`. Same gap as portfolio-v2; same fix.

The home-v2 SPEC referenced `useRiskSummary` as if it existed — it does NOT. Verified by `grep -n "useRiskSummary" frontend/src/lib/`. This document treats it as a GAP to be implemented.

### Backend services

`risk_defense.py` (referenced in `CLAUDE.md` as the 7-Layer Risk Defense engine) is already complete on the backend. The frontend wire-up is the entire scope of this work — no new risk math is required.

---

## 8. Tokens used (NO new tokens)

Same set as home-v2 + portfolio-v2. Specific to this page:

| Token | Used by |
|---|---|
| `--pq-positive` (#dc2626) | Risk timeline strain wash (very low alpha 0.04), POSITIVE status label |
| `--pq-negative` (#2563eb) | NEGATIVE status label |
| `--pq-bronze` ramp | gauges, donut, weight bars, layer numbers, rank numbers |
| `--pq-ivory` ramp | layer names, value cells, gauge values |

**Banned**: any new hex code, any radius >4px, any non-Playfair/Source-Serif/JetBrains-Mono/Pretendard font, any glyph or icon set not already in v3.

---

## 9. Banned UI strings (legal)

Same legal-safe list as home-v2 / portfolio-v2:

| Banned | Replacement |
|---|---|
| `BUY` / `SELL` / `HOLD` | (none) |
| `recommend` / `recommendation` | (none — this surface is observation) |
| `advice` / `advise` / `advisory` | `observation` / `posture` |
| `AI Coach` / `투자 코치` | (none) |
| `추천` / `조언` | `관찰` / `자세` |

Risk-specific additional rules:
- Never write "high-risk" or "low-risk" as labels — use **POSITIVE / NEGATIVE / NEUTRAL** posture vocabulary.
- Never imply action: "you should reduce", "consider trimming", "exit recommended" — all banned. The page describes state, not intent.
- VaR / ES / DD copy must include "observed" or "probabilistic" framing — never present a single number as a forecast.

The disclaimer at the bottom of this page extends the standard banner with the line **"Risk metrics on this page are probabilistic observations over historical windows — not guarantees of future loss."**

---

## 10. Responsive breakpoints

| Breakpoint | Layout |
|---|---|
| `≥1280px` | All blocks as mocked |
| `1024–1279px` | Hero unchanged; gauges 2×2 stays; defense table same; sector exposure 2-col stays |
| `768–1023px` | Hero padding 56/40; gauges 2×2 stays but each card narrows; defense table column 6 ("Observed at") drops to inline below status; concentration row stacks rank-name on left + weight-pct stacked above bar on right; sector exposure 2-col → stacked 1-col |
| `<768px` | Hero h1 clamps ~32px; gauges 2×2 → 1×4; defense list collapses to a vertical card-per-layer pattern (number + name + status row, then a 2-col strip with value + threshold); concentration as cards; sector donut shrinks to 160; sector leader becomes a card list |

Mobile concrete numbers:
- Big gauge value: 44 → 36px.
- Donut: 220 → 160.
- Risk timeline height: 200 → 140.

---

## 11. A11y checklist

- [ ] H1 hero, H2 each section, H3 inside cards (gauge eyebrow → name → value reads in order).
- [ ] Big gauge: eyebrow-as-label + value as content; bar described in `aria-label="${eyebrow}: ${value}, ${posture}"`.
- [ ] Defense table: `<table>` semantics OR `role="table"` if grid; status column has `aria-label="status: ${value}"`.
- [ ] Risk timeline SVG inside `<figure>` with `<figcaption class="sr-only">` describing today's score, 30-day avg, days above strain.
- [ ] Concentration weight bars are decorative — the percentage itself is the data.
- [ ] Color paired with text: every POSITIVE/NEGATIVE/NEUTRAL has its label visible alongside the color.
- [ ] Bronze on Vantablack 6.94:1 (AA / AAA large) — same as home-v2.
- [ ] KR positive (#dc2626) and negative (#2563eb) on Vantablack: 4.93:1 and 4.86:1 respectively (passes AA normal). Verified WebAIM.
- [ ] Reduced-motion: gauge fill and timeline draw-in respect `prefers-reduced-motion`.

---

## 12. Feature flag

```ts
process.env.NEXT_PUBLIC_RISK_V2 === 'true'
```

While `false`, the existing `/risk` route (currently empty page per `qa_bug_log.md`) keeps its current behaviour. While `true`, the new layout renders. Mirrors home-v2 / portfolio-v2 pattern. Same 3-env rollout (prod=false, preview=true, dev=true).
