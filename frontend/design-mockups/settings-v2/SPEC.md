# /settings v2 — SPEC

> **Wave**: home-v2 → profile-v2 → **settings-v2**
> **Tone**: Editorial CFO room — Vantablack canvas, Bronze register, KR price convention.
> **Status**: Mockup only. No code, no implementation. Wireframe + content + token bindings.
> **Locked design system**: v3 (project_design_v3 · 2026-04-27).

---

## 1. Intent

Settings is the **operational dashboard** of the CFO room. Identity / persona belong to `/profile`; this surface holds only the dials the user adjusts: how they sign in, which brokers stream, what the room sends them, what they pay, and how they exercise data rights.

The page must read like an editorial control panel — section letters (A–E), serif section titles, mono row labels, no admin-y form bloat. **Form atoms exist, but the spread between them is editorial, not Material Design.**

---

## 2. Page anatomy

| Region                | Role                                                 | Source token                       |
|-----------------------|------------------------------------------------------|------------------------------------|
| Top nav               | Wordmark + section nav (Settings active)             | `.topnav` · `--pq-hairline`        |
| Top ticker (full bleed)| SPX/NDX/DJI/KOSPI/KOSDAQ/USD-KRW/VIX/10Y UST       | `.ticker` · `.pos` / `.neg`        |
| CFO status hairline   | OPEN · brokers count · plan · last config change     | `.cfo-status`                       |
| Hero                  | Eyebrow + Playfair H1 + Source Serif deck + CTA pair | `.pq-hero` · `.display-h1`         |
| Anchor rail (sticky)  | A · Identity / B · Brokers / C · Notifications / D · Subscription / E · Privacy | `.anchor-rail`     |
| Sections A–E          | Card-based, 2-col on Identity/Privacy, full on others| `.pq-card`                          |
| Disclaimer            | Dashed hairline, KR + EN                             | `.disclaimer`                       |
| Foot                  | Wordmark · Volume · City                             | `.foot`                             |

Layout: `max-w-[1280px]` content well · 12-col grid · 2-col rail (`.anchor-rail`) + 10-col body. Anchor rail is `position: sticky; top: 24px;`.

---

## 3. Section content — full text

### A. Identity & Security

| Card | Heading | Rows | Affordance |
|------|---------|------|------------|
| A1 Identity | "Signed-in as" | Display name (edit-in-place) · Email (verified, read-only) · Locale (한국어 / English pill toggle) | inline edit, language pill toggle |
| A2 Sign-in  | "How you authenticate" | Google (Linked, Disconnect link) · Kakao (Not linked, Connect link) · Password (N/A — OAuth-only) | Provider link/unlink |

**Helper line** (under A2): "At least one OAuth provider must remain connected. Disconnecting your last provider locks the account."

### B. Brokers

Hero deck: "PivoxQuant operates brokers on a *Bring-Your-Own-Key* model. We forward read-only requests under your own license — we never place orders, never store live trading credentials."

| Card | State shown | Body |
|------|-------------|------|
| B1 Alpaca | **Connected · Paper** | Glyph (α) · pill row (Connected, Paper) · last sync timestamp · 12 positions / 1 cash · `Sync now` ghost CTA + `Disconnect` red link · 3-col detail strip (Mode, Account ID, Buying power) · helper: "live trading hard-disabled at backend" |
| B2 KIS    | **Not connected**     | Glyph (韓) · pill (Not connected) · "Read-only KR positions and account balance · KOSPI / KOSDAQ symbols." · primary `Connect KIS →` CTA · helper explains App Key / App Secret / 계좌번호 + encryption at rest |

### C. Notifications

**Matrix table** — 7 events × 3 channels:

| Event                          | Email | Push | In-app |
|--------------------------------|:-----:|:----:|:------:|
| Weekly memo · Mon 07:00 KST    | on    | on   | on     |
| Earnings pre-brief             | on    | on   | on     |
| Signal state change            | off   | on   | on     |
| Risk layer breach              | on    | on   | on     |
| Pulse prompt · Weekly          | on    | off  | on     |
| Brag card · Monthly            | on    | off  | on     |
| Broker sync error              | on    | on   | on     |

Plus 2 sub-cards:
- **C1 Push**: device permission line (granted / device label / `Test push` link)
- **C2 Email**: delivery toggle to user's email

### D. Subscription

3-col tier comparison:

| Tier        | Price          | State    | Bullets |
|-------------|----------------|----------|---------|
| Free        | ₩0/mo          | -        | Watchlist 5 sym · Weekly memo read-only · Risk 30D |
| **Pro**     | **₩9,900/mo** · renews 14 May | **Current** (bronze border + bronze-04 wash) | Unlimited watchlist · Earnings pre-brief · Brag card · Broker sync · Persona v3 90D |
| Premium     | ₩19,900/mo     | -        | All Pro · Companion · Persona v3 365D · All cohorts · Priority queue |

Footer card **D1 Receipt**: 4-col strip — Last invoice · Amount · Method (Visa · 4242) · Receipts (Stripe portal link).

Current plan card has `Manage billing` ghost + `Cancel plan` red link. Premium card has primary `Upgrade to Premium →` CTA.

### E. Privacy

3 surfaces stacked:

| Card | Body |
|------|------|
| E1 Cookie consent | 4 categories with toggles: Strictly necessary (Always on, no toggle) · Analytics (on) · Performance (on) · Marketing (off, default) |
| E2 Data export    | "Download a portable JSON copy…" · last export timestamp + size · `Request new export →` primary CTA · 24h delivery, includes Companion archive on Premium |
| E3 Danger zone (red border) | 2-col split: Sign out (`Sign out →` ghost) and Delete account (`Contact support to delete` red link, `mailto:seanbae1521@gmail.com`) — PIPA · 30-day purge |

---

## 4. Token bindings (mirror of `frontend/src/app/globals.css`)

| Token | Use |
|-------|-----|
| `--pq-ink #050505` | body, hero |
| `--pq-ivory #F5F0E8` | primary text |
| `--pq-ivory-soft .82` | secondary text |
| `--pq-ivory-quiet .55` | metadata, ticker prices |
| `--pq-ivory-mute .40` | helper, dim eyebrows |
| `--pq-bronze #B8956A` | eyebrows, italic emphasis word, current tier border, link |
| `--pq-bronze-deep #6F5636` | gauge gradient base (none on this page) |
| `--pq-bronze-15 / -08` | hover wash, link underline |
| `--pq-positive #dc2626` | KR price up only (ticker) — never on settings actions |
| `--pq-negative #2563eb` | KR price down only (ticker) — never on settings actions |
| `--pq-error #d18888` | disconnect / cancel / delete links and danger-zone border |
| `--pq-hairline` / `--pq-hairline-2` | dividers, card border, dashed disclaimer |
| `--pq-radius-cta 2px` | CTA pill (intentionally squarer than convention) |
| `--pq-radius-card 4px` | cards |

Fonts: `--pq-font-display` (Playfair) for H1/H2/tier names · `--pq-font-serif` (Source Serif 4) for editorial body and row names · `--pq-font-mono` (JetBrains Mono) for eyebrows/numbers/pills · `--pq-font-sans` (Pretendard) for app shell.

Number convention: KR locked — up=red, down=blue, won/dollar formatted via `lib/format.ts` helpers.

---

## 5. Ban-list compliance

Zero occurrences of: `BUY`, `SELL`, `HOLD`, `recommend`, `recommendation`, `advice`, `AI Coach`, `투자 코치`, `추천`, `조언`. Verify with `rg -i '(buy|sell|hold|recommend|advice|coach|추천|조언)' settings-v2/mockup.html` before merge.

Disclaimer is bilingual KR + EN, dashed-hairline framed, present at the bottom of `<main>`.

---

## 6. Responsive notes (informational only — desktop 1280 priority)

- 1280px: as drawn — 12-col grid + sticky rail.
- 1024px: rail collapses to a horizontal pill row above the hero; sections stack 1-col.
- 768px: notifications matrix becomes accordion list (event = header, 3 toggles in body).
- 375px: connection cards reflow glyph-on-top + actions stacked.

These are informational; the v2 mockup pass freezes the desktop story only.

---

## 7. Acceptance bar

A pass is when: (a) every v1 setting maps to exactly one v2 location (see MIGRATION.md), (b) the editorial cadence A–E reads without scroll-jank, (c) the page contains zero ban-list strings, (d) the disclaimer is present, (e) all numbers use `tabular-nums` via the `.num` class.
