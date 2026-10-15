/**
 * Persisted SWR cache (2026-10-09) — the on-device copy of the main screens.
 *
 * What these pin, in order of how bad a regression would be:
 *   1. it never stores what it must not (auth/me, imports with raw broker
 *      text, support tickets, CSRF/profile) — allowlist + denylist;
 *   2. one user's copy never reaches another user's screen, and every
 *      "session ended" path wipes it;
 *   3. size cap + version + age limits hold;
 *   4. the screen paints the stored copy at once AND still revalidates it,
 *      even for hooks that set `revalidateIfStale: false` (portfolio);
 *   5. `useStaleness` / <LastSyncNote /> only speak up for an OLD copy and go
 *      quiet once fresh data lands.
 */
import React from "react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, act, waitFor } from "@testing-library/react";
import useSWR, { SWRConfig, type Cache } from "swr";

import {
  PERSIST_MAX_AGE_MS,
  PERSIST_MAX_CHARS,
  PERSIST_OWNER_KEY,
  PERSIST_STORAGE_PREFIX,
  PERSIST_VERSION,
  STALE_AFTER_MS,
  __resetPersistedCacheForTests,
  activatePersistedCacheForUser,
  clearPersistedSwrCache,
  flushPersistedCache,
  isPersistableKey,
  onSessionEndedElsewhere,
  persistStorageKey,
  persistedCacheMiddleware,
  persistedCacheUserId,
  recordFetched,
  syncPersistedCacheIdentity,
  useStaleness,
} from "@/lib/persisted-swr-cache";
import { API, PORTFOLIO_POSITIONS, PORTFOLIO_SUMMARY } from "@/lib/endpoints";
import { LastSyncNote } from "@/components/mirror/last-sync-note";

const NOW = Date.UTC(2026, 9, 9, 3, 0, 0);

function seed(uid: number, entries: Record<string, { at: number; data: unknown }>, v = PERSIST_VERSION) {
  window.localStorage.setItem(
    persistStorageKey(uid),
    JSON.stringify({ v, uid, entries }),
  );
}

function stored(uid: number): { v: number; uid: number; entries: Record<string, { at: number; data: unknown }> } | null {
  const raw = window.localStorage.getItem(persistStorageKey(uid));
  return raw ? JSON.parse(raw) : null;
}

function ourKeys(): string[] {
  return Object.keys(window.localStorage).filter((k) => k.startsWith(PERSIST_STORAGE_PREFIX));
}

const newCache = () => new Map() as unknown as Cache;

beforeEach(() => {
  window.localStorage.clear();
  __resetPersistedCacheForTests();
});

afterEach(() => {
  vi.useRealTimers();
  __resetPersistedCacheForTests();
});

describe("isPersistableKey — what may be stored on the device", () => {
  it.each([
    API.mirror.home,
    API.behavior.holdingMirror,
    API.behavior.concentrationMirror,
    API.behavior.profitLossMirror,
    API.behavior.turnoverMirror,
    API.behavior.averagingDownMirror,
    API.behavior.frictionOutcome,
    `${API.behavior.frictionOutcome}?period=30d`,
    PORTFOLIO_SUMMARY,
    PORTFOLIO_POSITIONS,
    `${API.preTrade.list}?limit=50`,
    `${API.observationNotes.list}?limit=200`,
  ])("allows %s", (key) => {
    expect(isPersistableKey(key)).toBe(true);
  });

  it.each([
    API.auth.me,
    "/api/csrf-token",
    API.imports.pending,
    API.imports.tokens,
    API.imports.image,
    API.imports.aiRead,
    API.support.inquiries,
    API.profile.get,
    API.notifications.preferences,
    `${API.alerts.list}?limit=50`,
    // filtered / unexpected query shapes are not the main screen's read
    `${API.preTrade.list}?ticker=AAPL&linkable=1`,
    `${API.observationNotes.list}?limit=50&ticker=AAPL`,
    `${PORTFOLIO_SUMMARY}?x=1`,
    "https://evil.example/api/mirror-home",
    "",
  ])("refuses %s", (key) => {
    expect(isPersistableKey(key)).toBe(false);
  });

  it("refuses non-string keys", () => {
    expect(isPersistableKey(null)).toBe(false);
    expect(isPersistableKey(["/api/mirror-home"])).toBe(false);
  });
});

describe("identity scoping", () => {
  it("restores only the confirmed user's copy, and deletes every other user's", () => {
    seed(7, { [API.mirror.home]: { at: NOW - 60_000, data: { who: 7 } } });
    seed(8, { [API.mirror.home]: { at: NOW - 60_000, data: { who: 8 } } });
    const cache = newCache();

    activatePersistedCacheForUser(cache, 7, NOW);

    expect(cache.get(API.mirror.home)?.data).toEqual({ who: 7 });
    expect(cache.get(API.mirror.home)?.isLoading).toBe(false);
    expect(window.localStorage.getItem(persistStorageKey(8))).toBeNull();
    expect(stored(7)).not.toBeNull();
  });

  it("never overwrites a live value already in the cache", () => {
    seed(7, { [API.mirror.home]: { at: NOW - 60_000, data: { old: true } } });
    const cache = newCache();
    cache.set(API.mirror.home, { data: { live: true } });

    activatePersistedCacheForUser(cache, 7, NOW);

    expect(cache.get(API.mirror.home)?.data).toEqual({ live: true });
  });

  it("a different user on the same tab evicts the previous user's data from memory", () => {
    seed(7, { [API.mirror.home]: { at: NOW - 60_000, data: { who: 7 } } });
    const cache = newCache();
    activatePersistedCacheForUser(cache, 7, NOW);
    cache.set(PORTFOLIO_SUMMARY, { data: { fetchedFor: 7 } }); // fetched live for 7
    cache.set(API.auth.me, { data: { authenticated: true } }); // not ours to touch

    activatePersistedCacheForUser(cache, 8, NOW);

    expect(cache.get(API.mirror.home)).toBeUndefined();
    expect(cache.get(PORTFOLIO_SUMMARY)).toBeUndefined();
    expect(cache.get(API.auth.me)).toBeDefined();
    expect(window.localStorage.getItem(persistStorageKey(7))).toBeNull();
  });

  it("syncPersistedCacheIdentity: 'not signed in' wipes every stored copy", () => {
    seed(7, { [API.mirror.home]: { at: NOW, data: { who: 7 } } });
    const cache = newCache();
    activatePersistedCacheForUser(cache, 7, NOW);

    syncPersistedCacheIdentity(cache, { authenticated: false });

    expect(ourKeys()).toEqual([]);
    expect(cache.get(API.mirror.home)).toBeUndefined();
  });

  it("syncPersistedCacheIdentity: a signed-in answer activates that id", () => {
    seed(7, { [API.mirror.home]: { at: Date.now(), data: { who: 7 } } });
    const cache = newCache();
    syncPersistedCacheIdentity(cache, { authenticated: true, user: { id: 7 } });
    expect(cache.get(API.mirror.home)?.data).toEqual({ who: 7 });
  });

  it("an answer without a numeric id is treated as signed out", () => {
    seed(7, { [API.mirror.home]: { at: NOW, data: { who: 7 } } });
    syncPersistedCacheIdentity(newCache(), { authenticated: true, user: { id: "7" } });
    expect(ourKeys()).toEqual([]);
  });
});

describe("payload rules", () => {
  it("discards another version instead of reading it", () => {
    seed(7, { [API.mirror.home]: { at: NOW, data: { v: "old" } } }, PERSIST_VERSION + 1);
    const cache = newCache();
    activatePersistedCacheForUser(cache, 7, NOW);
    expect(cache.get(API.mirror.home)).toBeUndefined();
  });

  it("drops entries older than the max age and keys that are not allowlisted", () => {
    seed(7, {
      [API.mirror.home]: { at: NOW - PERSIST_MAX_AGE_MS - 1, data: { tooOld: true } },
      [API.imports.pending]: { at: NOW, data: { raw_snippet: "계좌 1234" } },
      [PORTFOLIO_SUMMARY]: { at: NOW - 1000, data: { ok: true } },
    });
    const cache = newCache();
    activatePersistedCacheForUser(cache, 7, NOW);
    expect(cache.get(API.mirror.home)).toBeUndefined();
    expect(cache.get(API.imports.pending)).toBeUndefined();
    expect(cache.get(PORTFOLIO_SUMMARY)?.data).toEqual({ ok: true });
  });

  it("survives a corrupt payload", () => {
    window.localStorage.setItem(persistStorageKey(7), "{not json");
    const cache = newCache();
    expect(() => activatePersistedCacheForUser(cache, 7, NOW)).not.toThrow();
    expect(cache.get(API.mirror.home)).toBeUndefined();
  });

  it("writes newest entries first and stays under the size cap", () => {
    activatePersistedCacheForUser(newCache(), 7, NOW);
    const big = "x".repeat(Math.floor(PERSIST_MAX_CHARS * 0.6));
    recordFetched(PORTFOLIO_POSITIONS, { blob: big }, NOW - 10);
    recordFetched(PORTFOLIO_SUMMARY, { blob: big }, NOW); // newer — wins
    recordFetched(API.mirror.home, { small: 1 }, NOW - 5);
    flushPersistedCache(NOW);

    const payload = stored(7)!;
    expect(payload.v).toBe(PERSIST_VERSION);
    expect(payload.uid).toBe(7);
    expect(Object.keys(payload.entries).sort()).toEqual(
      [API.mirror.home, PORTFOLIO_SUMMARY].sort(),
    );
    expect(window.localStorage.getItem(persistStorageKey(7))!.length).toBeLessThan(
      PERSIST_MAX_CHARS + 1_000,
    );
  });

  it("never records a key outside the allowlist, even if asked", () => {
    activatePersistedCacheForUser(newCache(), 7, NOW);
    recordFetched(API.auth.me, { authenticated: true, user: { id: 7 } }, NOW);
    recordFetched(API.imports.pending, { items: [{ raw_snippet: "x" }] }, NOW);
    flushPersistedCache(NOW);
    expect(stored(7)!.entries).toEqual({});
  });

  it("records nothing while no user is active", () => {
    recordFetched(API.mirror.home, { a: 1 }, NOW);
    flushPersistedCache(NOW);
    expect(ourKeys()).toEqual([]);
  });

  it("a null answer removes the stored entry rather than keeping old data", () => {
    seed(7, { [API.mirror.home]: { at: NOW - 1000, data: { a: 1 } } });
    activatePersistedCacheForUser(newCache(), 7, NOW);
    recordFetched(API.mirror.home, null, NOW);
    flushPersistedCache(NOW);
    expect(stored(7)!.entries[API.mirror.home]).toBeUndefined();
  });

  it("flush also captures values that reached the cache by mutate, not fetch", () => {
    const cache = newCache();
    activatePersistedCacheForUser(cache, 7, NOW);
    cache.set(PORTFOLIO_POSITIONS, { data: { positions: [{ symbol: "AAPL" }] } });
    cache.set(API.support.inquiries, { data: { tickets: ["private"] } });
    flushPersistedCache(NOW);
    expect(stored(7)!.entries[PORTFOLIO_POSITIONS]).toEqual({
      at: NOW,
      data: { positions: [{ symbol: "AAPL" }] },
    });
    expect(stored(7)!.entries[API.support.inquiries]).toBeUndefined();
  });

  it("clearPersistedSwrCache removes every copy (any user, any version)", () => {
    seed(7, { [API.mirror.home]: { at: NOW, data: {} } });
    window.localStorage.setItem(`${PERSIST_STORAGE_PREFIX}v0:u3`, "{}");
    window.localStorage.setItem("pq_had_session", "1");
    clearPersistedSwrCache();
    expect(ourKeys()).toEqual([]);
    expect(window.localStorage.getItem("pq_had_session")).toBe("1");
  });

  it("a debounced write after logout does not resurrect the copy", () => {
    vi.useFakeTimers();
    activatePersistedCacheForUser(newCache(), 7, NOW);
    recordFetched(API.mirror.home, { a: 1 }, NOW);
    clearPersistedSwrCache();
    vi.advanceTimersByTime(5_000);
    expect(ourKeys()).toEqual([]);
  });
});

/* ── Another tab ───────────────────────────────────────────────────────── */

/** What another tab's writes look like here: the change, then its event. */
function otherTabSets(key: string, value: string | null) {
  if (value === null) window.localStorage.removeItem(key);
  else window.localStorage.setItem(key, value);
  window.dispatchEvent(new StorageEvent("storage", { key, newValue: value }));
}

// 2026-10-15 bug hunt: a tab left open as user 7 kept writing under 7's key
// after another tab switched the device to user 8 — and 8's portfolio, fetched
// with 8's cookie, was painted for 7 at 7's next sign-in.
describe("another tab ends this tab's session", () => {
  it("another account signs in: nothing more is written for the old user, and its copy goes", () => {
    const cache = newCache();
    const told = vi.fn();
    onSessionEndedElsewhere(told);
    activatePersistedCacheForUser(cache, 7, NOW);
    recordFetched(API.mirror.home, { who: 7 }, NOW);
    flushPersistedCache(NOW);
    expect(stored(7)).not.toBeNull();
    expect(window.localStorage.getItem(PERSIST_OWNER_KEY)).toBe("7");

    otherTabSets(PERSIST_OWNER_KEY, "8");

    expect(told).toHaveBeenCalledTimes(1);
    expect(persistedCacheUserId()).toBeNull();
    expect(stored(7)).toBeNull();
    // This tab's next answer comes with 8's cookie — it must not land as 7's.
    recordFetched(PORTFOLIO_POSITIONS, { positions: [{ ticker: "ONLY-8" }] }, NOW);
    flushPersistedCache(NOW);
    expect(ourKeys()).toEqual([]);
    expect(window.localStorage.getItem(PERSIST_OWNER_KEY)).toBe("8"); // the other tab's mark stays
  });

  it("the event never arrived (frozen tab): the write itself checks the owner mark", () => {
    activatePersistedCacheForUser(newCache(), 7, NOW);
    window.localStorage.removeItem(PERSIST_OWNER_KEY); // another tab logged out, silently

    recordFetched(PORTFOLIO_POSITIONS, { positions: [{ ticker: "AFTER-LOGOUT" }] }, NOW);
    flushPersistedCache(NOW);

    expect(persistedCacheUserId()).toBeNull();
    expect(ourKeys()).toEqual([]);
  });

  it("drops what this tab fetched from memory, so the next user's copy cannot capture it", () => {
    const cache = newCache();
    activatePersistedCacheForUser(cache, 7, NOW);
    cache.set(PORTFOLIO_SUMMARY, { data: { fetchedFor: 7 } });
    cache.set(API.auth.me, { data: { authenticated: true } }); // not ours to touch

    otherTabSets(PERSIST_OWNER_KEY, null);
    expect(cache.get(PORTFOLIO_SUMMARY)).toBeUndefined();
    expect(cache.get(API.auth.me)).toBeDefined();

    // /me then names user 8 in this tab — 7's value must not be written as 8's.
    activatePersistedCacheForUser(cache, 8, NOW);
    flushPersistedCache(NOW);
    expect(JSON.stringify(stored(8))).not.toContain("fetchedFor");
  });

  it("the same user in another tab changes nothing", () => {
    const told = vi.fn();
    onSessionEndedElsewhere(told);
    activatePersistedCacheForUser(newCache(), 7, NOW);
    otherTabSets(PERSIST_OWNER_KEY, "7");
    otherTabSets("unrelated", "x");
    recordFetched(API.mirror.home, { who: 7 }, NOW);
    flushPersistedCache(NOW);
    expect(told).not.toHaveBeenCalled();
    expect(stored(7)!.entries[API.mirror.home].data).toEqual({ who: 7 });
  });

  it("this tab's logout removes the owner mark, which is what the other tabs hear", () => {
    activatePersistedCacheForUser(newCache(), 7, NOW);
    clearPersistedSwrCache();
    expect(window.localStorage.getItem(PERSIST_OWNER_KEY)).toBeNull();
  });

  it("an owner mark that cannot be written means no on-device copy at all", () => {
    seed(7, { [API.mirror.home]: { at: NOW, data: { who: 7 } } });
    const setItem = Storage.prototype.setItem;
    const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(function (this: Storage, k: string, v: string) {
      if (k === PERSIST_OWNER_KEY) throw new DOMException("full", "QuotaExceededError");
      return setItem.call(this, k, v);
    });
    const cache = newCache();
    activatePersistedCacheForUser(cache, 7, NOW);
    spy.mockRestore();
    expect(persistedCacheUserId()).toBeNull();
    expect(cache.get(API.mirror.home)).toBeUndefined();
    expect(ourKeys()).toEqual([]);
  });
});

/* ── With real SWR ─────────────────────────────────────────────────────── */

function Screen({
  swrKey,
  fetcher,
  revalidateIfStale = true,
}: {
  swrKey: string;
  fetcher: (k: string) => Promise<unknown>;
  revalidateIfStale?: boolean;
}) {
  const { data } = useSWR(swrKey, fetcher, { revalidateIfStale });
  const { syncedAt, isStale } = useStaleness(swrKey);
  return (
    <div>
      <span data-testid="data">{JSON.stringify(data ?? null)}</span>
      <span data-testid="stale">{isStale ? "old" : syncedAt ? "recent" : "fresh"}</span>
    </div>
  );
}

function withSwr(cache: Cache, ui: React.ReactElement) {
  return render(
    <SWRConfig value={{ provider: () => cache, use: [persistedCacheMiddleware], dedupingInterval: 0 }}>
      {ui}
    </SWRConfig>,
  );
}

describe("middleware + useStaleness with real SWR", () => {
  it("paints the stored copy at once, revalidates even with revalidateIfStale:false, then stops marking it", async () => {
    const savedAt = Date.now() - STALE_AFTER_MS - 60_000;
    seed(7, { [PORTFOLIO_SUMMARY]: { at: savedAt, data: { nav: "stored" } } });
    const cache = newCache();
    activatePersistedCacheForUser(cache, 7);

    let resolveFetch: (v: unknown) => void = () => {};
    const fetcher = vi.fn(
      () => new Promise((r) => {
        resolveFetch = r;
      }),
    );
    withSwr(cache, <Screen swrKey={PORTFOLIO_SUMMARY} fetcher={fetcher} revalidateIfStale={false} />);

    expect(screen.getByTestId("data").textContent).toBe(JSON.stringify({ nav: "stored" }));
    expect(screen.getByTestId("stale").textContent).toBe("old");
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));

    await act(async () => {
      resolveFetch({ nav: "fresh" });
    });
    await waitFor(() =>
      expect(screen.getByTestId("data").textContent).toBe(JSON.stringify({ nav: "fresh" })),
    );
    expect(screen.getByTestId("stale").textContent).toBe("fresh");
  });

  it("an identical fresh answer still clears the mark (SWR keeps the old object)", async () => {
    seed(7, { [API.mirror.home]: { at: Date.now() - STALE_AFTER_MS - 1, data: { same: 1 } } });
    const cache = newCache();
    activatePersistedCacheForUser(cache, 7);
    withSwr(cache, <Screen swrKey={API.mirror.home} fetcher={async () => ({ same: 1 })} />);
    await waitFor(() => expect(screen.getByTestId("stale").textContent).toBe("fresh"));
  });

  it("a recent stored copy is not marked as old", () => {
    seed(7, { [API.mirror.home]: { at: Date.now() - 60_000, data: { a: 1 } } });
    const cache = newCache();
    activatePersistedCacheForUser(cache, 7);
    withSwr(cache, <Screen swrKey={API.mirror.home} fetcher={() => new Promise(() => {})} />);
    expect(screen.getByTestId("stale").textContent).toBe("recent");
  });

  it("successful fetches are written for the active user", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const cache = newCache();
    activatePersistedCacheForUser(cache, 7);
    withSwr(cache, <Screen swrKey={API.mirror.home} fetcher={async () => ({ m: 1 })} />);
    await waitFor(() => expect(screen.getByTestId("data").textContent).toBe('{"m":1}'));
    await act(async () => {
      vi.advanceTimersByTime(2_000);
    });
    expect(stored(7)!.entries[API.mirror.home].data).toEqual({ m: 1 });
  });

  it("does not touch hooks for keys outside the allowlist", async () => {
    const cache = newCache();
    activatePersistedCacheForUser(cache, 7);
    withSwr(cache, <Screen swrKey={API.support.inquiries} fetcher={async () => ({ t: 1 })} />);
    await waitFor(() => expect(screen.getByTestId("data").textContent).toBe('{"t":1}'));
    flushPersistedCache();
    expect(stored(7)!.entries).toEqual({});
  });
});

describe("<LastSyncNote />", () => {
  it("renders nothing for fresh data", () => {
    render(<LastSyncNote />);
    expect(screen.queryByTestId("last-sync-note")).toBeNull();
  });

  it("shows the fetch time for an old stored mirror, same day as HH:MM", () => {
    const savedAt = new Date();
    savedAt.setHours(0, 5, 0, 0); // 00:05 today
    const hydrateAt = savedAt.getTime() + STALE_AFTER_MS + 60_000;
    seed(7, { [API.mirror.home]: { at: savedAt.getTime(), data: { a: 1 } } });
    activatePersistedCacheForUser(newCache(), 7, hydrateAt);
    render(<LastSyncNote />);
    expect(screen.getByTestId("last-sync-note").textContent).toContain("마지막 동기화 00:05");
  });

  it("names the date when the copy is from an earlier day", () => {
    const savedAt = new Date(2026, 9, 8, 21, 30);
    const hydrateAt = new Date(2026, 9, 9, 8, 0).getTime();
    seed(7, { [API.mirror.home]: { at: savedAt.getTime(), data: { a: 1 } } });
    activatePersistedCacheForUser(newCache(), 7, hydrateAt);
    render(<LastSyncNote />);
    expect(screen.getByTestId("last-sync-note").textContent).toContain("10월 8일 21:30");
  });
});
