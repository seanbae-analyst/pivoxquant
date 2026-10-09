/**
 * retakeChangesLeft — mirrors routes/profile.py::update_profile: only a free
 * (or missing) effective tier is capped by profile_changes_left.
 */
import { describe, it, expect } from "vitest";
import { retakeChangesLeft } from "@/lib/profile-retake";

describe("retakeChangesLeft", () => {
  it("free tier → the stored count, floored at 0", () => {
    expect(retakeChangesLeft({ effective_tier: "free", profile_changes_left: 2 })).toBe(2);
    expect(retakeChangesLeft({ effective_tier: "free", profile_changes_left: 0 })).toBe(0);
    expect(retakeChangesLeft({ effective_tier: "free", profile_changes_left: -1 })).toBe(0);
  });

  it("missing tier is treated as free, like the backend", () => {
    expect(retakeChangesLeft({ profile_changes_left: 0 })).toBe(0);
    expect(retakeChangesLeft({ subscription_tier: "free", profile_changes_left: 1 })).toBe(1);
  });

  it("any other tier is uncapped (null), whatever the stored count", () => {
    expect(retakeChangesLeft({ effective_tier: "pro", profile_changes_left: 0 })).toBeNull();
    expect(retakeChangesLeft({ effective_tier: "founding_lifetime", profile_changes_left: 3 })).toBeNull();
    expect(retakeChangesLeft({ subscription_tier: "premium", profile_changes_left: 0 })).toBeNull();
  });

  it("an unknown count does not block (server is the final word)", () => {
    expect(retakeChangesLeft({ effective_tier: "free" })).toBeNull();
  });
});
