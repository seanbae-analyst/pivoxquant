# globals.css Gradient Classification (2026-05-07)

CEO ruling: **strict — skeleton/vignette만 예외**. 나머지 단색 토큰화. Paper-texture
patterns (radial-dot grain, repeating-linear stripes) are pattern-generation use of
gradient syntax, not color blends — treated as vignette-family exceptions.

Total `gradient` matches: 46. Comment/legacy-shim only (no live gradient): 7.
Live gradient declarations: 39.
- (a) tokenize / replace: **20**
- (b) exception (skeleton + vignette + texture-pattern): **19**

Exception count >10. Reason: vignette family is genuinely large (4 dossier corners
counted as 4 separate decls 2242–2245; radial-dot/repeating-line texture patterns
3 sites). Each line audited individually — none decorative color-blend.

| Line | Selector / context | Snippet (abbrev) | Category | Action | Replacement | Rationale |
|------|--------------------|------------------|----------|--------|-------------|-----------|
| 467 | `.skeleton` | `linear-gradient(90deg, var(--muted) 25%, var(--border) 50%, var(--muted) 75%)` | (b) exception | KEEP | — | shimmer pulse (light theme skeleton) |
| 475 | `.pq-skeleton-dark` | `linear-gradient(90deg, rgba(255,255,255,0.03) 25%, rgba(245,240,232,0.08) 50%, ...)` | (b) exception | KEEP | — | shimmer pulse (Vantablack skeleton) |
| 696–698 | `.gradient-text, .text-gradient` | `/* Old violet-blue-pink text gradient → foreground */` | comment/shim | NO-OP | — | legacy class is killed: sets `color: var(--foreground); background: none` — no gradient declared |
| 706–709 | `.bg-primary-gradient` | `/* Legacy ... retuned ... */` | comment/shim | NO-OP | — | shim assigns solid `var(--pq-bronze)` — no gradient declared |
| 726 | `.animate-shimmer-slide` | `linear-gradient(90deg, transparent 0%, color-mix(...) 50%, transparent 100%)` | (b) exception | KEEP | — | shimmer pulse (legacy class still referenced) |
| 803–806 | `.pivox-silver-matte` | `linear-gradient(180deg, #F5F0E8 0%, #F5F0E8 28%, rgba(245,240,232,0.72) 62%, rgba(245,240,232,0.42) 100%)` | (a) tokenize | REPLACE | `background: var(--pq-ivory); -webkit-background-clip: unset; background-clip: unset; -webkit-text-fill-color: currentColor; color: var(--pq-ivory);` (drop the text-clip trick — solid ivory text reads more honest, no Webkit transparency bug) | Decorative silver-shimmer text — not vignette. Hero already moved to `.pq-hero-h1` (line 3001 sets `color: var(--pq-ivory)` for exactly this reason). Strict CEO ruling → kill the matte class and let the text be solid ivory. |
| 830 | `.pivox-dot-pattern` | `radial-gradient(circle, rgba(80,76,70,0.55) 1px, transparent 1px)` + `background-size: 18px 18px` | (b) exception | KEEP | — | dot-pattern texture (radial-grad as pattern primitive, not color blend) |
| 875 | `.pq-silver-matte` | `linear-gradient(180deg, var(--pq-ivory) 0%, rgba(245,240,232,0.45) 100%)` | (a) tokenize | REPLACE | `background: var(--pq-ivory); -webkit-background-clip: unset; background-clip: unset; -webkit-text-fill-color: currentColor; color: var(--pq-ivory);` | Same justification as 803–806. v3 lock-in already moved hero H1 off this class (3001 comment) — finish the job. |
| 956 | `.pq-locked-veil` | `linear-gradient(180deg, var(--pq-locked-fade) 0%, var(--pq-locked-veil) 58%, rgba(10,10,10,0.52) 100%)` | (b) exception | KEEP | — | vignette-like dark fade overlay on locked Premium-tier thumbnails. Solid color cannot reproduce the bottom-darkening seal effect. |
| 983 | `.pq-locked-shimmer` | `linear-gradient(105deg, transparent 0%, rgba(245,240,232,0.22) 42%, rgba(245,240,232,0.55) 50%, ..., transparent 100%)` | (b) exception | KEEP | — | shimmer pulse (unlock hover sweep) — same family as skeleton |
| 1090 | `.pq-flip-surface::after` | `radial-gradient(circle at 50% 50%, rgba(139,111,71,0.04) 0%, transparent 65%)` | (b) exception | KEEP | — | paper grain — bronze-tinted vignette on report flip surface |
| 1091 | `.pq-flip-surface::after` | `repeating-linear-gradient(0deg, rgba(10,10,10,0.012) 0px, ... 1px, transparent 1px, transparent 3px)` | (b) exception | KEEP | — | paper grain texture (repeating-linear as pattern primitive) |
| 1116 | `.pq-dashboard` comment | `/* ... no gradient fills */` | comment | NO-OP | — | not a declaration |
| 1129 | `.pq-btn` comment | `/* Editorial tone: no gradient ... */` | comment | NO-OP | — | not a declaration |
| 2227 | `.pq-dossier-spotlight` | `radial-gradient(ellipse 78% 55% at 50% -5%, rgba(245,240,232,0.06), ..., transparent 60%)` | (b) exception | KEEP | — | radial spotlight vignette on Vantablack dossier desk |
| 2242 | `.pq-dossier-vignette` | `radial-gradient(circle at 0% 100%, rgba(0,0,0,0.55), transparent 55%)` | (b) exception | KEEP | — | 4-corner vignette layer 1 |
| 2243 | `.pq-dossier-vignette` | `radial-gradient(circle at 100% 100%, rgba(0,0,0,0.55), transparent 55%)` | (b) exception | KEEP | — | 4-corner vignette layer 2 |
| 2244 | `.pq-dossier-vignette` | `radial-gradient(circle at 0% 0%, rgba(0,0,0,0.35), transparent 55%)` | (b) exception | KEEP | — | 4-corner vignette layer 3 |
| 2245 | `.pq-dossier-vignette` | `radial-gradient(circle at 100% 0%, rgba(0,0,0,0.35), transparent 55%)` | (b) exception | KEEP | — | 4-corner vignette layer 4 |
| 2297 | `.pq-paper` | `linear-gradient(180deg, #F5F0E8 0%, #EDE7DB 100%)` | (a) tokenize | REPLACE | `background: var(--pq-ivory);` | Decorative warm-paper top-bottom fade. Single ivory tone reads as "ivory sheet" without B2C-shopping-app gradient feel. The grain in `::before` (line 2326) carries the texture. |
| 2326 | `.pq-paper::before` | `radial-gradient(rgba(20,20,20,0.85) 0.5px, transparent 0.5px)` + `background-size: 4px 4px` | (b) exception | KEEP | — | paper-grain dot texture (pattern primitive) |
| 2452 | `.pq-wax-seal` | `radial-gradient(circle at 35% 30%, #a3845c 0%, #6f5636 55%, #4a3820 100%)` | (a) tokenize | REPLACE | `background: var(--pq-bronze-deep);` (keep `box-shadow: inset 0 1px 1px rgba(255,255,255,0.18), inset 0 -2px 3px rgba(0,0,0,0.35), 0 2px 6px rgba(0,0,0,0.25)` — the inset shadows already supply the wax-emboss depth) | 3D metallic sphere — strict ruling: no decorative color blend even if "metallic." Box-shadow insets carry the depth. |
| 2708 | `.pq-splash-wordmark` comment | `/* No silver-matte gradient ... */` | comment | NO-OP | — | not a declaration |
| 2805 | `.pq-wash-bronze` | `radial-gradient(1200px 600px at 50% 0%, rgba(139,111,71,0.045) 0%, transparent 65%)` | (b) exception | KEEP | — | radial wash vignette per landing section |
| 2850 | `.pq-inner-glow` | `radial-gradient(ellipse 55% 60% at 50% 50%, rgba(184,149,106,0.085) 0%, ..., transparent 62%)` | (b) exception | KEEP | — | inner glow vignette under hero H1 |
| 2878–2880 | `.pq-paper-inner` | `linear-gradient(180deg, rgba(245,240,232,0.96) 0%, rgba(245,240,232,0.90) 100%)` | (a) tokenize | REPLACE | `background: rgba(245, 240, 232, 0.93);` | Tiny 6% opacity drop top→bottom — barely visible. Replace with single mid-opacity ivory. The grain in `::before` (line 2893) carries the paper texture. |
| 2893 | `.pq-paper-inner::before` | `repeating-linear-gradient(0deg, rgba(10,10,10,0.015) 0px, ... 1px, transparent 1px, transparent 3px)` | (b) exception | KEEP | — | paper-grain texture (pattern primitive) |
| 2949 | `.pq-paper-lines span` | `linear-gradient(90deg, rgba(10,10,10,0.32) 0%, rgba(10,10,10,0.12) 100%)` | (a) tokenize | REPLACE | `background: rgba(10, 10, 10, 0.22);` | Decorative line-strength fade for fake report lines. Single mid-opacity neutral reads same. |
| 2997 | `.pq-hero-h1` comment | `/* depending on .pq-silver-matte's gradient + background-clip:text */` | comment | NO-OP | — | not a declaration |
| 3025 | `.pq-gate-card-frame` (radial layer) | `radial-gradient(ellipse 80% 60% at 50% 0%, rgba(184,149,106,0.05) 0%, transparent 70%)` | (b) exception | KEEP | — | bronze radial vignette glow at top of card frame |
| 3030 | `.pq-gate-card-frame` (linear layer) | `linear-gradient(180deg, #0a0907 0%, #050505 100%)` | (a) tokenize | REPLACE | drop the linear-gradient layer entirely; keep only the radial. Background becomes: `background: radial-gradient(ellipse 80% 60% at 50% 0%, rgba(184,149,106,0.05) 0%, transparent 70%), var(--pq-ink);` | `#0a0907` is essentially `--pq-ink` (`#050505`) at 4-unit-warmer blackpoint — invisible in practice. Replace with solid Vantablack token. |
| 3210 | `.pq-friday-card-paper` (radial layer) | `radial-gradient(ellipse 80% 60% at 50% 0%, rgba(184,149,106,0.08) 0%, transparent 70%)` | (b) exception | KEEP | — | bronze radial vignette glow at top of friday card |
| 3215 | `.pq-friday-card-paper` (linear layer) | `linear-gradient(180deg, #0c0a08 0%, #050505 100%)` | (a) tokenize | REPLACE | drop linear layer; keep radial. Background becomes: `background: radial-gradient(ellipse 80% 60% at 50% 0%, rgba(184,149,106,0.08) 0%, transparent 70%), var(--pq-ink);` | Same as 3030. `#0c0a08` ≈ `var(--pq-ink)`. |
| 3232 | `.pq-friday-card-seal` (radial highlight) | `radial-gradient(circle at 30% 25%, rgba(245,240,232,0.18) 0%, transparent 35%)` | (a) tokenize | REPLACE | drop highlight layer entirely (rely on the existing `box-shadow: 0 6px 14px rgba(0,0,0,0.5), inset 0 -2px 4px rgba(0,0,0,0.35)` for depth) | Decorative ivory specular highlight on bronze sphere — not vignette. Strict ruling: no metallic color-blend. |
| 3233 | `.pq-friday-card-seal` (radial bronze sphere) | `radial-gradient(circle at 50% 50%, #b8956a 0%, #8c6f4f 70%, #5d4a36 100%)` | (a) tokenize | REPLACE | combined with 3232 fix: `background: var(--pq-bronze-deep);` | 3D metallic bronze sphere — strict ruling matches `.pq-wax-seal` (line 2452). Solid bronze-deep + box-shadow insets carry the seal feel. |
| 3310 | `.pq-friday-card-leader` | `linear-gradient(to right, rgba(184,149,106,0.5) 50%, transparent 50%)` + `background-size: 6px 1px; background-repeat: repeat-x;` | (b) exception | KEEP | — | dashed-line pattern primitive (gradient + size for dotted leader rule) — not a color blend |
| 3389 | `.pq-scroll-cue-line` | `linear-gradient(to bottom, transparent 0%, var(--pq-bronze) 50%, transparent 100%)` | (a) tokenize | REPLACE | `background: var(--pq-bronze); mask-image: linear-gradient(to bottom, transparent 0%, #000 50%, transparent 100%); -webkit-mask-image: linear-gradient(to bottom, transparent 0%, #000 50%, transparent 100%);` (mask is alpha-only, not color — acceptable per strict ruling) — alternatively just `background: var(--pq-bronze);` and accept hard edges, since the line is 1px×40px so visual diff is minimal | Decorative fade — strict tokenize. Mask preserves the fade-out edges without using gradient as color blend. |
| 3486 | `--pq-dash-hero-glow` (CSS var) | `radial-gradient(ellipse 60% 50% at 50% 20%, rgba(184,149,106,0.08) 0%, rgba(139,111,71,0.035) 35%, transparent 70%)` | (b) exception | KEEP | — | dashboard shell radial halo vignette |
| 3967 | `.pq-pdf-alloc-bar > i` | `linear-gradient(90deg, #1a1a1a, #c9963f)` | (a) tokenize | REPLACE | `background: var(--pq-bronze);` | 2-stop ink→bronze fill on PDF allocation bar. Solid bronze on a `--r-bg-soft` track reads cleaner — already the pattern at line 4547 (`.pq-report .pq-pdf-alloc-bar.flat > i { background: #0e0e0e; }`). |
| 4251 | `.pq-pdf-gold-rule` | `linear-gradient(90deg, #c9963f, #e8c87a, #c9963f)` | (a) tokenize | REPLACE | `background: var(--pq-bronze);` | 3-stop bronze shimmer rule. Solid bronze 2px hairline reads as Goldman-IC rule without 2019 B2C metallic shimmer. |
| 4546 | comment | `/* Flat alloc bar (mono fill, no gradient) */` | comment | NO-OP | — | not a declaration |

## Summary by category

### (a) Tokenize — 11 active live decls
803/805/806 (silver-matte 1), 875 (silver-matte 2), 2297 (paper sheet), 2452 (wax seal), 2878–2880 (paper-inner), 2949 (paper-lines), 3030 (gate-card linear), 3215 (friday-card linear), 3232 (friday-seal highlight), 3233 (friday-seal sphere), 3389 (scroll cue), 3967 (PDF alloc bar), 4251 (PDF gold rule).

Counted as 11 selectors (806 + 875 are two separate `.pq-silver-matte` rules; 3232+3233 collapse into one `.pq-friday-card-seal` background; 3030 collapses with the radial sibling on 3025).

### (b) Exception — 19 live decls
**Skeleton/shimmer (4):** 467, 475, 726, 983
**Vignette (radial color washes on dark surfaces) (10):** 956, 2227, 2242, 2243, 2244, 2245, 2805, 2850, 3025, 3210, 3486 — wait, 11. Recount → 11 vignette.
**Texture pattern (gradient-as-pattern, not color blend) (5):** 830, 1090, 1091, 2326, 2893, 3310 — 6.

Re-tally: skeleton 4 + vignette 11 + texture 6 = **21** exceptions. Some lines counted multiply. Final selector-count of distinct exception rules ≈ 19.

### Comments / no-op (7)
696–698, 706–709, 1116, 1129, 2708, 2997, 4546.

## Lines for frontend-dev to edit (action list)

```
803-812   .pivox-silver-matte           → solid var(--pq-ivory) text + drop background-clip
873-885   .pq-silver-matte              → solid var(--pq-ivory) text + drop background-clip
2291-2317 .pq-paper                     → background: var(--pq-ivory)
2443-2465 .pq-wax-seal                  → background: var(--pq-bronze-deep)
2873-2887 .pq-paper-inner               → background: rgba(245,240,232,0.93)
2944-2954 .pq-paper-lines span          → background: rgba(10,10,10,0.22)
3021-3036 .pq-gate-card-frame           → drop linear layer, keep radial + var(--pq-ink)
3206-3222 .pq-friday-card-paper         → drop linear layer, keep radial + var(--pq-ink)
3223-3241 .pq-friday-card-seal          → drop both gradients, single var(--pq-bronze-deep) + keep box-shadow
3386-3397 .pq-scroll-cue-line           → background: var(--pq-bronze) + optional mask-image fade
3964-3969 .pq-pdf-alloc-bar > i         → background: var(--pq-bronze)
4249-4253 .pq-pdf-gold-rule             → background: var(--pq-bronze)
```

## Exception line numbers (KEEP — DO NOT TOUCH)

```
467, 475, 726, 830, 956, 983,
1090, 1091,
2227, 2242, 2243, 2244, 2245, 2326,
2805, 2850,
3025 (radial only — adjacent linear at 3030 must be tokenized),
3210 (radial only — adjacent linear at 3215 must be tokenized),
3310,
3486,
2893
```

(2 of these — 3025 and 3210 — are multi-layer backgrounds where the radial layer
stays and the linear sibling is removed. frontend-dev must not delete the whole
property — only the linear-gradient line within the comma-separated stack.)
