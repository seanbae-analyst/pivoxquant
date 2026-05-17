"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import useSWR from "swr";
import { apiFetch } from "./api";
import { API } from "./endpoints";
import { clearHadSession, markHadSession } from "./had-session";

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
   * PIPA §22 ⑥ — true iff the User row has ``birthdate IS NULL``.
   * Set by ``services/serializers.py serialize_user``. New OAuth sign-ups
   * and legacy pre-migration-031 accounts both reach the dashboard with
   * this flag true; the protected layout must redirect them through
   * ``/signup/oauth-finalize`` before any other route renders.
   */
  birthdate_required?: boolean;
}

interface AuthCtx {
  user: User | null;
  loading: boolean;
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
// Hard-cap the auth probe at 8s so the UI always unblocks — a
// timeout means "treat as unauthenticated for now"; the next 5-min
// refresh will pick up the warm-cache response when Railway is up.
const meFetcher = async (url: string): Promise<MeResponse> => {
  const ctrl = new AbortController();
  const timeoutId = setTimeout(() => ctrl.abort(), 8000);
  try {
    return await apiFetch<MeResponse>(url, { signal: ctrl.signal });
  } catch {
    // Treat any failure (timeout / network / 401) as unauthenticated so the
    // UI shell unblocks. A subsequent refresh will pick up the real state.
    return { authenticated: false };
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
  const { data, isLoading, mutate } = useSWR<MeResponse>(
    API.auth.me,
    meFetcher,
    {
      refreshInterval: 5 * 60 * 1000, // 5 min — matches prior cadence
      dedupingInterval: 60 * 1000, // collapse duplicate calls within 60s
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      errorRetryCount: 2,
      // The fetcher already converts errors to { authenticated: false } so
      // SWR will not retry-storm on auth failures.
    },
  );

  // Local override for logout — clears the user immediately without waiting
  // for the network round-trip, mirroring the previous setUser(null) behavior.
  const [logoutPending, setLogoutPending] = useState(false);

  const user: User | null = logoutPending
    ? null
    : data?.authenticated
      ? (data.user ?? null)
      : null;

  // Match prior semantics: loading is true only on the very first fetch.
  const loading = isLoading && !data;

  // Track "this browser has held a session" so apiFetch can disambiguate
  // a real expiry from a fresh-guest 401 when redirecting to /login.
  // See lib/had-session.ts and the SESSION_EXPIRED branch in lib/api.ts.
  useEffect(() => {
    if (user) markHadSession();
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
        console.warn("logout request failed (clearing local state anyway):", err);
      }
    } finally {
      setLogoutPending(true);
      // Clear the "had session" marker so the next 401 on this device is
      // treated as a fresh-guest 401 (no /login?expired=1 banner).
      clearHadSession();
      // Force the SWR cache to drop the authenticated payload so any
      // subsequent revalidation reflects the logged-out state.
      await mutate({ authenticated: false }, { revalidate: false });
    }
  }, [mutate]);

  const value = useMemo<AuthCtx>(
    () => ({ user, loading, login, signup, logout, refresh }),
    [user, loading, login, signup, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
