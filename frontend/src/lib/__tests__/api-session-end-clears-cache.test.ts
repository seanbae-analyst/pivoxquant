/**
 * A successful account-deletion request (or logout) wipes the on-device
 * screen cache at the apiFetch layer — DeleteAccountModal calls these
 * endpoints directly and full-navigates away without going through logout().
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import type { Cache } from "swr";
import {
  PERSIST_STORAGE_PREFIX,
  __resetPersistedCacheForTests,
  activatePersistedCacheForUser,
  persistStorageKey,
} from "@/lib/persisted-swr-cache";
import { storageKey as paydayKey } from "@/lib/payday-plan";

const ok = () => new Response(JSON.stringify({ ok: true }), { status: 200 });
const fail = () => new Response(JSON.stringify({ error: "no" }), { status: 500 });

function seed() {
  window.localStorage.setItem(persistStorageKey(7), JSON.stringify({ v: 1, uid: 7, entries: {} }));
}
const ours = () => Object.keys(window.localStorage).filter((k) => k.startsWith(PERSIST_STORAGE_PREFIX));

beforeEach(() => {
  window.localStorage.clear();
  __resetPersistedCacheForTests();
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

describe("apiFetch — an account-deletion request also clears that user's 월급날 배분", () => {
  function seedPayday() {
    window.localStorage.setItem(paydayKey(7), JSON.stringify({ v: 1, payday: 25, cycles: [] }));
    window.localStorage.setItem(paydayKey(8), JSON.stringify({ v: 1, payday: 10, cycles: [] }));
  }
  const signedInAs = (uid: number) => activatePersistedCacheForUser(new Map() as unknown as Cache, uid);

  it.each([
    ["POST", API.auth.deleteRequest],
    ["DELETE", API.auth.deleteAccount],
  ])("%s %s success removes the signed-in user's plan only", async (method, path) => {
    seedPayday();
    signedInAs(7);
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(ok())));
    await apiFetch(path, { method });
    expect(window.localStorage.getItem(paydayKey(7))).toBeNull();
    expect(window.localStorage.getItem(paydayKey(8))).not.toBeNull();
  });

  it("logout keeps it — the plan is the user's own note on this device", async () => {
    seedPayday();
    signedInAs(7);
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(ok())));
    await apiFetch(API.auth.logout, { method: "POST" });
    expect(window.localStorage.getItem(paydayKey(7))).not.toBeNull();
  });

  it("a failed deletion request keeps it", async () => {
    seedPayday();
    signedInAs(7);
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(fail())));
    await expect(apiFetch(API.auth.deleteRequest, { method: "POST" })).rejects.toBeTruthy();
    expect(window.localStorage.getItem(paydayKey(7))).not.toBeNull();
  });

  it("with no confirmed user nothing is removed", async () => {
    seedPayday();
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(ok())));
    await apiFetch(API.auth.deleteRequest, { method: "POST" });
    expect(window.localStorage.getItem(paydayKey(7))).not.toBeNull();
    expect(window.localStorage.getItem(paydayKey(8))).not.toBeNull();
  });
});
