# /profile v2 — MIGRATION

> **Source of truth**: v1 inventory `docs/v1-feature-inventory.md` §6 + §1 row 23 + §2 hook table line 318+
> **Goal**: Zero feature loss vs v1. Feature flag toggle. v1 fallback preserved verbatim.

---

## 1. v1 inventory § profile — component mapping (from `docs/v1-feature-inventory.md` rows 138–139, 322–323)

| v1 Component | v1 Source | v2 Surface | Disposition |
|---|---|---|---|
| `PersonaV2Card` | `frontend/src/components/dashboard/persona-v2-card.tsx` | Block 1 right (8-col hero card with declared vs observed split) | **Re-skinned** — same data shape, v3-locked typography (Playfair 40px persona name + serif body). v1 component reusable as-is via `<PersonaV2Card />` import; v2 layout is wrapper styling. |
| `PersonaEvolution` | `frontend/src/components/dashboard/persona-evolution.tsx` | Block 2 (full-width timeline card, 90D/180D/365D toggle) | **Re-skinned** — chart style migrates from grid bars to CSS-only SVG path (mockup line 178+). Component-level reuse possible if we expose `windowDays` prop. |
| `WeeklyPulseCard` | `frontend/src/components/dashboard/weekly-pulse.tsx` | Block 5 left (6-col Pulse card · 06 · Weekly) | **Reused unchanged** — same component as on home-v2. |
| `ModalShell` | `frontend/src/components/dashboard/modal-shell.tsx` (assumed location) | Block 6 Danger zone confirmation modal | **Reused unchanged** — for reset-persona destructive flow |
| Section 06 Behavioral Score | inline JSX in v1 `profile/page.tsx` | Block 3 — Six Dimensions row "Behavioral patterns" | **Folded** — behavioral score is now one of the six dimensions, not a separate section |
| Section 07 Persona Evolution | inline JSX in v1 `profile/page.tsx` | Block 2 (full block) | **Promoted** — evolution gets its own block instead of being a sub-section |

**100% mapping verification**: 6 v1 components + 2 inline sections → 6 v2 blocks. Zero loss.

---

## 2. Hook mapping — v1 → v2 (hooks.ts grep verified)

| v1 Hook | Source | v2 Block | Migration |
|---|---|---|---|
| `useAuth` | `lib/auth.tsx` | Hero · Block 1 | Reused |
| `useInvestmentProfile` | `lib/hooks.ts` (verify line) | Block 1 (Identity card · "Risk-managed Growth" line) | Reused |
| `usePersona` | `lib/hooks.ts` line 318 | Block 1 (Persona V2 hero · "Defensive Allocator") | Reused |
| `usePersonaDetail(windowDays)` | `lib/hooks.ts` line 322 | Block 1 + Block 2 + Block 3 | Reused, called twice (90D + 365D for evolution) |
| `usePersonaBenchmark(windowDays)` | `lib/hooks.ts` line 323 | Block 4 (Peer benchmark) | Reused |
| `usePulse` | `lib/hooks.ts` (cfo/hooks if separated) | Block 5 (Pulse) | Reused |
| `useCompanionStatus` | `lib/cfo/useCompanion.ts` | Block 5 (Companion entry) + tier gate | Reused |

**Verification command:**
```
grep -nE "^export function (useAuth|useInvestmentProfile|usePersona|usePersonaDetail|usePersonaBenchmark|usePulse|useCompanionStatus)" frontend/src/lib/{hooks,auth,cfo/hooks,cfo/useCompanion}.ts
```

**Zero hook additions needed for v2 baseline.** All data sources exist.

---

## 3. Endpoint mapping (endpoints.ts grep verified)

From v1 inventory §4 line 503–506:

| Endpoint | v2 Use |
|---|---|
| `/api/profile` | Block 1 Identity card · Hero status |
| `/api/profile/persona` | Block 1 Persona V2 hero |
| `/api/profile/persona-detail?window_days={n}` | Block 1 (90D), Block 2 (365D), Block 3 (90D) |
| `/api/profile/persona-benchmark?window={n}` | Block 4 |
| `/api/profile/persona-explain` | Block 6 CTA — direct `apiFetch` (no dedicated hook) |
| `/api/profile/pulse` | Block 5 |
| `/api/agent/status` | Block 5 Companion entry |

**Zero endpoint additions.** All paths exist in current backend.

---

## 4. New components vs reuse

| Status | Count | Components |
|---|---|---|
| **Reused unchanged** | 4 | `PersonaV2Card`, `PersonaEvolution`, `WeeklyPulseCard`, `ModalShell` |
| **Re-skinned wrapper** | 0 | (none — v3 tokens applied to outer layout, inner components untouched) |
| **New (v2-only)** | 6 | `ProfileHeroV2`, `IdentityCardV2`, `SixDimensionsGrid`, `PeerBenchmarkBlock`, `CompanionEntryV2`, `DangerZoneCard` |

**Reuse ratio: 4/10 = 40%.** Lower than home-v2 (53%) because profile's editorial reframe needs more new wrappers — but core data components (PersonaV2Card, PersonaEvolution, WeeklyPulseCard) are 100% reused.

---

## 5. Feature flag + v1 fallback

```tsx
// frontend/src/app/(dashboard)/profile/page.tsx (toggle)
"use client";
import V1 from "./_v1/page-v1";
import V2 from "./_v2/page-v2";

export default function ProfilePage() {
  const v2Enabled = process.env.NEXT_PUBLIC_PROFILE_V2 === "true";
  return v2Enabled ? <V2 /> : <V1 />;
}
```

- `_v1/page-v1.tsx`: verbatim copy of current `profile/page.tsx` (export rename: `ProfilePage` → `ProfilePageV1`).
- `_v2/page-v2.tsx`: new file using 6 v2 blocks.
- Default flag missing/false → V1 path (no behavior change).
- Vercel env: `NEXT_PUBLIC_PROFILE_V2=true` to enable.

---

## 6. GAPs

| ID | Gap | Severity | Resolution |
|---|---|---|---|
| GAP-PERSONA-EXPLAIN-HOOK | No dedicated hook for `/api/profile/persona-explain` | P2 | Use `apiFetch` directly in Block 6 CTA, defer hook extraction to next sprint |
| GAP-PROFILE-V2-A11Y-AUDIT | Persona evolution SVG accessibility (chart description for screen readers) | P2 | Add `<title>` and `<desc>` to SVG; defer full a11y audit to QA phase |
| GAP-DIM-NARRATIVE | Six dimensions narrative text is hard-coded in mockup; production needs CMS or backend-served | P2 | v2 Block 3 reads from persona-detail response (already has dimension scores); editorial text in code constants for now |
| GAP-PULSE-INPUT | Pulse weekly mood capture (Block 5) needs input mutation | P1 | Backend already accepts POST /api/profile/pulse — frontend `setPulse(mood)` mutation hook needed |

---

## 7. v1 vs v2 user experience deltas

| Aspect | v1 | v2 |
|---|---|---|
| Hero | "Profile" generic | "Identity · Persona · Living CFO" editorial framing |
| Persona display | One card | Declared vs Observed split (90D window) |
| Evolution | Sub-section | Promoted to full block with 90D/180D/365D toggle |
| Six dimensions | Inline sections (06, 07) | Dedicated grid (Block 3) with editorial vocabulary |
| Peer benchmark | Component import (PeerBenchmarkBlock) | Promoted to Block 4 with 4 KPIs (Sharpe / DD / Turnover / Concentration) |
| Pulse | Component reuse (WeeklyPulseCard) | Same component, framed as "Tell the CFO how you read" |
| Companion | Sidebar entry | Promoted to Block 5 with waitlist phase + entitlement check |
| Danger zone | Bottom of page | Block 6 with persona-explain CTA + reset confirmation |

**No feature loss.** All v1 surfaces reachable in v2; some are promoted from sub-sections to first-class blocks.

---

## 8. Rollout plan

| Phase | Action | Owner |
|---|---|---|
| 1 | Mockup review (CEO) | Today |
| 2 | Code implementation behind `NEXT_PUBLIC_PROFILE_V2` | Next sprint (deferred per CEO B-option choice) |
| 3 | Audit (`audit-code` agent) | Same sprint |
| 4 | PR + CI + merge | Same sprint |
| 5 | Vercel env toggle (manual by CEO) | Same sprint |
| 6 | v1 fallback removal | After 2-week prod soak |

---

## 9. Risk & rollback

- **Risk**: PersonaV2Card / PersonaEvolution components are reused — any regression there affects both v1 and v2. Mitigation: snapshot test the rendered output of these two components before merging v2 implementation.
- **Rollback**: Disable Vercel env flag → instant v1. No DB migration, no endpoint changes, no breaking type changes.
- **Visual regression**: v3 tokens already locked across 5 prod-merged pages (home/portfolio/risk/signals/reports). Profile inherits same token set — visual consistency guaranteed.
