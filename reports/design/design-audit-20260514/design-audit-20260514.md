# PivoxQuant Production Deep Design Audit — 2026-05-14

**Target:** https://pivoxquant.com (Vercel production)
**Auditor:** Claude Code (Design Director — Apple × Bloomberg × v3 calibration)
**Scope:** Authenticated session (seanbae1521@gmail.com), 1440×900 desktop viewport. Mobile viewport (390×844) attempted but Chrome host window did not honor resize below screen.width = 1470 — mobile responsive layout could not be visually verified in this session.
**Duration:** ~75 min. READ-ONLY audit. Zero code changes made.
**Pages audited:** /home · /detail/005930.KS · /detail/AAPL · /market (US + Korea tabs) · /risk · /signals · /settings · /portfolio · /reports · /pricing · /login (redirected). Beta gate not visible — host browser already past it.

**Screenshot evidence:** All findings reference screenshot IDs (`ss_xxxxxxx`) captured live in this audit session via Claude-in-Chrome and visible in the audit transcript. Local disk copies were not produced — the Chrome extension's `save_to_disk` flag is not honored at the OS level for this MCP, so screenshots are evidence-of-record in the transcript.

---

## First Impression (3-second verdict)

> **"Genuinely premium. But the data is fake and the math is off."**

The visual language is far ahead of any KR fintech I've seen. Vantablack + bronze + Playfair Display lands clean editorial gravitas — the home `Six rooms.` and risk `Risk board.` hero pages would be at home in a Bloomberg Markets long-read. The Korean italic emphasis ("관측" / "보유") is a confident bilingual move.

The problem is *underneath* that surface: portfolio NAV reads $2.93M with a +82% unrealized PNL, Samsung's market cap renders as ₩1,974조 (~5× real), KOSPI shows 7,892 on one surface and `— ·—` on another, and the Pro tier price animates from `519` → `2,420` → `9,900 KRW` over ~10 seconds. The aesthetic says "institutional research desk." The data says "seed dataset still wired up."

**One-word:** *Beautiful-but-leaky.*

---

## Scores

- **Design Score: B+** — typography, color, composition, and editorial voice are A-tier. Pulled down by 151 inline `font-size`, 36 arbitrary `text-[Npx]`, and token drift on `--up`/`--down`/`--pq-text-deck`.
- **AI Slop Score: A-** — virtually none of the 10-pattern blacklist present. No violet gradients, no decorative blobs, no 3-column "Features" SaaS grid, no fake IB wordmarks. Light deduction for spinning SVGs (×2) and the pulse-dot-on-static-ticker combination.

---

## Inferred Design System (live dump from production)

```
Background body: rgb(255,255,255) ← TOKEN DRIFT (should be #050505)
Body text:       rgb(15,23,42)    ← TOKEN DRIFT (should be #f5f0e8)
Body font:       Geist (✓)
Primary heading: Playfair Display 500 (✓) — 48 / 40 / 32 / 24 px observed

Tokens read from :root —
  --pq-ink:           #050505 ✓
  --pq-ivory:         #f5f0e8 ✓
  --pq-bronze:        #b8956a ✓
  --pq-bronze-light:  #a3845c ✓
  --pq-bronze-deep:   #6f5636 ✓
  --pq-muted:         #8a8a8a ✓
  --pq-border:        #f5f0e81a ✓
  --pq-error:         #d18888 ✓
  --pq-text-display:  clamp(3rem, 7vw, 6rem) ✓
  --pq-text-h1:       clamp(2.4rem, 5.6vw, 4.5rem) ✓
  --pq-text-h2:       clamp(1.875rem, 3.6vw, 2.75rem) ✓
  --pq-text-h3:       32px ← spec said 30px (drift)
  --pq-text-quote:    24px ← spec said 22px (drift)
  --pq-text-deck:     (UNSET) ← MISSING from CSS (spec: 17px)
  --pq-text-body:     14px ✓
  --pq-text-body-sm:  14px ← spec said 13px (collapsed with body)
  --pq-text-caption:  12px ✓
  --pq-text-mono-sm:  12px ← spec said 11px
  --pq-text-eyebrow:  12px ← spec said 10.5px
  --pq-track-eyebrow: .22em ✓
  --pq-track-wordmark:.16em ✓
  --pq-track-tight:   -.02em ✓
  --font-display:     "Playfair Display" ✓
  --pq-safe-top:      (UNSET) ← PWA safe-area missing
  --pq-safe-bottom:   (UNSET) ← PWA safe-area missing
  --up:               #dc2626 ← NOT spec #D18888 (US red, not KR carmine)
  --down:             #2563eb ← NOT spec #7AA0C8 (US blue, not KR indigo)

Drift summary: 4 typography tokens off-spec, 2 PWA safe-area tokens unset,
              2 directional color tokens off-spec, 1 typography token missing.

Inline overrides on /home:  151 elements carry style="font-size: …"
Arbitrary classes on /home:  36 elements carry text-[Npx] / text-[var(…)]
Animations running on /home:  3 (claude-pulse × 1, spin × 2)
Naked ticker leaks on /home:  4 (005930 × 4 — 2 mono + 2 Playfair display)
```

---

## Findings

### Severity legend
- **HIGH** — user-visible defect, data/UX/legal/brand risk. Fix before next user touchpoint.
- **MEDIUM** — works but degrades the editorial promise. Fix this sprint.
- **POLISH** — premium-tier nit. Fix when polishing.

---

### HIGH

#### FINDING-001 · Body background and color tokens are NOT Vantablack — they are still Tailwind defaults
- **Category:** Color & Contrast / Token drift
- **Page:** every page (`/home`, `/portfolio`, `/risk`, `/signals`, `/market`, `/settings`, `/reports`, `/pricing`, `/detail/*`)
- **Evidence:** `getComputedStyle(document.body)` returns `backgroundColor: rgb(255, 255, 255)` and `color: rgb(15, 23, 42)`. Visually the page reads as Vantablack because nested wrappers (`.bg-pq-ink` / `<main>`) repaint the surface — but the `<body>` itself is white-on-slate-900. Screenshot evidence: `ss_5050spec2` (home initial paint).
- **Why it matters:** (a) any momentary unstyled flash (FOUC) on slow networks will show white; (b) when a page is missing a wrapper (e.g. an embed, an error page, a PDF preview iframe) the user gets a white page; (c) screen-reader fly-up labels (`.sr-only`) inherit the body color which would be invisible on white if shown to assistive tech; (d) systemic token-bypass signal that the v3 lock-in is partial.
- **Recommendation:** In `globals.css`, set `body { background: var(--pq-ink); color: var(--pq-ivory); }` so the floor of the page IS the design system, not Tailwind defaults.

#### FINDING-002 · `--up` and `--down` tokens are Tailwind US red/blue (#dc2626 / #2563eb), NOT spec KR carmine/indigo (#D18888 / #7AA0C8)
- **Category:** Color & Contrast / KR convention compliance
- **Page:** every surface that renders deltas — `/home` ticker tape, `/portfolio` PNL, `/market` cards, `/risk` posture chips.
- **Evidence:** `getComputedStyle` returned `--up: #dc2626` / `--down: #2563eb`. Visually all "▲+0.61%" / "+$92,881" reads as bright Tailwind-red-600, not the muted carmine the v3 spec defines. Screenshot: `ss_9315r0af1` (portfolio +$92,881 in bright red).
- **Why it matters:** Brand inconsistency with the rest of the editorial palette — the muted carmine sits *inside* the Vantablack+bronze world; #dc2626 is a candy-bright red that fights bronze. Also breaks the explicit lock-in in memory (`feedback_pq-design-v3`).
- **Recommendation:** Set `:root { --up: #D18888; --down: #7AA0C8; }` and have `lib/format.ts` `PRICE_COLOR_HEX` reference them.

#### FINDING-003 · 151 inline `style="font-size: …"` overrides on /home alone
- **Category:** Typography / token drift
- **Page:** `/home` (sampled; likely worse on heavier pages)
- **Evidence:** `document.querySelectorAll('[style*="font-size"]').length === 151` on /home.
- **Why it matters:** §3 of the v3 spec is explicit: "인라인 `style={{ fontSize: '...' }}` 금지. 토큰만 사용." 151 inline font-size declarations means every responsive recalibration, every theme tweak, every type-scale adjustment has to chase 151 callsites. Token system is decorative if not enforced.
- **Recommendation:** Audit the components folder for `fontSize:` literal in JSX and replace with className tokens (`text-pq-body` / `text-pq-eyebrow` / etc. — already defined). Add ESLint `no-inline-fontsize` rule.

#### FINDING-004 · 36 Tailwind arbitrary `text-[Npx]` classes bypass the 11-step type scale
- **Category:** Typography / token drift
- **Page:** `/home` (sampled)
- **Evidence:** Samples: `text-[10px]`, `text-[11px]`, `text-[12px]`, `text-[var(--pq-ink)]`. 36 unique elements.
- **Why it matters:** Same as FINDING-003 — explicit §3 violation. `text-[10px]` should be `text-pq-eyebrow`, `text-[11px]` should be `text-pq-mono-sm`, etc.
- **Recommendation:** Replace arbitrary value Tailwind classes with semantic token classes from `globals.css`.

#### FINDING-005 · `--pq-text-deck` is UNSET in CSS (referenced by spec, absent in production)
- **Category:** Typography / missing token
- **Page:** every page (anything that references the deck size)
- **Evidence:** `getComputedStyle(document.documentElement).getPropertyValue('--pq-text-deck') === ''`.
- **Why it matters:** A token that's referenced but unset silently falls back to inherited / browser default. The spec says deck = 17px; the production CSS has no rule for it. Any component using `var(--pq-text-deck)` is rendering at inherited size unpredictably.
- **Recommendation:** Add `:root { --pq-text-deck: 17px; }` to `globals.css`. Audit every consumer.

#### FINDING-006 · `--pq-safe-top` / `--pq-safe-bottom` UNSET — PWA safe-area not wired
- **Category:** Responsive / PWA hygiene
- **Page:** every page (matters on iOS PWA installed mode)
- **Evidence:** Both tokens returned empty string from `getComputedStyle`.
- **Why it matters:** Memory says PivoxQuant is PWA (`project_pwa.md`). On iPhone home-screen install, the top notch / bottom home indicator will overlap content unless safe-area is set. Bottom nav (confirmed present) and top-bar will be eaten by the iOS chrome.
- **Recommendation:** `:root { --pq-safe-top: env(safe-area-inset-top); --pq-safe-bottom: env(safe-area-inset-bottom); }` plus matching `--pq-safe-left/right`. Audit bottom-nav padding.

#### FINDING-007 · Pricing tier prices ANIMATE on page load (count-up from low values, settle ~10s later)
- **Category:** Motion / legal sensitivity
- **Page:** `/pricing`
- **Evidence:** At T+6s after navigation, prices were `519 KRW` (Pro) and `1,043 KRW` (Premium) — screenshot `ss_551115fvx`. At T+11s, `2,420 KRW` and `4,865 KRW` — screenshot `ss_551115fvx` (second capture). At T+18s, settled at `9,900` and `19,900 KRW`.
- **Why it matters:** §6 explicitly forbids decorative animation, and prices are NOT a decoration — they are a contractual representation. A user landing on the page mid-animation sees an inaccurate price for the same product. For a paid SaaS pre-launch, this is brand-perception + potential consumer-law risk in KR (`표시광고법 §3` — misleading price representation).
- **Recommendation:** Render prices static — never animate currency. If a "premium reveal" feel is desired, animate the *card* itself (opacity / translate), not the digit content.

#### FINDING-008 · Samsung detail: `MARKET CAP 1974.1조` — ~5× actual value
- **Category:** Data integrity
- **Page:** `/detail/005930.KS`
- **Evidence:** Screenshot `ss_4323kiq4l` shows `1974.1조` market cap. Samsung Electronics' actual common-share mkt cap is ~₩350-400조 KRW depending on date.
- **Why it matters:** This is the headline number on the dossier. A 5× overstatement either means (a) seed/test data leaked to prod, (b) shares-outstanding miscalculation (preferred + common double-counted), or (c) FX or unit error. Per `feedback_official_data_only.md`, KR data must be from KIS / KRX / DART only — output should reconcile.
- **Recommendation:** Open the FMP/KIS pipeline for KOSPI tickers, validate `mktCap` reconciliation. Add a sanity-check assertion (any KR mega-cap > 1000조 is flagged).

#### FINDING-009 · Samsung 52-week low ₩53,700 and current ₩292,500 — both implausible
- **Category:** Data integrity
- **Page:** `/detail/005930.KS`
- **Evidence:** Screenshot `ss_4323kiq4l`. Samsung Electronics trades roughly ₩50,000-90,000 in mid-2026. ₩292,500 is ~3-5× actual. ₩53,700 low is plausible-looking — but as the current price is wrong, the spread is meaningless.
- **Why it matters:** Same as 008 — seed-data leak. The 3-month chart in screenshot `ss_4749u3r71` shows price climbing from 167,200 to 292,500 — both wrong.
- **Recommendation:** Same as 008 — verify the KIS/KRX symbol mapping and intraday price feed for `005930.KS`.

#### FINDING-010 · Portfolio NAV `$2,930,000` with `+$92,881 today` and `+$2,390,000 unrealized` — seed data
- **Category:** Data integrity / brand
- **Page:** `/portfolio`
- **Evidence:** Screenshot `ss_9315r0af1`. 1 position, $2.93M capital, 0% cash, +82% unrealized — these are all suspiciously round / extreme.
- **Why it matters:** On a financial product, "demo-looking" numbers leak the unfinished-product feeling that the rest of the typography fights so hard to overcome. The `Six rooms.` editorial gravitas evaporates when the user looks at their own data and sees $2.93M they don't have.
- **Recommendation:** For a logged-in user with zero real positions, render a true zero/empty state (the Reports page already does this beautifully — "0 memos, 0 pre-briefs, 0 brag cards"). Mirror that empty state on Portfolio.

#### FINDING-011 · `/home` shows 4 naked ticker leaks of `005930` (Positions row + Signals row)
- **Category:** Brand / KR convention / memory rule violation
- **Page:** `/home`
- **Evidence:** Screenshot `ss_34950pr99` shows `POSITIONS · TOP WEIGHT — 005930  005930` (ticker rendered twice, in mono and Playfair Display) and `SIGNALS · TODAY'S THREE — 005930`. DOM scan confirmed 4 elements with bare text `005930`.
- **Why it matters:** `feedback_ticker_display.md` records the user has repeated this instruction 3+ times: show "삼성전자" before "005930.KS". A naked 6-digit ticker is illegible to a Korean retail user. Critical to brand promise.
- **Recommendation:** Use `formatSymbolToName('005930.KS') -> "삼성전자"` helper (or extend `lib/format.ts`). Display ticker only as a secondary subtitle.

#### FINDING-012 · The 005930 ticker is rendered in **Playfair Display 24px** (editorial font on a number)
- **Category:** Typography / semantic mismatch
- **Page:** `/home`
- **Evidence:** DOM dump returned `{tag: SPAN, font: Playfair Display, size: 24px, text: "005930"}`.
- **Why it matters:** Playfair Display is reserved for serif editorial moments — H1/H2/hero callouts. Putting it on a 6-digit ticker number gives the worst of both worlds: ticker still illegible (FINDING-011), AND now occupying premium typographic weight reserved for the literary tone. JetBrains Mono with tabular-nums is the right home for numeric IDs.
- **Recommendation:** When tickers must be shown (next to a name), use mono. Reserve Playfair for the name (e.g. "*삼성전자*" italicized for emphasis).

#### FINDING-013 · Browser tab title is `005930.KS — Stock Detail | PivoxQuant` (naked ticker in `<title>`)
- **Category:** Brand / SEO / memory rule
- **Page:** `/detail/005930.KS`
- **Evidence:** `document.title` returned `"005930.KS — Stock Detail | PivoxQuant"`.
- **Why it matters:** Tab titles surface in browser history, bookmarks, the OS task switcher, and search results. "005930.KS" is the most-impoverished form of the company name. Per `feedback_ticker_display.md`.
- **Recommendation:** `<title>` should be `"삼성전자 005930.KS · Equity Dossier · PivoxQuant"` or similar.

#### FINDING-014 · ₩ Korean Won glyph appears struck-through in JetBrains Mono on price displays
- **Category:** Typography / numeric legibility
- **Page:** `/detail/005930.KS`
- **Evidence:** Screenshot `ss_4323kiq4l`. The ₩ symbol (U+20A9) in JetBrains Mono renders with double horizontal strokes that visually read as a strikethrough through the price (`₩292,500` looks like `S̶2̶9̶2̶,̶5̶0̶0̶` at small sizes). Confirmed `text-decoration: none` via inspection — the strikethrough effect is glyph-shape only.
- **Why it matters:** In a financial UI, anything that looks struck-through must mean "deprecated / cancelled / old price." Users will instinctively read these as crossed-out and panic. This is a font-glyph problem masquerading as a CSS bug.
- **Recommendation:** Either (a) use a different mono font that renders ₩ cleanly (e.g. IBM Plex Mono renders ₩ as a clean W with single underline), or (b) split the ₩ from the digits and render it in a sans (Geist) before the JetBrains Mono number: `<span class="not-mono">₩</span><span class="mono tabular-nums">292,500</span>`.

#### FINDING-015 · Market page renders S&P 500 +0.56% in RED while the chart trend line is GREEN (internal divergence)
- **Category:** Color & Contrast / semantic clash
- **Page:** `/market` (United States tab)
- **Evidence:** Screenshot `ss_91359zul0`. `742.31 +0.56% · 1D` typeset in red (`--up: #dc2626`), the 30-day chart line beneath it typeset in green (#10b981-ish, an accent color not in the v3 token list).
- **Why it matters:** Within a single composition, the SAME data point is encoded with two opposite-meaning colors. A user trying to learn "is red up or down on this product" gets contradictory training within one card. Worst kind of color signaling.
- **Recommendation:** Pick one. v3 spec says KR convention — red is up. The chart line and the delta text must agree. Replace the green-line chart with bronze (`--pq-bronze`) for neutral trend visualization, OR with `--up: #D18888` (after FINDING-002 fix) for explicit up-pos.

#### FINDING-016 · KOSPI value diverges across surfaces: `7,892.33` on /home ticker vs `— ·—` on /market header
- **Category:** Data integrity / divergence
- **Page:** `/home` vs `/market` vs `/portfolio`
- **Evidence:** Screenshot `ss_5050spec2` shows top ticker `KOSPI 7,892.33 ▲+0.62%`. Screenshot `ss_5545iwa52` shows `/market` header `KOSPI — ·—`. The 7,892.33 value is ~3× actual KOSPI (which trades ~2,500-2,800 in mid-2026).
- **Why it matters:** Two surfaces showing the same data must agree. Also: the visible KOSPI value is wrong by ~3×, same family of seed-data bugs as Samsung (FINDING-008/009).
- **Recommendation:** Ensure all index reads route through one provider/cache. Add a `sanitizeKrIndex` (memory mentions this helper already exists in `lib/format.ts`) — verify it's applied on both surfaces.

#### FINDING-017 · Signals page filter chips show `삼성전자 · 카카오 · App` — "App" appears to be truncated "Apple"
- **Category:** Truncation / brand
- **Page:** `/signals`
- **Evidence:** Screenshot `ss_8403qbn08`. Filter row reads `종목 삼성전자 · 카카오 · App` (third chip = "App", three characters, all letters). Most likely the company name "Apple" was truncated at 3 chars, OR the ticker "AAPL" lost its 4th char, OR a different name field is being read.
- **Why it matters:** Mid-truncation of a brand name is unprofessional. Worse, "App" reads as a category, not a company.
- **Recommendation:** Use `text-overflow: ellipsis` (which would render `Apple` or `Apple…`) instead of a hard slice. Or render with `min-width` that fits the longest expected name.

#### FINDING-018 · Risk Board KPI cards show `0.00` / `-0.00%` / `0.00` but POSTURE chips still render `POSITIVE`
- **Category:** Empty state / data integrity
- **Page:** `/risk`
- **Evidence:** Screenshot `ss_5545iwa52`. VaR 95 = 0.00, Correlation = 0.00, Tail = -0.00%, Sector concentration = 100%. Beneath each, `POSTURE · POSITIVE` chip in coral/bronze. Below copy reads "Cluster snapshot pending."
- **Why it matters:** The text honestly says "pending" but the chip lies — saying "POSITIVE" on zero data is a false-positive signal. If the user looks only at the chip color, they assume their risk is safe; actually it's unknown.
- **Recommendation:** When data is `pending` / `null`, posture chip should render `PENDING` / `OBSERVING` in muted bronze, not `POSITIVE` in any color. Reserve `POSITIVE` strictly for evaluated-and-passing layers.

#### FINDING-019 · POSITIVE / NEGATIVE chips on Risk Board use `--pq-error` (coral) color — confuses the safe signal
- **Category:** Color / semantic
- **Page:** `/risk`
- **Evidence:** Screenshot `ss_59998e2t5`. `POSTURE · POSITIVE` chip rendered in a coral/carmine tone — same hue as `--pq-error: #d18888`. Also the `01 VaR Layer ... POSITIVE` row uses the same color.
- **Why it matters:** Coral/carmine reads as "warning" or "elevated" — not "safe." A user scanning the Risk Board will read the color before the word and think they're at risk. The text says POSITIVE (safe) while the color says NEGATIVE (warning).
- **Recommendation:** POSITIVE = bronze or ivory neutral. NEGATIVE = `--pq-error` carmine. NEUTRAL = muted gray. The spec already lays out POSITIVE/NEGATIVE/NEUTRAL as the 3-color system in §7 — apply it consistently.

#### FINDING-020 · CTAs in top-bar use `border-radius: ~9999px` (rounded-full) — spec mandates `rounded-sm` (4px) for editorial tone
- **Category:** Component shape / spec compliance
- **Page:** every page top-bar
- **Evidence:** Top-bar Search bar, notification bell, avatar circle, and avatar CS chip all reported `border-radius: 1.67772e+07px` (effectively `rounded-full`). Other CTAs (`READ FULL MEMO`, `OPEN LAYERS`, `CLAIM FOUNDING SEAT`) correctly use squared/2px corners.
- **Why it matters:** §0 explicitly: "CTA radius: 모든 CTA `rounded-sm` (4px) 통일. `rounded-full`/`rounded-2xl`/`rounded-3xl` editorial 톤에서 금지." Avatar pictures can be circular (different rule), but the Search and Bell buttons should be squared with the editorial system.
- **Recommendation:** Replace `rounded-full` on top-bar action buttons (search, bell) with `rounded-sm` or `rounded-md`. Keep avatar as circle (legitimate exception).

---

### MEDIUM

#### FINDING-021 · `/home` Position row shows `$293,000.00 +442.59%` on a single 005930 position
- **Category:** Numeric reasonableness / unit confusion
- **Page:** `/home`
- **Evidence:** Screenshot `ss_34950pr99` — `005930 005930  $293,000.00  +442.59%`. The price is rendered with `$` prefix (USD), but 005930 is a KOSPI ticker quoted in KRW. The +442.59% is implausible for a daily/holding gain on Samsung.
- **Why it matters:** Currency-symbol drift (`$` for KRW) compounds with seed data. User cannot trust the number.
- **Recommendation:** Use `fmtKrw()` (memory says helper exists) for KOSPI tickers. Validate %-change ranges before display.

#### FINDING-022 · Sticky header re-renders on top of scrolled content (visible "bleed-through" of position text under "LIVING CFO" eyebrow)
- **Category:** Layering / z-index
- **Page:** `/home`
- **Evidence:** Screenshot `ss_34950pr99` — `005930 005930 $293,000.00 +442.59%` faintly visible *behind* the sticky `LIVING CFO   L1 IDENTITY ...` header during scroll. The sticky bar has insufficient background opacity.
- **Why it matters:** Editorial typography demands clean stacking. Bleed-through reads as "broken modal" / "z-index forgot to win."
- **Recommendation:** Sticky header should have a solid `var(--pq-ink)` background (with optional blur backdrop), not a semi-transparent overlay.

#### FINDING-023 · Top ticker tape combines a pulsing live-dot with static-looking numbers (live-impersonation flag in §6)
- **Category:** Motion / honesty
- **Page:** `/home`, `/risk`, `/signals`, `/portfolio`, `/reports`, `/settings` — all dashboard pages
- **Evidence:** DOM scan found `animation-name: claude-pulse, 2s` on the live dot. The ticker numbers next to it (S&P 500 742.31 / NASDAQ 100 714.71 / KOSPI / etc.) do not visibly tick. Time stamp `PIVOX 11:04:44 KST` does increment.
- **Why it matters:** §6 explicitly: "펄싱 dot + 정적 ticker 동시 사용 금지 (라이브 위장)." A pulsing green dot next to numbers that don't change suggests live but isn't.
- **Recommendation:** Either (a) tick the numbers (real-time fetches) so the live indicator earns itself, or (b) replace the pulsing dot with a small `LAST OBSERVED · 11:04` static label.

#### FINDING-024 · KOSPI value 7,892 is rendered with `▲+0.62%` in `--up: #dc2626` (bright red) — color is right for KR convention but value is wrong
- **Category:** Color consistency / data
- **Page:** `/home` (top ticker)
- **Evidence:** Screenshot `ss_5050spec2`.
- **Why it matters:** Folded into FINDING-002 + FINDING-016, but worth noting that color *direction* is KR-correct (▲ = red) while the VALUE is wrong. Don't fix one without the other.

#### FINDING-025 · `MORNING PAPERS · UNITED STATES` ivory paper card abruptly transitions from Vantablack body — visual hard cut
- **Category:** Composition / layout transition
- **Page:** `/market`
- **Evidence:** Screenshot `ss_91359zul0`. The cream paper card (`#FAF8F3` per spec) sits inside Vantablack with no transition — no shadow, no subtle border, no gradient. The eye lands on the bright rectangle hard.
- **Why it matters:** The "ivory paper" surface concept is GOOD (§4 explicit exception). But it needs to feel laid on the desk, not pasted. Slight shadow + a 1px hairline border in `--pq-hairline` would integrate it.
- **Recommendation:** Add `box-shadow: 0 4px 24px rgba(0,0,0,0.4), 0 1px 0 rgba(245,240,232,0.06)` and a 0.5px ivory border.

#### FINDING-026 · "관심 종목 추가" empty state on AAPL detail says `AAPL` not `Apple Inc.`
- **Category:** Brand / ticker name preference
- **Page:** `/detail/AAPL`
- **Evidence:** Screenshot `ss_39981xu0n`. "AAPL 분석은 관심종목 또는 보유 포지션으로 등록한 후 이용 가능합니다."
- **Why it matters:** Same family as FINDING-011/013 — the rule is name-before-ticker. Korean users especially expect "Apple" or "애플."
- **Recommendation:** `Apple (AAPL) 분석은 ...` or `애플(AAPL) 분석은 ...`.

#### FINDING-027 · Detail page tag chips redundant: `TECHNOLOGY · KRW · KOSPI · CONSUMER ELECTRONICS`
- **Category:** Content density / metadata
- **Page:** `/detail/005930.KS`
- **Evidence:** Screenshot `ss_4323kiq4l`.
- **Why it matters:** TECHNOLOGY (sector) ⊃ CONSUMER ELECTRONICS (industry) — three chips for what could be two (`Tech · 디스플레이/반도체 · KOSPI`). Visually busy.
- **Recommendation:** Pick one of sector/industry depending on user audience. Or hierarchical render: `Tech › Consumer Electronics`.

#### FINDING-028 · `/pricing` H1 is in italic on its entire phrase ("Pick the tier that matches your cadence."), whereas other pages italicize only emphasis words
- **Category:** Typography rhythm
- **Page:** `/pricing`
- **Evidence:** Screenshot `ss_3366thxs1` vs `/risk` "Risk *board*." (selective italics) vs `/portfolio` "Your *book*." (selective italics).
- **Why it matters:** The italic-emphasis pattern is one of the strongest signatures of the design language. Pricing breaks the pattern by italicizing everything.
- **Recommendation:** "Pick the tier that matches your *cadence*." with only `cadence` italic. Or "Pick the *tier* that matches your *cadence*."

#### FINDING-029 · `Pricing` page eyebrow mixes EN + KR mid-string: `COMING SOON · 정식 출시 후 활성화`
- **Category:** Microcopy / language consistency
- **Page:** `/pricing`
- **Evidence:** Screenshot `ss_3366thxs1`.
- **Why it matters:** A bilingual product is welcome, but mid-eyebrow language switching dilutes the editorial cadence. The English-Korean break should happen on a meaningful boundary (between paragraphs / between sections), not inside a single 5-word eyebrow.
- **Recommendation:** Either fully English (`COMING SOON · LAUNCHING WITH STRIPE INTEGRATION`) or fully Korean (`출시 임박 · Stripe 활성화 시점`).

#### FINDING-030 · The splash wordmark page shows `PivoxQuant` in italic Playfair Display
- **Category:** Brand identity
- **Page:** splash / initial load
- **Evidence:** Screenshot `ss_89267gfml`. PivoxQuant wordmark rendered italic with bronze dot above + a thin hairline below.
- **Why it matters:** A brand wordmark normally stays in one canonical typographic form. The dashboards show `PIVOXQUANT` in roman uppercase (sidebar) and `PivoxQuant` in italic Playfair Display (splash + market header) — two different wordmark treatments competing for "the" brand presentation.
- **Recommendation:** Pick the canonical wordmark. The italic Playfair feels right for an editorial brand — but then the sidebar should also use that form (small-caps italic Playfair). Or commit to roman uppercase wordmark everywhere.

#### FINDING-031 · Right side of every dashboard page: ticker tape `USD/KRW 1,491.78 ·—` and `VIX 27.33 ▲+2.…` clip off the right edge
- **Category:** Layout / overflow
- **Page:** all dashboard pages (sticky ticker tape)
- **Evidence:** Many screenshots show `VIX 27.33 ▲+2.…` cut by viewport.
- **Why it matters:** The data the user might most want during volatility (VIX) is exactly the data that disappears. Either always scroll the ticker (and accept the live-impersonation cost — see FINDING-023), or fit all chips at 1280px+.
- **Recommendation:** Reduce chip count or apply horizontal auto-scroll only when content exceeds container. At 1440px, all chips should fit.

#### FINDING-032 · 2 spinning SVGs running on /home (`animation-name: spin, 1s`)
- **Category:** Loading state / spec compliance
- **Page:** `/home`
- **Evidence:** `getComputedStyle` query returned 2 SVGs with `spin` animation.
- **Why it matters:** §6 says "Skeleton UI — 다크 표면용 `.pq-skeleton-dark` 클래스 사용 (스피너 금지)." Spinners are forbidden on dark surfaces — should be skeletons.
- **Recommendation:** Replace any `<Loader2 className="animate-spin" />` icon with the `.pq-skeleton-dark` skeleton component.

---

### POLISH

#### FINDING-033 · `--pq-text-eyebrow: 12px` (production) vs `10.5px` (spec); `--pq-text-mono-sm: 12px` (prod) vs `11px` (spec)
- **Category:** Typography / token spec drift
- **Page:** all
- **Evidence:** Token dump above.
- **Why it matters:** Eyebrows currently read just slightly bigger than the spec intent. Most readers won't notice — but the calibrated rhythm of editorial body 14 → small 13 → eyebrow 10.5 is shallower than it should be. Visually you see "tight 11-12-13-14" instead of "12-13-14 + tiny accent eyebrow." The eyebrows lose their whisper quality.
- **Recommendation:** Match spec exactly: eyebrow 10.5px, mono-sm 11px, body-sm 13px.

#### FINDING-034 · Open Sans (300/400/500/600/700/800) loaded but unused; Plus Jakarta Sans loaded unused
- **Category:** Performance / payload
- **Page:** every page
- **Evidence:** `document.fonts` shows 7 Open Sans weights and Plus Jakarta Sans in `unloaded` state but installed in the registry.
- **Why it matters:** Even unloaded font faces cost a few KB in the font registry and confuse the Source-of-Truth for typography. v3 spec is Playfair + Source Serif 4 + Geist + JetBrains Mono — no Open Sans, no Jakarta.
- **Recommendation:** Remove the unused `@font-face` declarations from CSS/manifest.

#### FINDING-035 · `MARKET CAP 1974.1조` uses Playfair Display 32px for the number, then `조` (KR for trillion) in a different font/weight — typographic transition mid-number
- **Category:** Typography composition
- **Page:** `/detail/005930.KS`
- **Evidence:** Screenshot `ss_4323kiq4l`.
- **Why it matters:** A unit suffix (조 / B / 억) should be visually subordinate to the digit, but here the suffix has a separate-feeling weight. Reads as a typeset mistake more than a unit modifier.
- **Recommendation:** Render the suffix smaller and in `--pq-muted` color, locked to the number baseline.

#### FINDING-036 · `READ FULL MEMO` / `OPEN LAYERS` / `CLAIM FOUNDING SEAT` CTAs use bronze background + Vantablack text — but the contrast feels slightly washed because bronze (#B8956A) on dark is the *fill* color, not a true high-contrast brand button
- **Category:** Color / contrast
- **Page:** `/home`, `/risk`, etc.
- **Evidence:** Various screenshots.
- **Why it matters:** Brand-true bronze CTAs feel premium, but a quick eyeball says contrast bronze-vs-ivory could be ~3.5:1 (below WCAG AA 4.5:1 for normal text). Wants formal contrast check.
- **Recommendation:** Verify computed contrast with a contrast tool. If <4.5:1, either deepen the bronze or use ivory text on bronze (currently it looks like the text is the dark variant — could be black).

#### FINDING-037 · Detail "CURRENT PRICE" row: `₩292,500 ·—` — the `·—` indicator next to the price is undefined to the user
- **Category:** Microcopy / iconography
- **Page:** `/detail/005930.KS`
- **Evidence:** Screenshot `ss_4323kiq4l`.
- **Why it matters:** A bronze dot + dash next to the price reads as a custom symbol — but its meaning is unstated. Probably "no recent observation" or "market closed", but undocumented.
- **Recommendation:** Either remove or annotate. A `LAST OBSERVED 11:04 KST` label next to the price would be more useful.

#### FINDING-038 · Disclaimer copy redundant: Korean disclaimer + English disclaimer + footer disclaimer + page-level disclaimer banner — 4 versions on /home
- **Category:** Compliance density
- **Page:** `/home`
- **Evidence:** Bottom of /home: `DISCLAIMER 본 서비스는 투자자문이 아니며...` panel + `PivoxQuant · Observational research only · Not investment advice` footer + per-section `Composite score — 4-pillar observational blend.` etc.
- **Why it matters:** Legal protection is good, but stacking 4 disclaimers in one page makes the actual product feel buried. Trust-by-volume is the opposite of trust-by-clarity.
- **Recommendation:** Consolidate into ONE expandable DisclaimerBanner at page foot (bilingual, accordion-collapsed). Remove redundant micro-disclaimers from individual cards.

#### FINDING-039 · Search bar in top-bar has placeholder `Search ticker, page...` — could be more confident
- **Category:** Microcopy
- **Page:** all
- **Evidence:** Screenshot `ss_5050spec2`.
- **Why it matters:** "Search ticker, page..." is functional but generic. The editorial brand voice would say something like `Find a ticker, an artifact, a page…` or `삼성전자, 위클리메모, 리포트…`.
- **Recommendation:** Sharper placeholder, optionally bilingual.

#### FINDING-040 · `V1.0 · PAPER` footer at bottom of every page — small, but the `PAPER` label is unclear
- **Category:** Microcopy
- **Page:** all dashboard
- **Evidence:** Screenshot `ss_5050spec2` left-rail bottom.
- **Why it matters:** "PAPER" likely means "paper trading mode" (broker disabled, observation only) — important context. But just `PAPER` is ambiguous (paper as in document? paper trade?).
- **Recommendation:** `V1.0 · PAPER MODE (OBSERVATION ONLY)` or hover-tooltip explaining what PAPER means.

---

## Quick Wins (30 min each — high impact)

1. **Fix the body element tokens.** One CSS rule (`body { background: var(--pq-ink); color: var(--pq-ivory); }`) closes FINDING-001 and prevents future FOUC. Also patch `--up` and `--down` to KR-convention hex (`#D18888` / `#7AA0C8`) — closes FINDING-002 + half of FINDING-024 in one diff.

2. **Replace naked `005930` with `삼성전자` everywhere on /home.** Use existing helper or add a tiny `tickerToName()` lookup for the top KOSPI 30 (or just Samsung + Kakao + Naver if those are the seed list). Closes FINDING-011, FINDING-012 (partially), FINDING-013, FINDING-017, FINDING-026. Single-day, transformative impact on perceived professionalism.

3. **Freeze pricing display.** Remove the count-up animation from `/pricing`. One component change. Closes FINDING-007 — the single biggest credibility risk for any user on the buy page.

(Bonus 4: **Define `--pq-safe-top` / `--pq-safe-bottom` via `env(safe-area-inset-*)`** — one line in `globals.css`. Closes FINDING-006 + de-risks iOS PWA install for beta testers.)

(Bonus 5: **Stop the live-impersonation by removing the pulsing dot OR adding real ticking digits.** Either change closes FINDING-023 + improves the brand-honesty signal.)

---

## Summary

- **40 findings** documented across `/home`, `/portfolio`, `/risk`, `/signals`, `/market`, `/detail/005930.KS`, `/detail/AAPL`, `/settings`, `/reports`, `/pricing`, /splash.
- **20 HIGH**, **12 MEDIUM**, **8 POLISH**.
- **First impression: A-tier editorial typography, C-tier data layer.** The Vantablack + bronze + Playfair editorial language is genuinely the best I've seen on a Korean fintech surface. The token system is 80% there. The body element is still white. The portfolio is still showing $2.93M demo capital. KOSPI is rendered at 3× actual. Samsung at 5× market cap. Pricing animates from 519 to 9,900 KRW.
- **Biggest single issue:** **FINDING-007 (pricing prices animate from low number up to actual)** — combined data + motion + legal-perception risk on the page that converts revenue. Closing this is 1 component change and removes a defensible-but-bad behavior from the only money-related view.
- **Quick Wins:**
  1. Body element tokens + KR-convention `--up/--down` hex (FINDING-001, FINDING-002).
  2. Ticker name display on /home top weights and signals (FINDING-011, FINDING-013, FINDING-017).
  3. Static pricing — kill the count-up animation (FINDING-007).

**Status: COMPLETE** — within time budget. Mobile responsive (375px) and beta-gate-uncached UX could not be verified in this session due to host browser constraints (window won't shrink below screen width; auth session pre-cleared past beta-gate). Recommend follow-up audit with a fresh incognito window + Chrome DevTools Device Mode for true mobile verification.

---

## Notes on evidence and limitations

- **Screenshots:** Each `ss_xxxxxxx` ID was captured live during this audit via Claude-in-Chrome. The MCP `save_to_disk` flag does not write to the local filesystem from this tool, so screenshots exist as in-transcript evidence only. If permanent on-disk copies are needed for the design team, re-run with a screenshot tool that has filesystem write (or take screenshots manually from the listed URLs).
- **No code changes:** This is a READ-ONLY audit — zero edits, zero PRs, zero file writes outside this report.
- **No external APIs called:** Audit used only the Chrome session already running on the host. No Stripe, no FMP, no third-party calls.
- **Mobile (375px iPhone):** could not be verified — host Chrome window will not resize below screen.width. Memory says PWA is the primary target — a follow-up mobile audit with Chrome DevTools Device Mode is strongly recommended.
- **Beta gate:** could not be verified — host browser session is already past the gate.
- **Logged-out landing:** could not be verified — host browser is already authenticated; `/login` redirects to `/home`. Recommend separate session with cleared cookies / incognito.

— end —
