"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import useSWR, { useSWRConfig, type SWRConfiguration } from "swr";
import { apiFetch, ApiError } from "./api";
import { API } from "./endpoints";
import { clearHadSession, markHadSession } from "./had-session";
import { isDemoMode, DEMO_USER } from "./demo";
import {
  clearPersistedSwrCache,
  syncPersistedCacheIdentity,
} from "./persisted-swr-cache";
import { useAuthWakePoll } from "./auth-wake";

// PIPA: drop the service-worker API_CACHE so per-user SWR endpoints
// (/api/profile, /api/earnings, /api/discover — cached by URL only with
// multi-minute windows) cannot leak one user's payload to the next on a
// shared device. Must run on login/signup too, not just logout: a session
// can expire without an explicit logout, after which a different user signs
// in and would otherwise see the previous user's cached first render.
// Best-effort — never throw if the SW is unavailable.
function clearSwApiCache(): void {
  try {
    if (
      typeof navigator !== "undefined" &&
      navigator.serviceWorker?.controller
    ) {
      navigator.serviceWorker.controller.postMessage({
        type: "CLEAR_API_CACHE",
      });
    }
  } catch {
    // SW not controlling this page yet / messaging unsupported — ignore.
  }
}

export interface User {
  id: number;
  email: string;
  name: string;
  available_capital: number;
  available_capital_krw: number;
  avatar_url?: string | null;
  oauth_provider?: string | null;
  risk_profile?: string;
  profile_changes_left?: number;
  subscription_tier?: string;
  /**
   * 2026-05-17 (wave 12 P1): backend serializer emits these three fields
   * but the User interface never declared them. Adding so callers that
   * read `user.effective_tier` / `user.subscription_status` /
   * `user.raw_subscription_status` type-check correctly and don't fall
   * back to undefined → FREE gate silently. Same drift class as the
   * SubscriptionResponse fix in PR #416. See
   * `services/serializers.py:serialize_user`.
   */
  effective_tier?: string;
  subscription_status?: string;
  raw_subscription_status?: string;
  onboarding_completed?: boolean;
  /**
   * PIPA §22 ⑥ — true until the user has self-declared that they are 14
   * or older (``users.age_confirmed_at IS NULL``). Set by
   * ``services/serializers.py serialize_user``. 2026-09-19: the product
   * stopped collecting a birthdate — the gate is the required ``age``
   * consent sent to ``/api/auth/oauth-finalize``. New OAuth sign-ups reach
   * the dashboard with this flag true; the protected layout must redirect
   * them through ``/signup/oauth-finalize`` before any other route
   * renders. Read it through ``ageConfirmationRequired()`` below.
   */
  age_confirmation_required?: boolean;
  /**
   * @deprecated 2026-09-19 — same value as ``age_confirmation_required``,
   * emitted by the backend for one deploy cycle and then removed. Do not
   * read it directly; ``ageConfirmationRequired()`` handles the fallback.
   */
  birthdate_required?: boolean;
  /**
   * PIPA §28-8 — true once a cross-border consent has been recorded
   * server-side (``users.cross_border_consent_at`` set; a later revocation
   * does not flip it back). Read through ``serverHasRequiredConsents()`` in
   * ``@/lib/consents`` — onboarding and the (dashboard) consent flush use it
   * instead of the localStorage snapshot (2026-09-29).
   */
  cross_border_consent_recorded?: boolean;
}

/**
 * PIPA §22 ⑥ gate — the one place the (dashboard) layout and the
 * ``/signup/oauth-finalize`` interstitial read during the deploy window in
 * which the backend emits both ``age_confirmation_required`` and the
 * deprecated ``birthdate_required``. Missing on both → not required
 * (legacy / demo users).
 */
export function ageConfirmationRequired(
  user:
    | Pick<User, "age_confirmation_required" | "birthdate_required">
    | null
    | undefined,
): boolean {
  if (!user) return false;
  return user.age_confirmation_required ?? user.birthdate_required ?? false;
}

interface AuthCtx {
  user: User | null;
  /**
   * True only until the FIRST auth probe has settled (an answer or an
   * error). It never flips back to true on a retry — see `authSettled`.
   */
  loading: boolean;
  /**
   * Auth state UNKNOWN: the probe has never been answered and its last
   * attempt failed with "could not reach / could not ask the server"
   * (AuthUnknownError — a cold backend, a timeout, a 5xx, a 429). `user` is
   * null here but that is not "signed out": guards must hold, not redirect
   * to /login. Cleared by the first real answer.
   */
  waking: boolean;
  /** `waking` and the wake poll passed its deadline (show error + retry). */
  wakeFailed: boolean;
  /** Restart the wake poll and re-run the auth probe now. */
  retryAuth: () => void;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, name?: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

interface MeResponse {
  authenticated: boolean;
  user?: User;
}

const AuthContext = createContext<AuthCtx | null>(null);

// 2026-05-02: Railway cold-start could push /api/auth/me to ~10s on
// the first call after idle, exceeding the implicit Vercel proxy
// window and leaving the SPA stuck on its loading splash forever.
// Hard-cap the auth probe at 8s so the UI always unblocks.
//
// 2026-09-01: the catch used to answer EVERY failure with
// `{ authenticated: false }`. That conflates two different facts — "the
// server says you are not signed in" and "we could not reach the server" —
// and the second one is not something we know. A single 429, a timeout, or
// a 502 mid-session made the dashboard guard read `user == null` and bounce
// a signed-in user to /login; the login page then saw the next (successful)
// probe, bounced them back, and the two guards ping-ponged. Reproduced
// locally by exhausting the backend's 100/min limit: /login and /portfolio
// alternated indefinitely and the app never painted.
//
// Now only a real 401/403 asserts "signed out". Anything else rethrows, and
// SWR keeps the last known response — so a transient blip is invisible
// instead of logging the user out. On a cold start there is no previous
// response to keep, so `data` stays undefined and the shell renders its
// unauthenticated branch exactly as before.
export class AuthUnknownError extends Error {
  /** HTTP status when the server answered at all; undefined = no answer. */
  readonly status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.status = status;
  }
}

/**
 * A failure that a sleeping Render backend produces while it boots: no
 * answer at all (network error, our 8 s abort) or a 5xx/408 from the router.
 * 429 and other 4xx are NOT this — retrying those fast would only add load.
 */
export function isColdStartAuthError(err: unknown): boolean {
  if (!(err instanceof AuthUnknownError)) return false;
  const s = err.status;
  return s === undefined || s === 408 || s >= 500;
}

/**
 * Wake retry cadence for the auth probe (2026-10-09). The previous policy —
 * SWR's default `errorRetryCount: 2` with exponential backoff — made its
 * last attempt at roughly 31–41 s and then went quiet until the 5-minute
 * refresh. A cold start is ~44 s (keep-warm.yml), so the probe routinely
 * gave up just before the server came up. Now: a fixed short gap while the
 * failure looks like a boot, for longer than the wake deadline the login
 * button uses (lib/backend-wake WAKE_DEADLINE_MS = 75 s):
 *   8 retries × (≤ 8 s probe + 3 s gap) ≈ 88 s.
 */
export const AUTH_WAKE_RETRY_MS = 3_000;
export const AUTH_WAKE_MAX_RETRIES = 8;
/** Non-boot failures (e.g. 429): the old budget — 2 retries, backoff. */
const AUTH_OTHER_MAX_RETRIES = 2;
const AUTH_OTHER_RETRY_BASE_MS = 5_000;

export const authErrorRetry: NonNullable<SWRConfiguration["onErrorRetry"]> = (
  err,
  _key,
  _config,
  revalidate,
  { retryCount },
) => {
  if (isColdStartAuthError(err)) {
    if (retryCount > AUTH_WAKE_MAX_RETRIES) return;
    setTimeout(() => void revalidate({ retryCount }), AUTH_WAKE_RETRY_MS);
    return;
  }
  if (retryCount > AUTH_OTHER_MAX_RETRIES) return;
  const delay = AUTH_OTHER_RETRY_BASE_MS * 2 ** Math.max(0, retryCount - 1);
  setTimeout(() => void revalidate({ retryCount }), delay);
};

export const meFetcher = async (url: string): Promise<MeResponse> => {
  const ctrl = new AbortController();
  const timeoutId = setTimeout(() => ctrl.abort(), 8000);
  try {
    return await apiFetch<MeResponse>(url, { signal: ctrl.signal });
  } catch (err) {
    if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
      return { authenticated: false };
    }
    throw new AuthUnknownError(
      err instanceof Error ? err.message : "auth probe failed",
      err instanceof ApiError ? err.status : undefined,
    );
  } finally {
    clearTimeout(timeoutId);
  }
};

export function AuthProvider({ children }: { children: React.ReactNode }) {
  // 2026-05-03: P1 fix — replace raw setInterval(refresh, 5min) with useSWR.
  // React Strict Mode double-mounts the provider, which doubled the raw
  // setInterval and produced the "7x duplicate /api/auth/me" pattern flagged
  // by verify-ux. SWR dedupes concurrent in-flight requests and respects
  // refreshInterval/dedupingInterval globally per cache key.
  // Global SWR mutate — used on logout to evict every other per-user cache
  // key (the bound `mutate` below only clears the auth.me key). `cache` is
  // SWR's default cache, the one lib/persisted-swr-cache hydrates.
  const { mutate: globalMutate, cache } = useSWRConfig();

  // The persisted screen cache follows the SERVER's answer about identity:
  // it is put back only after /me names the same user id it was saved for,
  // and wiped when /me says "not signed in". Running this inside the fetcher
  // means it happens before SWR commits the answer, i.e. before any
  // (dashboard) page mounts and reads the cache. Demo mode never persists.
  const fetchMe = useCallback(
    async (url: string): Promise<MeResponse> => {
      const res = await meFetcher(url);
      if (!isDemoMode()) syncPersistedCacheIdentity(cache, res);
      return res;
    },
    [cache],
  );

  const { data, error, mutate } = useSWR<MeResponse>(API.auth.me, fetchMe, {
    refreshInterval: 5 * 60 * 1000, // 5 min — matches prior cadence
    dedupingInterval: 60 * 1000, // collapse duplicate calls within 60s
    revalidateOnFocus: false,
    revalidateOnReconnect: true,
    errorRetryCount: AUTH_WAKE_MAX_RETRIES,
    onErrorRetry: authErrorRetry,
    // keepPreviousData is what makes an unreachable backend a no-op rather
    // than a logout: on an AuthUnknownError SWR surfaces the error but
    // leaves `data` at the last good response.
    keepPreviousData: true,
  });

  // Local override for logout — clears the user immediately without waiting
  // for the network round-trip, mirroring the previous setUser(null) behavior.
  const [logoutPending, setLogoutPending] = useState(false);

  // DEMO mode (portfolio showcase): inject a fixed user so the dashboard renders
  // with no login. Flag-gated — a no-op when the env var is unset.
  //
  // Render the authenticated shell CLIENT-ONLY: stay "loading" until mounted, so
  // SSR emits the skeleton — exactly like the real app's unauthenticated SSR.
  // Rendering authenticated content on the SERVER would bake in server-timezone
  // dates (Vercel = UTC) that mismatch the viewer's client (KST / any TZ) on
  // hydration → React #418 → hydration aborts → SWR never runs → data frozen.
  // Deferring to post-mount makes SSR + the first client render both the
  // skeleton, so hydration matches and the data then fills client-side.
  const demo = isDemoMode();
  const [demoMounted, setDemoMounted] = useState(false);
  useEffect(() => {
    if (demo) setDemoMounted(true);
  }, [demo]);

  const user: User | null = demo
    ? demoMounted
      ? DEMO_USER
      : null
    : logoutPending
      ? null
      : data?.authenticated
        ? (data.user ?? null)
        : null;

  // `loading` is true only until the first probe SETTLES, and latches there.
  //
  // 2026-10-09 wake-state fix: this used to be `isLoading && !data`. SWR sets
  // `isLoading` back to true at the start of EVERY retry while there is no
  // data (swr/dist/index: `if (isUndefined(getCache().data))
  // initialState.isLoading = true`). On a cold backend the probe fails and
  // retries, so `loading` went true → false → true… and /login swapped its
  // OAuth card for the skeleton on each retry. That unmounted <OAuthButtonsV2>
  // mid-wake: its "서버를 깨우는 중" note and "다시 시도" button vanished, and
  // its wake loop was aborted by the unmount cleanup, so a click made during
  // a gap never navigated. Once the first answer or error is in, later
  // retries change `waking`, never `loading`. (State updated during render
  // is React's documented "adjust state on prop change" pattern.)
  const settledNow = data !== undefined || error !== undefined;
  const [authSettled, setAuthSettled] = useState(settledNow);
  if (settledNow && !authSettled) setAuthSettled(true);
  // In demo mode, stay loading until mounted so the authenticated shell is
  // client-only.
  const loading = demo ? !demoMounted : !(authSettled || settledNow);
  const waking =
    !demo && !logoutPending && data === undefined && error instanceof AuthUnknownError;

  // While unknown: poll /api/health every 2 s and re-run this probe the moment
  // the backend answers, instead of waiting out the probe's own retry timer
  // (lib/auth-wake.ts has the measured numbers).
  const revalidateMe = useCallback(() => mutate(), [mutate]);
  const { gaveUp: wakeFailed, retry: retryAuth } = useAuthWakePoll(waking, revalidateMe);

  // Track "this browser has held a session" so apiFetch can disambiguate
  // a real expiry from a fresh-guest 401 when redirecting to /login.
  // See lib/had-session.ts and the SESSION_EXPIRED branch in lib/api.ts.
  //
  // Wave-3 P2 (2026-06-10): also clear the service-worker API cache whenever
  // the authenticated user ID CHANGES. The password login() below already
  // clears, but prod auth is OAuth (full-page redirect) which never calls
  // login() — so User B logging in after User A's session expired (no
  // explicit logout) could be served A's SW-cached /api/profile* responses
  // for up to 60min. The SWR in-memory cache resets with the redirect; the
  // SW disk cache is the one that must be evicted here.
  const prevUserIdRef = useRef<number | null>(null);
  useEffect(() => {
    if (user) {
      markHadSession();
      if (prevUserIdRef.current !== null && prevUserIdRef.current !== user.id) {
        clearSwApiCache();
      }
      prevUserIdRef.current = user.id;
    }
  }, [user]);

  const refresh = useCallback(async () => {
    await mutate();
  }, [mutate]);

  const login = useCallback(
    async (email: string, password: string) => {
      await apiFetch(API.auth.login, {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      clearSwApiCache();
      setLogoutPending(false);
      await mutate();
    },
    [mutate],
  );

  const signup = useCallback(
    async (email: string, password: string, name?: string) => {
      await apiFetch(API.auth.register, {
        method: "POST",
        body: JSON.stringify({ email, password, name }),
      });
      clearSwApiCache();
      setLogoutPending(false);
      await mutate();
    },
    [mutate],
  );

  const logout = useCallback(async () => {
    // Logout is idempotent server-side and must never leave the user stuck.
    // Even if the network request fails (offline, 5xx), we clear local
    // auth state so the UI transitions to the logged-out shell — the
    // session cookie will be rejected on the next authenticated call.
    try {
      await apiFetch(API.auth.logout, { method: "POST" });
    } catch (err) {
      // Swallow logout errors — user intent is clear, and the server-side
      // session will either already be gone or expire naturally.
      // P3 (wave1-critical): only surface the warning in non-production
      // to keep end-user consoles clean. Local state is cleared either way.
      if (
        typeof console !== "undefined" &&
        process.env.NODE_ENV !== "production"
      ) {
        console.warn(
          "logout request failed (clearing local state anyway):",
          err,
        );
      }
    } finally {
      setLogoutPending(true);
      // Clear the "had session" marker so the next 401 on this device is
      // treated as a fresh-guest 401 (no /login?expired=1 banner).
      clearHadSession();
      // Force the SWR cache to drop the authenticated payload so any
      // subsequent revalidation reflects the logged-out state.
      await mutate({ authenticated: false }, { revalidate: false });
      // Evict every OTHER per-user SWR key (portfolio, watchlist, signals,
      // risk…). The bound mutate above clears only auth.me and clearSwApiCache
      // only clears the service-worker HTTP cache — the in-memory SWR store
      // survived, so a different user signing in on this device could see the
      // previous user's data on first paint (no full reload on OAuth switch).
      await globalMutate((key) => key !== API.auth.me, undefined, {
        revalidate: false,
      });
      clearSwApiCache();
      // The on-device copy of the screens (lib/persisted-swr-cache) goes too.
      clearPersistedSwrCache(cache);
    }
  }, [mutate, globalMutate, cache]);

  const value = useMemo<AuthCtx>(
    () => ({
      user,
      loading,
      waking,
      wakeFailed: waking && wakeFailed,
      retryAuth,
      login,
      signup,
      logout,
      refresh,
    }),
    [user, loading, waking, wakeFailed, retryAuth, login, signup, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
