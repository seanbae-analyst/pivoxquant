/**
 * toUiTier (reports v2 page boundary) — founding_lifetime / premium_plus are
 * PAID tiers on the backend (services/artifacts/_tiers.py PAID_TIERS_* include
 * both). The old raw `as Tier` cast let them through to the v2 components'
 * 3-key TIER_RANK lookups → rank undefined → a founding user saw every tile
 * locked, including the free Brag Card ("Upgrade to free"). 2026-06-11 fix.
 */
import { describe, it, expect } from "vitest";
import { toUiTier } from "@/app/(dashboard)/reports/_v2/page-v2";

describe("reports v2 toUiTier", () => {
  it("collapses lifetime/plus entitlement tiers to premium", () => {
    expect(toUiTier("founding_lifetime")).toBe("premium");
    expect(toUiTier("premium_plus")).toBe("premium");
  });

  it("passes canonical tiers through and defaults unknown/missing to free", () => {
    expect(toUiTier("free")).toBe("free");
    expect(toUiTier("pro")).toBe("pro");
    expect(toUiTier("premium")).toBe("premium");
    expect(toUiTier(undefined)).toBe("free");
    expect(toUiTier(null)).toBe("free");
    expect(toUiTier("some_future_tier")).toBe("free");
  });
});
