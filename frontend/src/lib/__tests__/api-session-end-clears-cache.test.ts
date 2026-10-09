/**
 * A successful account-deletion request (or logout) wipes the on-device
 * screen cache at the apiFetch layer — DeleteAccountModal calls these
 * endpoints directly and full-navigates away without going through logout().
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { PERSIST_STORAGE_PREFIX, persistStorageKey } from "@/lib/persisted-swr-cache";

const ok = () => new Response(JSON.stringify({ ok: true }), { status: 200 });
const fail = () => new Response(JSON.stringify({ error: "no" }), { status: 500 });

function seed() {
  window.localStorage.setItem(persistStorageKey(7), JSON.stringify({ v: 1, uid: 7, entries: {} }));
}
const ours = () => Object.keys(window.localStorage).filter((k) => k.startsWith(PERSIST_STORAGE_PREFIX));

beforeEach(() => {
  window.localStorage.clear();
});
afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiFetch — session-ending requests clear the persisted cache", () => {
  it.each([
    ["POST", API.auth.deleteRequest],
    ["DELETE", API.auth.deleteAccount],
    ["POST", API.auth.logout],
  ])("%s %s success clears it", async (method, path) => {
    seed();
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(ok())));
    await apiFetch(path, { method });
    expect(ours()).toEqual([]);
  });

  it("a failed deletion request keeps it", async () => {
    seed();
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(fail())));
    await expect(apiFetch(API.auth.deleteRequest, { method: "POST" })).rejects.toBeTruthy();
    expect(ours()).toHaveLength(1);
  });

  it("an ordinary read keeps it", async () => {
    seed();
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(ok())));
    await apiFetch(API.mirror.home);
    expect(ours()).toHaveLength(1);
  });
});
