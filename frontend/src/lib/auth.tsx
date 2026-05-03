"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { apiFetch } from "./api";
import { API } from "./endpoints";

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
  onboarding_completed?: boolean;
}

interface AuthCtx {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, name?: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    // 2026-05-02: Railway cold-start could push /api/auth/me to ~10s on
    // the first call after idle, exceeding the implicit Vercel proxy
    // window and leaving the SPA stuck on its loading splash forever.
    // Hard-cap the auth probe at 8s so the UI always unblocks — a
    // timeout means "treat as unauthenticated for now"; the next 5-min
    // refresh will pick up the warm-cache response when Railway is up.
    const ctrl = new AbortController();
    const timeoutId = setTimeout(() => ctrl.abort(), 8000);
    try {
      const data = await apiFetch<{ authenticated: boolean; user?: User }>(
        API.auth.me,
        { signal: ctrl.signal },
      );
      setUser(data.authenticated ? (data.user ?? null) : null);
    } catch {
      setUser(null);
    } finally {
      clearTimeout(timeoutId);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 5 * 60 * 1000); // Refresh session every 5 min
    return () => clearInterval(interval);
  }, [refresh]);

  const login = useCallback(
    async (email: string, password: string) => {
      await apiFetch(API.auth.login, {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      await refresh();
    },
    [refresh],
  );

  const signup = useCallback(
    async (email: string, password: string, name?: string) => {
      await apiFetch(API.auth.register, {
        method: "POST",
        body: JSON.stringify({ email, password, name }),
      });
      await refresh();
    },
    [refresh],
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
      setUser(null);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
