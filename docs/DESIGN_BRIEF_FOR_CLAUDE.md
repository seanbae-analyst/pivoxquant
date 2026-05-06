# PivoxQuant — Design Brief (stub)

> **SoT for visual design**: [`frontend/design-principles-cfo.md`](../frontend/design-principles-cfo.md).
> **SoT for /home v2 component spec**: [`frontend/design-mockups/home-v2/SPEC.md`](../frontend/design-mockups/home-v2/SPEC.md).
> Do not duplicate visual rules here. If you find yourself wanting to write color/typography/layout rules in this file, edit the SoT instead.

---

## Why this file exists (and why it's short)

This file used to carry the full design brief — color palette, typography stack, banned patterns. That created two SoTs and the codebase drifted from both. As of 2026-05-06 the visual brief lives only in `frontend/design-principles-cfo.md` (Vantablack + Bronze + Playfair/Source Serif/JetBrains/Geist+Pretendard, locked v3 2026-04-27).

This stub remains for the few non-visual context items that have no other home — product positioning, banned product copy, and the prompt template for handing context to an external design tool.

## Product context (1-paragraph)

**PivoxQuant** is an AI + Quant personal investment platform for Korean retail investors trading US + Korean equities. Core concept: "User as CFO" — users feel like their own portfolio's Chief Financial Officer, not a chatbot user. We generate Artifacts (PDF reports, emails, Brag Cards) while users sleep. Pricing: Free / Pro ₩9,900 / Premium ₩19,900. Solo founder, Seoul, private beta April 2026.

## Banned product copy (legal — non-visual)

These strings must never appear in UI, regardless of design choices:
- `BUY`, `SELL`, `HOLD` (자본시장법 — use POSITIVE/NEGATIVE/NEUTRAL)
- `recommend`, `recommendation`, `advice`, `advise`, `추천`, `조언`
- `AI Coach`, `AI Assistant`, `투자 코치`

`DisclaimerBanner` is mounted once by `(dashboard)/layout.tsx`. Don't duplicate.

## When briefing an external design tool

Paste this preamble, then your specific request:

```
PivoxQuant — AI + Quant personal investment platform, Korean retail investors,
US + Korean stocks. "User as CFO" concept. Generates PDF Artifacts (Weekly
Memo, Earnings Pre-Brief, Brag Card) while user sleeps.

Visual SoT: frontend/design-principles-cfo.md (Vantablack #050505 + Bronze
#B8956A + ivory #F5F0E8). Typography: Playfair Display (display Serif) +
Source Serif 4 (reading Serif) + Geist+Pretendard (body Sans) + JetBrains
Mono (numbers).

Banned: purple/blue gradients, neon glow, "AI Coach" labels, BUY/SELL.
Required: tabular-nums on all numbers, DisclaimerBanner footer, KR/EN
toggle.

Component-level spec when designing /home: frontend/design-mockups/home-v2/SPEC.md.

Now design: [your specific request]
```

---

**Last updated**: 2026-05-06 — reduced from 236-line full-brief to stub + SoT links.
