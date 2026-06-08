# Overnight Bug Hunt — 2026-06-08 (Session 3, autonomous)

> CEO: "나 자는동안 버그헌팅이랑 구조 다 잡아놔라 … 자율모드로." Method: lock baseline →
> 6 parallel hunting lanes (background agents) + lead deep-dive on 2 high-value lanes the
> agents wouldn't reach → **lead re-verifies every finding by reading code + running repros**
> (v58 verify-gap lesson) → fix only SAFE + non-frozen, **document money-math / legal / frozen /
> prod-ops / large-refactor** (v57–v60 discipline). No browser (CEO session absent) → static +
> prod-API + test hunting. Separate from session 1/2 (`overnight_bug_hunt_2026-06-07*.md`).
>
> **Baseline**: this run EXPOSED that the prior "green" claim was masking 4 order-dependent
> failures (see Applied #2). After fixes: see PART 4.

---

## PART 1 — APPLIED fixes (verified, committed to `feat/data-storage-trust`, **push 안 함**)

### 1. JSON serialization safety net — non-finite floats → `null` (SYSTEMIC, structure) ✅
- **Root cause**: Flask's `DefaultJSONProvider` (stdlib `json`) emits the bare tokens
  `NaN` / `Infinity` / `-Infinity`, which are **invalid JSON**. A browser `response.json()`
  rejects them → the *entire* payload is lost (silent blank/error card despite HTTP 200).
  Empirically confirmed: `jsonify({"x": float('nan')})` → `{"x":NaN}` → strict-parse FAIL.
- **Why structural**: **74 `isfinite/isnan` guards across 25 files** + `_finite_floats`
  re-implemented per-route — the canonical helper's own docstring says *"Run the final payload
  through this before jsonify so a single missed guard can never ship a non-parseable response"*,
  yet it's wired into only ~9 of 40+ route modules. Whack-a-mole.
- **Fix**: new `services/json_provider.py::SafeJSONProvider` coerces non-finite floats → `null`
  at the serialisation boundary; wired in `app.create_app` (`app.json = SafeJSONProvider(app)`).
  Non-destructive (returns the *same* object on the all-finite common path → no realloc, never
  mutates cached payloads). `null` not `0.0` — honest "no data" sentinel, avoids fabricating a
  financial zero (표시광고법 false-display). The 74 upstream guards still run → defense-in-depth.
- **Verify**: new `tests/test_json_provider_nan.py` (7 tests) — scalars/nested/tuple/identity/
  no-mutation/strict-parse/wiring-lock; all green. End-to-end through `create_app()` confirmed.

### 2. Flaky test isolation — `test_data_status_endpoint` cross-test pollution ✅
- **Root cause**: `services.container.realtime` is a process-wide singleton. A test that drives
  its KR feed into failure (singleton `get_price` on a KR ticker w/ stubbed-down fetch) sets
  `_kr_last_fail = now` via `_record_kr_health`. `kr_health().degraded` then stays True for 120 s,
  and `routes/data_status.py`'s live overlay turns that into a forced `is_stale=True`. → The 4
  `*_returns_not_stale` cases fail **only in full-suite order** (the one expecting `True` + the
  type-only tests pass — exactly the observed pattern). The prior handover's "baseline green
  3833" was masking this; **the full suite was actually 4-failed**.
- **Fix**: autouse fixture `_reset_realtime_kr_health` in `tests/conftest.py` resets the
  singleton's transient KR-health timestamps before each test. Kills the entire flakiness class
  for **every** consumer, not just these 4.
- **Verify**: pollution probe (set `_kr_last_fail`, assert degraded) run immediately before the
  data_status tests → all 8 green (fixture isolates). Probe removed.

### 3. PIPA §21 erasure gap — `anthropic_usage_log` orphaned PII (P1) ✅
- **Root cause** (migration-guard agent, **live prod read-only introspection**): the table has a
  `user_id` column but **no ORM model** and **no users FK on prod** (migration 042 declares the FK
  but never ran — prod alembic is stuck at 032, see PART 2 P0; the app.py self-heal `CREATE TABLE`
  owns the live schema and omits the FK). So **both** erasure paths miss it: the explicit ORM
  purge list (no model) and the FK-driven dynamic sweep (no users FK). → A deleted user's
  per-user API-usage rows survive = orphaned PII.
- **Fix**: model-less allowlist sweep added to **both** `routes/auth.py::delete_account` and
  `scripts/nightly/pipa_purge._delete_user_cascade`. SAVEPOINT-isolated (can never block the
  user-row delete) + **allowlist-only** (`("anthropic_usage_log",)`) so the deliberately-retained
  `funnel_events` analytics snapshot is never touched.
- **Verify**: new `test_delete_account_purges_modelless_fkless_user_id_table` — creates the
  FK-less table w/ rows for 2 users, deletes account, asserts target's PII purged + other user's
  rows survive + table survives. Green. All 24 deletion/purge tests still pass.

### 4. CFO Weekly-Pulse localStorage shape crash (P2, frontend) ✅
- **Root cause**: `lib/cfo/hooks.ts` `safeRead` does an unvalidated `JSON.parse`. A stale /
  older-schema `pq_cfo_pulse_v1` (e.g. `{}` with no `history[]`) seeds `fallbackData` / `swr.data`,
  then `submit`'s `[...current.history]` throws → uncaught → toast/ErrorBoundary. **Same corruption
  class** that already shipped a SHIP-BLOCKER: `living-cfo-status.tsx` was patched at ONE consumer,
  but the hook root cause was never fixed (other consumers — `profile/_v2:450`, `submit` — stayed
  exposed).
- **Fix**: `coercePulse()` validates `Array.isArray(history)` at both `fallbackData` and `submit`'s
  `current` (matches the `Array.isArray` convention already used at the patched consumer).
- **Verify**: tsc 0, vitest 545.

### 5. Dead-code deletes (structure) ✅
- `services/cache_service.py` — `ca_cache: dict = {}` global with **zero** readers/writers (the
  real cross-asset cache is `routes/strategy_quant.py::_ca_cache`, a different object). Deleted.
- `services/data/fmp.py` — `normalize_ticker()`: **dead** (no internal use, no importers) **and a
  footgun** (same name as the canonical `ticker_normalizer.normalize_ticker` but *opposite*
  semantics — returns `None` for KR). Deleted (better than rename — removes the collision).

### 6. Notification dropdown double-submit guard (P3, frontend) ✅
- `components/ui/notification-dropdown.tsx` `markAllRead` had no in-flight guard (rapid double-tap
  → 2 POSTs; idempotent server-side so harmless, but inconsistent). Added `markingRead` state +
  `disabled` — parity with the already-guarded `/alerts` page.

---

## PART 2 — DOCUMENTED (NOT auto-applied — CEO / ops / lawyer / large-refactor)

### 🔴 Prod / ops — escalate (irreversible prod op, NOT autonomous)
- **[P0] prod `alembic_version` stuck at 032 vs code head 048** (migration agent, live prod).
  **Mitigated**: prod schema IS current via the `app.py::_do_migrations` self-heal (model-vs-prod
  column parity passed live); `flask db upgrade` runs best-effort non-fatal and has never advanced
  past 032 because early `create_table` migrations (003/004/005/007…) aren't idempotent. **Why
  still P0**: alembic is no longer the real migrator → single point of failure on the hand-maintained
  self-heal. This is the exact 2026-05-17 v44.7 OAuth `provisioning_failed` incident class. **Fix
  (ops)**: make early create_table migrations idempotent, then `flask db stamp 048` on prod; alert
  on `flask db upgrade` failure instead of swallowing. **Not done autonomously — touching prod
  alembic state is irreversible + outward-facing.**

### 🟠 Money-math / legal — consolidate deliberately (CEO discipline: don't churn overnight)
> Structure agent's headline: *"the canonical helpers already exist — adoption is the gap, not
> architecture."* The risk is the "fix one copy, miss the others" hazard that already bit money/ticker.
- **`_fx_rate()` — 9 byte-identical copies** in `services/artifacts/*` (all already delegate to
  `fx_service.get_rate()`, so consolidation is behavior-preserving) + **two divergent fallback
  constants**: `1380` (artifacts/`fx_service`) vs `1350` (`quant/engine.py` [FROZEN], `ai/models.py`).
  → route all through `fx_service`. Blast radius = 9 paid-PDF files → do with full artifact test.
- **KR disclaimer text — ≥8 divergent wordings** across `legal_filter` / `ai/*` / `quant/portfolio`
  / `tax/capital_gains` / `artifacts/sample_data` / `profile/persona_history`. **Legal/audit risk**:
  a lawyer-mandated phrasing change can't be made in one place. → one `DISCLAIMER_KR/EN` constant
  (legal_filter as SoT).
- **`is_korean_ticker` — 48 inline `.endswith((".KS",".KQ"))` + 7 private redefinitions**
  (`canslim`, `burn_rate`, `weekly_memo`, `capital_gains`, `nav_snapshot`, `performance_quant`,
  `quant_helpers`). The exact KOSDAQ `.KS` misroute class. → adopt `ticker_normalizer.is_korean_ticker`.
- **Positions loader — ~30 inline `Position.query.filter_by(user_id=…)` re-queries** across artifact
  services (a filter change e.g. exclude-closed misses most). → `_load_positions_with_prices`.
- **Currency KRW/USD raw-mixing** — **CEO already decided: LEAVE IT** ([[feedback_currency_separate]]
  "krw usd 냅두라 몇번말하노"). Enumerated set unchanged: F1 `simulate.py` ×5, F2 `credit_rating`,
  B2 `twin`, B3 `portfolio_analytics`. **NEVER FX-convert to merge** — bucket-by-currency or exclude KR.

### 🟡 Low-priority hygiene (safe but deferred — owner judgment)
- **`pykrx_service` deprecated stub wired to LIVE routes** `/api/alt-data/kr/*`
  (foreign_flow/short_interest/market_flow) → always returns empty `data` → permanently-empty KR
  alt-data widgets. **Product decision**: hide FE widgets or finish the KIS replacement.
- **Migrations not SQLite-replayable**: 004/005 unconditional `postgresql.JSONB()`; 016/017/018/019
  `BigInteger` PK autoincrement (the 2026-04-25 incident pattern). Latent only (prod=PG, tests=
  `create_all`); **models are SQLite-safe**, only the migration files are wrong → bites CI-fidelity /
  local `flask db upgrade`. Fix = `JSONB().with_variant(JSON(),"sqlite")` / `BigInteger().with_variant
  (Integer,"sqlite")` (pattern 045 already does this correctly).
- **`dart_corp_code.load_mapping`** holds `threading.Lock` across a 30 s ZIP download (P3,
  gevent-mitigated cold-path). Recipe: download outside lock → double-checked publish under lock.
- **Uncapped module caches** `dart_insider._cache` / `ai/models._cache` — TTL but no hard entry cap
  (slow, ticker-universe-bounded drift). Add the FIFO cap `fmp._set_cache` uses.
- **`morning_briefs` + post-029 user-FK tables** rely solely on the runtime dynamic sweep (no
  DB-level cascade). Add `ON DELETE CASCADE` for defense-in-depth.
- **`lib/hooks.ts::useMethodology`** — dead (zero callers). Left in place: frontend CLAUDE.md guards
  hooks.ts; remove deliberately with the `METHODOLOGY`/`MethodologyResponse` import cleanup.
- **`.env.example` undocumented `*_ENABLED` flags** (verified defaults): `AI_CHAT_ENABLED=0`,
  `STRIPE_ENABLED=` (unset→off), `SUPPORT_CHAT_LLM_ENABLED=0`, `PIVOX_CS1_CONSENT_ENABLED=false`,
  `KR_INDEX_KIS_ENABLED=1`. **Left untouched — `.env.example` already has uncommitted WIP**; add
  alongside that edit.
- **`settings/_v2` `.then(setState)`** with no mounted guard (P3 — cosmetic unmount console noise).

### 🔒 Frozen (Iron Rule §1 — CEO approval, not investigated)
- quant degenerate-input crashes (StatArb std0 / portfolio cummax NaN / AnchoringBias 0-price /
  GKYZ log0) — documented by prior sessions; out of scope per constraints. The new JSON provider
  (Applied #1) incidentally turns any *leaked* non-finite from these into `null` rather than a
  broken response, but does **not** fix the underlying degenerate-input handling.

---

## PART 3 — CLEAN (evidence-based, 6 lanes + lead)
| Lane | Scope | Verdict |
|------|-------|---------|
| **Write-path** (agent) | 128 POST/PUT/PATCH/DELETE handlers — IDOR/validation/mass-assignment/race | **ZERO findings.** Every user-owned mutation enforces `user_id==current_user.id`; inputs validated; admin fails-closed; races guarded with row locks + UNIQUE. Exceptionally hardened. |
| **Concurrency** (agent) | db.session lifecycle, locks, scheduler, SSE, KIS self-heal | **No P0/P1.** EGW02004 self-heal race correctly bounded (depth-2, once-only domain flip); token-manager double-checked locking correct; scheduler `max_instances=1`+`coalesce`. 4× P3 (see PART 2). |
| **Exception safety** (agent) | silent-swallow / uncaught-500 / envelope / partial-external | **CLEAN.** Framework `@errorhandler(Exception)` converts all uncaught `/api/*` → JSON 500 (no stack leak, no HTML-into-`.json()`); all user int/float guarded → 400; every external-data subscript length/None-guarded. |
| **Frontend runtime** (agent) | effect cleanup / stale closures / async-after-unmount / double-submit / SWR keys / NaN→screen | SSE teardown, timers/observers cleanup, mutation guards, `format.ts` NaN guards all present. 1 P2 (fixed #4), 2 P3 (1 fixed #6, 1 deferred). |
| **Migration head** (agent) | linearity / dialect / model-drift / data-loss | **Single head `048`, linear**, no orphans/cycles; no unguarded data-loss (all drops downgrade-only). P0/P1/P2 are prod-state/historical (PART 2), not the open branch. |
| **JSON/NaN + legal-scrub** (lead) | serialization boundary; §101 scrub coverage | NaN → fixed (#1). Legal scrub broad (26 route modules + decorator). |

---

## PART 4 — Meta
- **Frontend verified GREEN**: tsc 0 · vitest 545 passed.
- **Backend**: baseline (pre-fix) full-suite = **4 failed** (the masked flaky `data_status`,
  fixed in #2) / 3849 passed. **Post-fix full-suite = 3861 passed, 0 failed, 20 skipped,
  171 xfailed** (681 s). Δ +12 = 4 (flaky now green) + 7 (new json-provider) + 1 (new PIPA
  model-less purge). Zero regressions from the JSON provider across all 3861 tests.
- **Files changed**: `services/json_provider.py` (new), `app.py`, `services/cache_service.py`,
  `services/data/fmp.py`, `routes/auth.py`, `scripts/nightly/pipa_purge.py`, `tests/conftest.py`,
  `tests/test_json_provider_nan.py` (new), `tests/test_delete_account_full_cascade.py`,
  `frontend/src/lib/cfo/hooks.ts`, `frontend/src/components/ui/notification-dropdown.tsx`.
- **Not pushed** (feature-branch commit only, per session 1/2 convention).
