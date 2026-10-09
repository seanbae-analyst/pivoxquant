/**
 * Persisted SWR cache — last-known data for the signed-in user's main screens.
 *
 * Why
 * ---
 * The backend is on Render's free plan and sleeps after 15 idle minutes
 * (measured cold start ~44 s, `.github/workflows/keep-warm.yml`). Keeping it
 * warm 24/7 is out of the instance-hour budget, so the app has to feel fast
 * while the server is still booting. This module keeps the last successful
 * response of a short allowlist of read-only keys (/mirror, /journal,
 * /portfolio) in localStorage, and puts it back into SWR's in-memory cache
 * the moment the server has confirmed WHO is signed in — so the screen paints
 * the last data immediately and SWR revalidates it in the background.
 *
 * Privacy reasoning (this is personal financial data on a device)
 * ---------------------------------------------------------------
 * - What: only the allowlisted read responses below — mirror home, the five
 *   behaviour mirrors + friction outcome, the pre-trade journal list, the
 *   observation-note feed, portfolio summary and positions. All of it is the
 *   user's own record, already rendered on this same device. NEVER persisted:
 *   `/api/auth/*` (identity, session state), CSRF/session cookies or any
 *   token, `/api/support/*` (tickets), `/api/portfolio/imports/*` (pending
 *   rows carry `raw_snippet`, i.e. raw broker text, plus import tokens and
 *   image/AI reads), profile/notification settings. Keys are allowlisted, not
 *   denylisted, and a denylist is checked on top as a second line.
 * - Where: this browser's localStorage only. Nothing here is sent anywhere —
 *   the operator never receives this copy, so it is not a new collection or a
 *   new processor (privacy-ko §1, §6). It is the same category as the service
 *   worker's API cache that already exists (`clearSwApiCache` in lib/auth).
 * - Whose: scoped per user — the storage key includes the user id, the data
 *   enters SWR only after `/api/auth/me` has confirmed that same id, and any
 *   other user's entry is deleted at that point.
 * - How long: cleared on logout, on an account-deletion request (POST
 *   delete-request / DELETE delete-account, hooked in lib/api), when the
 *   server answers "not signed in", and when the signed-in user id changes.
 *   Entries older than PERSIST_MAX_AGE_MS are dropped on read. Total size is
 *   capped (PERSIST_MAX_CHARS) and the payload is versioned (an unknown
 *   version is discarded, never migrated).
 * - Policy check (2026-10-09, privacy-ko.md read-only): the policy's cookie
 *   section lists cookies (§8.1 "전부" refers to cookies) and mentions one
 *   local-storage use (§8.4) without claiming it is the only one; §2's
 *   "원본 파일은 저장하지 않습니다" covers import raw files, which are
 *   excluded here. No sentence says data is never kept on the user's device,
 *   so this does not contradict it. A one-line disclosure in §8 would still
 *   be more transparent — flagged for the policy owner, not edited here.
 *
 * Not in scope: the (dashboard) auth gate still waits for `/api/auth/me`,
 * because persisting identity is exactly what this module refuses to do. So
 * on a cold start the gain is "no second round-trip after auth", not "paint
 * before auth".
 */

import { useSyncExternalStore } from "react";
import type { Cache, Middleware, SWRConfiguration } from "swr";
import { API, PORTFOLIO_POSITIONS, PORTFOLIO_SUMMARY } from "./endpoints";

/** Bump when the stored shape changes. Old versions are deleted, not read. */
export const PERSIST_VERSION = 1;
export const PERSIST_STORAGE_PREFIX = "pq:swr-cache:";
/** ~300k UTF-16 chars ≈ 600 KB — well under the ~5 MB origin quota. */
export const PERSIST_MAX_CHARS = 300_000;
/** A week-old portfolio is a different portfolio; don't paint it. */
export const PERSIST_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;
/** Persisted data younger than this is not marked as old in the UI. */
export const STALE_AFTER_MS = 10 * 60 * 1000;
/** Coalesce bursts of successful fetches into one storage write. */
const FLUSH_DEBOUNCE_MS = 1_000;

export function persistStorageKey(uid: number): string {
  return `${PERSIST_STORAGE_PREFIX}v${PERSIST_VERSION}:u${uid}`;
}

/* ── Allowlist ───────────────────────────────────────────────────────── */

const EXACT_KEYS: ReadonlySet<string> = new Set([
  API.mirror.home,
  API.behavior.holdingMirror,
  API.behavior.concentrationMirror,
  API.behavior.profitLossMirror,
  API.behavior.turnoverMirror,
  API.behavior.averagingDownMirror,
  API.behavior.frictionOutcome,
  PORTFOLIO_SUMMARY,
  PORTFOLIO_POSITIONS,
]);

/** List endpoints persisted only in their plain `?limit=N` form (no filters). */
const LIMIT_ONLY_LISTS: ReadonlySet<string> = new Set([
  API.preTrade.list,
  API.observationNotes.list,
]);

/** Second line of defence: never persist these, whatever the allowlist says. */
const DENY_PREFIXES: readonly string[] = [
  "/api/auth",
  "/api/csrf",
  "/api/support",
  "/api/admin",
  "/api/portfolio/imports",
  "/api/profile",
  "/api/notifications",
];

export function isPersistableKey(key: unknown): key is string {
  if (typeof key !== "string" || !key.startsWith("/api/")) return false;
  if (DENY_PREFIXES.some((p) => key === p || key.startsWith(`${p}/`) || key.startsWith(`${p}?`))) {
    return false;
  }
  if (EXACT_KEYS.has(key)) return true;
  const q = key.indexOf("?");
  if (q < 0) return false;
  const path = key.slice(0, q);
  const query = key.slice(q + 1);
  if (LIMIT_ONLY_LISTS.has(path)) return /^limit=\d{1,4}$/.test(query);
  if (path === API.behavior.frictionOutcome) return /^period=[a-z0-9]{1,8}$/.test(query);
  return false;
}

/* ── Module state ────────────────────────────────────────────────────── */

interface Entry {
  /** epoch ms of the successful fetch that produced `data`. */
  at: number;
  data: unknown;
}

interface Payload {
  v: number;
  uid: number;
  entries: Record<string, Entry>;
}

export interface HydratedMeta {
  /** When the persisted response was originally fetched (epoch ms). */
  savedAt: number;
  /** When it was put back on screen (epoch ms). */
  hydratedAt: number;
  /** Age at the moment it was put back on screen. */
  ageAtHydrate: number;
  /** The exact object placed in the SWR cache (identity used for eviction). */
  data: unknown;
}

let activeUid: number | null = null;
/** The SWR cache the active user's data lives in (SWR's default cache). */
let activeCache: Cache | null = null;
let entries: Record<string, Entry> = {};
let flushTimer: ReturnType<typeof setTimeout> | null = null;
let lifecycleBound = false;
const hydrated = new Map<string, HydratedMeta>();
/**
 * Every object put back from storage this session. A restored value still
 * sitting in the cache is never re-captured as "live" — not when it is still
 * current (its stored timestamp must stand) and not after a fresh answer of
 * `null` removed it (it must not come back).
 */
let restored = new WeakSet<object>();
const listeners = new Set<() => void>();

function notify(): void {
  listeners.forEach((l) => l());
}

function storage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null; // privacy mode / blocked site data
  }
}

function ourStorageKeys(store: Storage): string[] {
  const keys: string[] = [];
  for (let i = 0; i < store.length; i += 1) {
    const k = store.key(i);
    if (k && k.startsWith(PERSIST_STORAGE_PREFIX)) keys.push(k);
  }
  return keys;
}

function removeStorageKeys(keep: string | null): void {
  const store = storage();
  if (!store) return;
  try {
    for (const k of ourStorageKeys(store)) if (k !== keep) store.removeItem(k);
  } catch {
    /* storage threw mid-iteration — nothing else to do */
  }
}

function readEntries(uid: number, now: number): Record<string, Entry> {
  const store = storage();
  if (!store) return {};
  let parsed: Partial<Payload> | null = null;
  try {
    const raw = store.getItem(persistStorageKey(uid));
    parsed = raw ? (JSON.parse(raw) as Partial<Payload>) : null;
  } catch {
    parsed = null;
  }
  if (!parsed || parsed.v !== PERSIST_VERSION || parsed.uid !== uid) return {};
  const out: Record<string, Entry> = {};
  for (const [key, e] of Object.entries(parsed.entries ?? {})) {
    const fresh = e && typeof e.at === "number" && now - e.at <= PERSIST_MAX_AGE_MS && e.at <= now;
    if (fresh && isPersistableKey(key) && e.data != null) out[key] = { at: e.at, data: e.data };
  }
  return out;
}

/** Drop every hydrated value still sitting untouched in the SWR cache. */
function evictHydrated(cache: Cache | undefined): void {
  if (cache) {
    hydrated.forEach((meta, key) => {
      if (cache.get(key)?.data === meta.data) cache.delete(key);
    });
  }
  hydrated.clear();
}

function bindLifecycle(): void {
  if (lifecycleBound || typeof window === "undefined") return;
  lifecycleBound = true;
  // A phone app is usually suspended, not closed: `visibilitychange` → hidden
  // is the last reliable moment to write.
  window.addEventListener("pagehide", () => flushPersistedCache());
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flushPersistedCache();
  });
}

/* ── Public API ──────────────────────────────────────────────────────── */

/**
 * Called once the server has said who is signed in. Puts that user's last
 * data into the SWR cache (only for keys the cache does not hold yet) and
 * deletes any other user's stored copy. Idempotent for the same user.
 */
export function activatePersistedCacheForUser(
  cache: Cache,
  uid: number,
  now: number = Date.now(),
): void {
  if (activeUid === uid) return;
  if (activeUid !== null) {
    // A different user on the same tab: nothing of the previous one may stay —
    // neither the restored copies nor anything fetched for them in memory
    // (flushPersistedCache reads the live cache, so it must not see them).
    evictHydrated(cache);
    for (const key of Array.from(cache.keys())) if (isPersistableKey(key)) cache.delete(key);
    restored = new WeakSet<object>();
    if (flushTimer) clearTimeout(flushTimer);
    flushTimer = null;
  }
  removeStorageKeys(persistStorageKey(uid));
  activeUid = uid;
  activeCache = cache;
  entries = readEntries(uid, now);
  for (const [key, e] of Object.entries(entries)) {
    if (cache.get(key)?.data !== undefined) continue; // a live value wins
    // isLoading/isValidating false: the screen has data, so no skeleton.
    cache.set(key, { data: e.data, isLoading: false, isValidating: false });
    if (typeof e.data === "object" && e.data !== null) restored.add(e.data);
    hydrated.set(key, {
      savedAt: e.at,
      hydratedAt: now,
      ageAtHydrate: Math.max(0, now - e.at),
      data: e.data,
    });
  }
  bindLifecycle();
  notify();
}

/** Logout / deletion request / "not signed in": remove everything. */
export function clearPersistedSwrCache(cache?: Cache): void {
  if (flushTimer) clearTimeout(flushTimer);
  flushTimer = null;
  activeUid = null;
  activeCache = null;
  entries = {};
  restored = new WeakSet<object>();
  evictHydrated(cache);
  removeStorageKeys(null);
  notify();
}

/**
 * Bring the persisted cache in line with an `/api/auth/me` answer. A signed-in
 * user activates their own copy; anything else wipes every copy.
 */
export function syncPersistedCacheIdentity(
  cache: Cache,
  me: { authenticated?: boolean; user?: { id?: unknown } | null } | null | undefined,
): void {
  const uid = me?.authenticated ? me.user?.id : undefined;
  if (typeof uid === "number" && Number.isFinite(uid)) {
    activatePersistedCacheForUser(cache, uid);
  } else {
    clearPersistedSwrCache(cache);
  }
}

/** A fetch for `key` succeeded: remember it and stop marking it as old. */
export function recordFetched(key: string, data: unknown, now: number = Date.now()): void {
  const wasHydrated = hydrated.delete(key);
  if (activeUid !== null && isPersistableKey(key)) {
    if (data == null) delete entries[key];
    else entries[key] = { at: now, data };
    if (!flushTimer) flushTimer = setTimeout(() => flushPersistedCache(), FLUSH_DEBOUNCE_MS);
  }
  if (wasHydrated) notify();
}

/**
 * Pick up values that reached the cache WITHOUT a fetch — `mutate(key, data)`
 * after a trade (portfolio refreshAll), realtime price pushes. They are what
 * the screen showed as current, so they are stamped "now". A value that is
 * still the restored copy is left with its original timestamp.
 */
function captureLiveValues(now: number): void {
  if (!activeCache) return;
  for (const key of Array.from(activeCache.keys())) {
    if (!isPersistableKey(key)) continue;
    const data = activeCache.get(key)?.data;
    if (data == null || data === entries[key]?.data) continue;
    if (typeof data === "object" && restored.has(data)) continue;
    entries[key] = { at: now, data };
  }
}

/** Write the current user's entries, newest first, within the size cap. */
export function flushPersistedCache(now: number = Date.now()): void {
  if (flushTimer) clearTimeout(flushTimer);
  flushTimer = null;
  const store = storage();
  if (activeUid === null || !store) return;
  captureLiveValues(now);
  const kept: Record<string, Entry> = {};
  let size = 0;
  const newestFirst = Object.entries(entries).sort((a, b) => b[1].at - a[1].at);
  for (const [key, e] of newestFirst) {
    let len: number;
    try {
      len = key.length + JSON.stringify(e).length;
    } catch {
      continue; // not serialisable — skip rather than break the write
    }
    if (size + len > PERSIST_MAX_CHARS) continue;
    kept[key] = e;
    size += len;
  }
  const storageKey = persistStorageKey(activeUid);
  try {
    store.setItem(
      storageKey,
      JSON.stringify({ v: PERSIST_VERSION, uid: activeUid, entries: kept } satisfies Payload),
    );
  } catch {
    // Quota or blocked storage: an unwritable cache must not leave a partial one.
    try {
      store.removeItem(storageKey);
    } catch {
      /* ignore */
    }
  }
}

/**
 * SWR middleware. For allowlisted keys it (a) records every successful fetch
 * and (b) forces one revalidation on mount while the value on screen came
 * from storage — some hooks set `revalidateIfStale: false` (portfolio), which
 * would otherwise leave persisted data unrefreshed until their next poll.
 */
export const persistedCacheMiddleware: Middleware = (next) => (key, fetcher, config) => {
  if (!isPersistableKey(key)) return next(key, fetcher, config);
  const ownOnSuccess = config.onSuccess;
  const onSuccess: SWRConfiguration["onSuccess"] = (data, k, c) => {
    recordFetched(key, data);
    ownOnSuccess?.(data, k, c);
  };
  const extra = hydrated.has(key) ? { revalidateOnMount: true } : {};
  return next(key, fetcher, { ...config, ...extra, onSuccess });
};

/* ── Staleness hook ──────────────────────────────────────────────────── */

export interface Staleness {
  /** When the data on screen was fetched, while it is still the stored copy. */
  syncedAt: Date | null;
  /** True only when the stored copy is older than STALE_AFTER_MS. */
  isStale: boolean;
  /** `syncedAt` fell on the same local calendar day the copy was shown. */
  sameDay: boolean;
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
};

/**
 * Is `key` currently showing a persisted copy, and is that copy old enough to
 * say so? Clears itself the moment a fresh fetch for `key` lands.
 */
export function useStaleness(key: string = API.mirror.home): Staleness {
  const meta = useSyncExternalStore(
    subscribe,
    () => hydrated.get(key) ?? null,
    () => null,
  );
  if (!meta) return { syncedAt: null, isStale: false, sameDay: false };
  const saved = new Date(meta.savedAt);
  return {
    syncedAt: saved,
    isStale: meta.ageAtHydrate >= STALE_AFTER_MS,
    sameDay: saved.toDateString() === new Date(meta.hydratedAt).toDateString(),
  };
}

/** Test-only: reset module state between cases. */
export function __resetPersistedCacheForTests(): void {
  if (flushTimer) clearTimeout(flushTimer);
  flushTimer = null;
  activeUid = null;
  activeCache = null;
  entries = {};
  restored = new WeakSet<object>();
  hydrated.clear();
  listeners.clear();
}
