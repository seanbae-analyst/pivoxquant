import { describe, it, expect } from "vitest";

import { coercePulse, type PulseResponse } from "@/lib/cfo/hooks";

/**
 * Regression for the Weekly-Pulse localStorage crash (P2): a stale / older-schema
 * `pq_cfo_pulse_v1` blob (no `history` array) used to seed `fallbackData`/`swr.data`
 * and then crash `[...current.history]` in `submit`. `coercePulse` filters those to
 * `undefined` so callers fall back to `mockPulse()`.
 */

const valid: PulseResponse = { history: [], next_due_at: null, cadence: "weekly" };

describe("coercePulse", () => {
  it("passes a valid pulse through unchanged (history is an array)", () => {
    expect(coercePulse(valid)).toBe(valid);
  });

  it("returns undefined for null / undefined", () => {
    expect(coercePulse(null)).toBeUndefined();
    expect(coercePulse(undefined)).toBeUndefined();
  });

  it("returns undefined for a stale/corrupt blob with no history array", () => {
    // The exact corruption vectors: empty object, wrong type, null history.
    expect(coercePulse({} as unknown as PulseResponse)).toBeUndefined();
    expect(
      coercePulse({ history: "nope" } as unknown as PulseResponse),
    ).toBeUndefined();
    expect(
      coercePulse({ history: null } as unknown as PulseResponse),
    ).toBeUndefined();
  });
});
