/**
 * 문 앞의 한 줄 — a create or delete on the web door re-reads the /mirror door
 * card's summary (30 s dedupe), so a deleted line does not linger there
 * (2026-10-21).
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

const calls = vi.hoisted(() => ({
  mutate: vi.fn((filter: (key: unknown) => boolean) => {
    void filter;
    return Promise.resolve([]);
  }),
  apiFetch: vi.fn(() => Promise.resolve({ ok: true })),
}));

vi.mock("swr", async (orig) => ({
  ...(await orig<typeof import("swr")>()),
  mutate: (f: (key: unknown) => boolean) => calls.mutate(f),
}));
vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<typeof import("@/lib/api")>()),
  apiFetch: () => calls.apiFetch(),
}));

import { createDoorwayCheck, deleteDoorwayCheck } from "@/lib/hooks";

beforeEach(() => calls.mutate.mockClear());

function revalidated(): string[] {
  const keys = ["/api/doorway/summary?days=30", "/api/doorway/summary?days=90", "/api/doorway/checks?limit=20", "/api/mirror-home"];
  const filter = calls.mutate.mock.calls[0][0];
  return keys.filter((k) => filter(k));
}

describe("doorway writes", () => {
  it("re-read the summary after a create", async () => {
    await createDoorwayCheck({ intent: "look" });
    expect(revalidated()).toEqual(["/api/doorway/summary?days=30", "/api/doorway/summary?days=90"]);
  });
  it("re-read the summary after a delete", async () => {
    await deleteDoorwayCheck(7);
    expect(revalidated()).toEqual(["/api/doorway/summary?days=30", "/api/doorway/summary?days=90"]);
  });
});
