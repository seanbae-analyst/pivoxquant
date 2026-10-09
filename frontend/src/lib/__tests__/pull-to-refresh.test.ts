import { describe, it, expect, vi, beforeEach } from "vitest";

const mutate = vi.fn((filter: (key: unknown) => boolean) => {
  void filter;
  return Promise.resolve([]);
});
vi.mock("swr", () => ({ mutate: (f: (key: unknown) => boolean) => mutate(f) }));

import {
  PULL_MAX_PX,
  PULL_THRESHOLD_PX,
  classifyPull,
  revalidateKeys,
  rubberBand,
} from "@/lib/pull-to-refresh";

beforeEach(() => mutate.mockClear());

describe("rubberBand", () => {
  it("follows the finger at first, then resists and never passes the max", () => {
    expect(rubberBand(-20)).toBe(0);
    expect(rubberBand(10)).toBeGreaterThan(9);
    expect(rubberBand(60)).toBeLessThan(60);
    expect(rubberBand(10_000)).toBeLessThanOrEqual(PULL_MAX_PX);
  });
  it("reaches the 70px threshold at roughly 100px of finger travel", () => {
    expect(rubberBand(90)).toBeLessThan(PULL_THRESHOLD_PX);
    expect(rubberBand(100)).toBeGreaterThanOrEqual(PULL_THRESHOLD_PX);
  });
});

describe("classifyPull", () => {
  it("waits inside the slop", () => {
    expect(classifyPull(3, 5)).toBe("undecided");
  });
  it("only a downward, mostly vertical move is a pull", () => {
    expect(classifyPull(2, 20)).toBe("pull");
    expect(classifyPull(0, -20)).toBe("other"); // scrolling down the page
    expect(classifyPull(30, 12)).toBe("other"); // a pager swipe
    expect(classifyPull(18, 20)).toBe("other"); // diagonal: not ours
  });
});

describe("revalidateKeys", () => {
  it("revalidates (never overwrites) the given keys, query strings ignored", async () => {
    await revalidateKeys(["/api/pre-trade/list", "/api/behavior/holding-mirror"]);
    expect(mutate).toHaveBeenCalledTimes(1);
    const filter = mutate.mock.calls[0][0];
    expect(filter("/api/pre-trade/list?limit=50")).toBe(true);
    expect(filter("/api/behavior/holding-mirror")).toBe(true);
    expect(filter("/api/mirror-home")).toBe(false);
    expect(filter(["/api/pre-trade/list"])).toBe(false);
  });
});
