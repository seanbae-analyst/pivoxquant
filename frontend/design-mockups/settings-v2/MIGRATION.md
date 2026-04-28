# /settings v1 → v2 — MIGRATION

> **Source of truth**:
> - v1 file: `frontend/src/app/(dashboard)/settings/page.tsx`
> - v1 endpoints: `frontend/src/lib/endpoints.ts` (lines 5–202)
> - v1 hooks: `frontend/src/lib/hooks.ts` (lines 43–202)
>
> **This document is a 1-to-1 mapping** of every v1 setting to its v2 home. Each row cites the exact v1 source (file:line or function), the v2 section, the wired endpoint, and the wired hook. **No item is left as "TBD" — gaps are explicitly labelled GAP and routed to a follow-up task.**

---

## 1. Mapping table — 11 CEO-required features

| # | Feature (v1)                          | v1 source (cited)                                          | v2 section / card | Endpoint (from `endpoints.ts`)                                    | Hook (from `hooks.ts` or auth)                  | Status |
|---|---------------------------------------|------------------------------------------------------------|-------------------|--------------------------------------------------------------------|------------------------------------------------|--------|
| 1 | Name + Email (read/edit)              | `AccountSection()` settings/page.tsx:122–161               | A1 Identity       | `API.profile.get` `/api/profile` · `API.profile.update` `/api/profile` | `useAuth()` (auth.tsx) · `user.name`, `user.email` | ✅ wired |
| 2 | Password change                       | **Not present in v1** — OAuth-only project                 | A2 Sign-in (row marked "N/A — OAuth-only") | — (no endpoint exists)                                | —                                              | **GAP-L** label only · v3-OAuth-pure stays |
| 3 | Google OAuth link / unlink            | `useAuth().user.oauth_provider` settings/page.tsx:130–139  | A2 Sign-in        | `API.auth.google` `/api/auth/google`                                | `useAuth()`                                    | ✅ wired (link) · **GAP-D** disconnect endpoint not in `endpoints.ts` |
| 4 | Kakao OAuth link / unlink             | `oauth_provider === "kakao"` settings/page.tsx:135–137     | A2 Sign-in        | `API.auth.kakao` `/api/auth/kakao`                                  | `useAuth()`                                    | ✅ wired (link) · **GAP-D** disconnect endpoint not in `endpoints.ts` |
| 5 | Alpaca broker connect (P0 bug)        | `BrokersSection()` + `AlpacaCard` + `AlpacaConnectModal` settings/page.tsx:387–493 | B1 Alpaca | `API.broker.alpacaConnect` / `…Sync` / `…Disconnect` / `…Status` (endpoints.ts:198–201) | `useBrokerConnections()` hooks.ts:176 | ✅ wired |
| 6 | KIS read-only connect                 | `KisCard` + `KisConnectModal` settings/page.tsx:451–491    | B2 KIS            | `API.broker.kisConnect` / `…Sync` / `…Disconnect` / `…Status` (endpoints.ts:192–195) | `useBrokerConnections()` hooks.ts:176 | ✅ wired |
| 7 | Notifications · email/push/in-app × event types | `PreferencesSection()` settings/page.tsx:534–652 (push toggle, email toggle via `localStorage.sp_mb_email`) | C Notifications matrix | Push: `API.push.subscribe` / `…unsubscribe` / `…status` (endpoints.ts:184–188) · Email: localStorage flag (no backend endpoint) · In-app: derived from `API.alerts.*` (endpoints.ts:69–79) | Push: `subscribeToPush` / `unsubscribeFromPush` / `getPushSubscription` from `lib/push` · Email: `useState` + localStorage · In-app: `useAlerts()` hooks.ts:73 | ✅ wired (push) · **GAP-E** per-event matrix backend (currently single global toggle) |
| 8 | Stripe subscription (Free/Pro/Premium)| `SubscriptionSection()` settings/page.tsx:314–383          | D Subscription    | `API.billing.subscription` `/api/billing/subscription` · `API.billing.portal` `/api/billing/portal` · `API.billing.createCheckout` `/api/billing/create-checkout` (endpoints.ts:179–183) | `useSWR(API.billing.subscription)` settings/page.tsx:316 · `useAuth().user.subscription_tier` | ✅ wired |
| 9 | Account deletion (PIPA)               | `DeleteAccountModal` settings/page.tsx:656–697 (mailto fallback) | E3 Danger zone   | `API.auth.deleteAccount` `/api/auth/delete-account` (endpoints.ts:13) — **but v1 currently uses `mailto:` only** | — | ⚠️ wired-by-mailto (matches v1) · **GAP-J** in-app delete flow not yet wired |
| 10| Cookie consent                        | **Not in v1 settings** — handled by global `CookieConsent` component (mounted in dashboard layout) | E1 Cookie consent | localStorage flags (no backend endpoint exists) | — | ⚠️ **moved into Settings as a granular surface** · **GAP-C** backend persistence — currently localStorage only |
| 11| Data export                           | **Not in v1 settings** — only an "Export agent memory" CTA on `/profile` (profile-v2 BLOCK 6) | E2 Data export | — (no endpoint exists in `endpoints.ts`) | — | **GAP-X** new endpoint needed `/api/profile/export` (JSON archive) |

### Bonus: v1-only items that v2 keeps

| # | v1 item                                | v1 source                             | v2 section | Notes |
|---|----------------------------------------|---------------------------------------|------------|-------|
| 12| Seed capital (USD/KRW)                 | `SeedCapitalSection()` settings/page.tsx:180–310 | **moved to /profile** (profile-v2 BLOCK already covers identity) | endpoint `API.profile.capital` (endpoints.ts:168) — out of v2 settings scope per CEO ("identity moves to /profile") |
| 13| Language toggle                        | `useLocale()` settings/page.tsx:535, 626–647    | A1 Identity → Locale row (한국어 / English pills) | client-only locale, no backend |
| 14| Sign out                               | `handleSignOut` settings/page.tsx:707–715       | E3 Danger zone left column | `API.auth.logout` `/api/auth/logout` (endpoints.ts:9) |

---

## 2. GAP register (must be filed as separate tasks)

Six gaps are surfaced by this mockup. None block v2 visual approval, but each must be tracked before implementation.

| Code   | Gap                                                              | Owner   | Resolution direction |
|--------|------------------------------------------------------------------|---------|----------------------|
| GAP-D  | OAuth disconnect endpoint absent for Google + Kakao              | Backend | Add `POST /api/auth/<provider>/disconnect` with last-provider guard |
| GAP-E  | Per-event-type notification matrix (currently single global toggle) | Backend + DB | Add `notification_pref` table keyed by `(user_id, event, channel)` |
| GAP-J  | In-app account-delete flow (currently mailto)                    | Backend | Wire `API.auth.deleteAccount` (already declared) → confirmation modal + 30-day purge |
| GAP-C  | Cookie-consent persistence (currently localStorage only)         | Backend | Add `consent_log` (PIPA evidence trail) — server-stamped |
| GAP-X  | Data export JSON archive endpoint                                | Backend | Add `POST /api/profile/export` → email delivery within 24h |
| GAP-L  | Password sign-in not in product scope                            | Decision| Confirm OAuth-only stance is permanent; otherwise add `/api/auth/password` |

---

## 3. Citations — exact strings used to confirm v1 wiring

Each citation is a literal token from `endpoints.ts` or `hooks.ts`. Re-grep before merge if either file moves.

```
endpoints.ts:9    logout: "/api/auth/logout"
endpoints.ts:11   google: "/api/auth/google"
endpoints.ts:12   kakao: "/api/auth/kakao"
endpoints.ts:13   deleteAccount: "/api/auth/delete-account"
endpoints.ts:163  profile: { get: "/api/profile", … }
endpoints.ts:168  capital: "/api/profile/capital"
endpoints.ts:179  billing: { createCheckout, subscription, portal }
endpoints.ts:184  push: { subscribe, unsubscribe, status }
endpoints.ts:189  broker: { connections, kisConnect/Sync/Disconnect/Status, alpacaConnect/Sync/Disconnect/Status }

hooks.ts:73       export function useAlerts()
hooks.ts:176      export function useBrokerConnections()
```

v1 settings page also imports:
```
settings/page.tsx:22  import { KisCard } from "@/components/broker/kis-card"
settings/page.tsx:23  import { KisConnectModal } from "@/components/broker/kis-connect-modal"
settings/page.tsx:24  import { AlpacaCard } from "@/components/broker/alpaca-card"
settings/page.tsx:25  import { AlpacaConnectModal } from "@/components/broker/alpaca-connect-modal"
```
These four components are **reused as-is** when v2 lands. The mockup illustrates their target surface; no rewrite is required.

---

## 4. Build sequence (when implementation starts — not now)

1. **Section A** — Account section already exists (settings/page.tsx:122–161); reskin into A1 + A2 cards with new tokens. Add Kakao link CTA (GAP-D allowing).
2. **Section B** — drop `KisCard` + `AlpacaCard` into the new `.conn-card` shell; no logic change.
3. **Section C** — replace global push toggle with the 7×3 matrix once GAP-E backend lands. Until then, ship matrix UI but bind only the rows that have endpoints; gray out unbacked rows with a `pill dim` "soon" tag.
4. **Section D** — keep `SubscriptionSection` logic; replace single card with the 3-tier comparison; current-tier card gets bronze border via `tier-card.current`.
5. **Section E** — port `DeleteAccountModal` (mailto path) until GAP-J. Cookie consent UI is ready in mockup; persistence stays localStorage until GAP-C.
6. **Seed capital** moves to `/profile` (profile-v2 already covers identity); the v1 `SeedCapitalSection` is **deleted from /settings** when v2 ships.

---

## 5. Verification checklist (pre-merge of v2 PR)

- [ ] `rg -i '(buy|sell|hold|recommend|advice|coach|추천|조언)' design-mockups/settings-v2/` returns **0 matches**
- [ ] All 11 CEO features mapped above appear on the rendered mockup with the listed endpoint+hook attribution
- [ ] Disclaimer block (KR + EN) present at end of `<main>`
- [ ] Bronze border on **current tier** only (Pro)
- [ ] Disconnect / Cancel / Delete affordances use `--pq-error`, never `--pq-positive` / `--pq-negative` (those are KR price colors only)
- [ ] All numbers (timestamps, amounts, account IDs) use `.num` class → tabular-nums
- [ ] Anchor rail `position: sticky` works at 1280px without overlapping the hero
