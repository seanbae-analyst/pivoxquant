import { describe, expect, it, vi, afterEach } from "vitest";

import { parseUtcSafe, relativeTime } from "@/lib/relative-time";

/**
 * Regression guard (AUTOPILOT_BACKLOG 2026-07-12 P1):
 * a naive ISO string is parsed as LOCAL time by `new Date()`, so KST users saw
 * freshly-observed prices labelled "9h ago" behind an amber stale dot.
 */
describe("parseUtcSafe", () => {
  afterEach(() => vi.useRealTimers());

  it("reads a naive stamp as UTC, not local time", () => {
    expect(parseUtcSafe("2026-08-30T07:00:00")).toBe(
      Date.UTC(2026, 7, 30, 7, 0, 0),
    );
  });

  it("agrees with an explicitly marked stamp", () => {
    expect(parseUtcSafe("2026-08-30T07:00:00")).toBe(
      parseUtcSafe("2026-08-30T07:00:00Z"),
    );
  });

  it("honours a non-UTC offset instead of overriding it", () => {
    expect(parseUtcSafe("2026-08-30T16:00:00+09:00")).toBe(
      Date.UTC(2026, 7, 30, 7, 0, 0),
    );
  });

  it("passes a Date through unchanged", () => {
    const d = new Date("2026-08-30T07:00:00Z");
    expect(parseUtcSafe(d)).toBe(d.getTime());
  });

  it("returns NaN for absent or unparseable input", () => {
    expect(parseUtcSafe(null)).toBeNaN();
    expect(parseUtcSafe(undefined)).toBeNaN();
    expect(parseUtcSafe("")).toBeNaN();
    expect(parseUtcSafe("garbage")).toBeNaN();
  });

  it("does not drift a just-observed naive stamp into the past", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-30T07:00:00Z"));
    // What the backend used to emit: naive UTC wall-clock, no marker.
    expect(relativeTime("2026-08-30T06:59:30", "ko")).toBe("방금");
    expect(relativeTime("2026-08-30T06:59:30", "en")).toBe("just now");
  });
});
