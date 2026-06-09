# Structural Consolidation — 2026-06-09 (CEO: "구조 제대로 싹다 잡으라")

> Greenlight to execute the large structural consolidations deferred in the
> 2026-06-08 bug-hunt (money/legal-touching, so previously documented-not-applied).
> Method: 2 read-only inventory agents (ticker, disclaimer) → **lead re-verified
> every site by reading code (실측, not agent's word)** → behavior-preserving only,
> per-cluster commit with full test verification → frozen files (services/quant/*,
> ai/models) never touched.
>
> The 4 candidate clusters and their outcome:

| Cluster | Outcome | Commit |
|---|---|---|
| fx `_fx_rate` (7 copies) | ✅ consolidated | `19fbc170` |
| `is_korean_ticker` (7 redefinitions) | ✅ consolidated | `c9f20ed7` |
| disclaimer text (16 copies) | ✅ consolidated | `cc861ac1` |
| **`_safe_price` (5 copies)** — the real dup in the "positions" area | ✅ consolidated (found when CEO told me to re-examine — see §4) | `9cb5dabf` |
| **`_try_import_weasyprint`/`_try_import_jinja` (32 copies/18 files)** | ✅ consolidated (found via a full cross-file dup scan — see §5) | `8c5eb1ad` |
| positions **query** (~30 sites) | ⛔ correctly NOT consolidated — context-specific, not duplication | — |

---

## 1. fx spot-rate — 7 copies → `fx_service.spot_usdkrw()` ✅
7 artifact services each had a **byte-identical** private `_fx_rate()` ( `>=900`
sanity guard + `1380` fallback) — the "fix one copy, miss the others" hazard,
with the fallback constant duplicated 7×. Added `fx_service.spot_usdkrw()` (uses
the existing `FALLBACK_USDKRW`) as the single SoT; the 7 wrappers now delegate.
- **Behavior**: identical (logic moved verbatim). Call sites unchanged.
- **Frozen left as-is** (documented): `engine.py` (1350) + `ai/models.py` are
  Iron-Rule frozen, so their fallback constants stay — only the non-frozen
  artifact side is unified. The 1380-vs-1350 split is now frozen-bound, not drift.
- **Verified**: `spot_usdkrw` unit-check (sane / <900 / 0 paths) + 251 artifact/fx tests.

## 2. is_korean_ticker — 7 private redefinitions → canonical ✅
`name_resolver._is_korean`, `nav_snapshot._is_kr`, `capital_gains._is_kr_ticker`,
`burn_rate._is_kr`, `weekly_memo._is_kr_ticker`, `counterfactual._is_korean`,
`DataFetcher.is_korean` each re-implemented `.upper().endswith((".KS",".KQ"))` —
the drift-risk class behind past KOSDAQ `.KS` misroutes. All now delegate to
`services.ticker_normalizer.is_korean_ticker`.
- **Verified behavior-identical** for every input (.KS/.KQ any case, US, bare
  6-digit, empty, None) by direct comparison vs the canonical; delegation is also
  more robust (canonical is null-safe where 2 old copies raised on None).
- **Scope = redefinitions only.** Inline `.endswith((.KS,.KQ))` idioms (~60),
  currency-based checks, bare-6-digit matchers, and normalize/suffix-strip ops
  were intentionally left (different semantics — see §5). Frozen `quant/*` untouched.
- **Verified**: 192 KR-routing/ticker/affected-service tests.

## 3. disclaimer text — 16 byte-identical copies → `services/legal/disclaimers.py` ✅
Four legal disclaimers were copy-pasted byte-identically across 16 surfaces — a
real compliance hazard (a lawyer wording change had to hit every copy or ship
inconsistent legal text). New `services/legal/disclaimers.py` (imports nothing →
no cycle risk) holds them once; adopted at all 16 with **ZERO wording change**:
- `DISCLAIMER_ARTIFACT_KR` (risk_board/self_audit/dd_checklist/kpi_dashboard/
  portfolio_segment + year_end/quarterly split-concat),
- `DISCLAIMER_ARTIFACT_BILINGUAL` (earnings_prebrief, weekly_memo),
- `DISCLAIMER_BRAG_BILINGUAL` (brag_card, monthly_brag),
- `DISCLAIMER_MIRROR_RETROSPECTIVE_KR` (behavior holding/profit-loss/turnover/
  averaging-down + profile activity — the recognized drift risk).
- **Left separate (legitimately different)**: tax / investment / sector /
  paper-twin / persona-drift / present-holdings concentration / `sample_data`
  fixtures / frozen `quant/portfolio.py`. NOT merged.
- **Safety**: `tests/test_disclaimer_sot.py` pins each constant's EXACT text (a
  typo in the SoT would otherwise silently change legal text everywhere).
- **Verified**: lock test + 669 artifact/legal/behavior tests. Zero text change.

## 4. positions / pricing area — re-examined on CEO push; found + fixed the real dup ✅⛔
**First pass I got this wrong.** I looked at the `Position.query.filter_by(...)`
*query line*, saw it followed by different logic, and dismissed the whole cluster
as "not duplication." The CEO said *"positions loader 이 부분 파악해봐 제대로"* — and
he was right. The duplication wasn't the query; it was the **price-fetch + market-
value logic that follows it.**

Re-examining ALL 14 `.all()` sites surfaced the genuine debt: **five
byte-identical `_safe_price(ticker)` helpers** (year_end_letter, risk_board,
quarterly_self_report, monthly_finance, kpi_dashboard) — `fetch 5d history → last
close → math.isfinite guard → None`. That is precisely why the 2026-06-07
`$nan`-in-paid-PDF fix had to be applied in 7 separate places. **Consolidated**
into `services/artifacts/_pricing.py::safe_last_price` (`9cb5dabf`).

What is **correctly NOT consolidated** (verified context-specific, not duplication):
- The `Position.query.filter_by(user_id=…)` line itself — ~10 are `.count()`
  existence checks, the `.all()` sites each feed different logic with raw
  `Position` objects. It is already the simplest form; no helper helps.
- `routes/quant_helpers._load_positions_with_prices` — NOT a generic loader; it
  batch-loads SignalCache prices and returns **KRW-normalized enriched dicts**
  for risk analytics (the currency-merge the CEO said to leave —
  [[feedback_currency_separate]]). Forcing artifacts through it would change the
  return shape + add the currency normalization — a behavior change for no gain.
- `weekly_memo._ticker_last_price` (fmp.get_quote multi-key + history fallback)
  and `portfolio_segment._safe_price_at` (date-window `(start,end)` tuple) —
  single distinct functions, not duplicates.

**Lesson**: a static "duplication" flag on a query line can hide the real dup one
layer down (the computation), and can also be a false positive. The CEO's push to
look properly turned a wrong "skip it" into a real money-math consolidation.

## 5. weasyprint / jinja import helpers — 32 copies → `services/artifacts/_render.py` ✅
After the `_safe_price` miss, I ran a **full cross-file duplicate scan** (md5 of
every function body across `services/`) to make sure nothing else was hiding.
Biggest remaining dup: the optional-render import helpers, copy-pasted across 18
artifact builders — `_try_import_weasyprint` (14 copies) + `_try_import_jinja`
(18 copies) = **32 functions**, differing only in log wording/level.
- New `services/artifacts/_render.py::try_import_weasyprint / try_import_jinja`;
  all 18 files import them as the old private names (call sites unchanged).
- Behavior-identical (import logic was byte-identical); log level normalised to
  WARNING — the level `weekly_memo` had already deliberately bumped to.
- −228 net lines. AST-based removal (handled all variant bodies uniformly).
- The scan also confirmed the post-consolidation `_fx_rate`/`_is_kr` "2-copy"
  hits are now thin delegators to the SoT (expected, not debt), and `_safe_history`
  is mostly context-specific (different periods/return shapes) — left as-is.

## 6. Not done & why (transparency)
- **Inline `is_korean_ticker` idiom (~60 `.endswith((.KS,.KQ))`)** — a working,
  consistent idiom, NOT drift-risk debt (unlike the 7 redefinitions, which are
  fixed). Canonical exists + SAFE-list mapped → clean mechanical follow-up; not
  worth a 60-site sweep across money/routing code for an idiom.
- **Frozen `services/quant/*` + `ai/models.py`** — Iron Rule §1, never touched.
- **Currency KRW/USD raw-mixing** + the per-position market-value loop
  (`year_end`/`quarterly` closing-value) — CEO decision: leave the currency path.

## 7. Verification
- Each cluster: targeted tests green before commit (251 / 192 / 669 / 163 / render-aliases).
- Combined: one clean full backend suite over all 5 clusters (final gate).
  `frontend` untouched this round (backend-only edits).
- Commits: `19fbc170` (fx) · `c9f20ed7` (ticker) · `cc861ac1` (disclaimer) ·
  `9cb5dabf` (_safe_price) · `8c5eb1ad` (render). Not pushed (feature branch).
