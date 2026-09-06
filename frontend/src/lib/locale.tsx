"use client";

/**
 * Locale / i18n Provider
 *
 * Lightweight custom provider — same key structure as next-intl so migration
 * is a drop-in replacement later.
 *
 * Supported locales: "ko" (default) | "en"
 * Persistence: cookie "sp_locale" (1-year TTL)
 * Detection: cookie → Accept-Language header is checked server-side in
 *            middleware.ts; on the client we read the cookie directly.
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import ko from "@/messages/ko.json";
import { API } from "@/lib/endpoints";
import en from "@/messages/en.json";

// ─── Types ────────────────────────────────────────────────────────────────────

export type Locale = "ko" | "en";

type Messages = typeof ko; // structural type; en must match the same shape

interface LocaleContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string, params?: Record<string, string>) => string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const MESSAGES: Record<Locale, Messages> = { ko, en };
const COOKIE_NAME = "sp_locale";
const COOKIE_MAX_AGE = 60 * 60 * 24 * 365; // 1 year

function readLocaleCookie(): Locale | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(
    new RegExp("(?:^|; )" + COOKIE_NAME + "=([^;]*)"),
  );
  if (!match) return null;
  const val = decodeURIComponent(match[1]);
  return val === "en" || val === "ko" ? val : null;
}

function writeLocaleCookie(locale: Locale): void {
  if (typeof document === "undefined") return;
  // Add `Secure` flag in production (HTTPS-only) so the locale cookie cannot
  // leak over plaintext channels. Skip in development since localhost runs
  // over HTTP and `Secure` would silently drop the cookie.
  const secure =
    process.env.NODE_ENV === "production" ? "; Secure" : "";
  document.cookie = `${COOKIE_NAME}=${locale}; path=/; max-age=${COOKIE_MAX_AGE}; SameSite=Lax${secure}`;
}

/**
 * Resolve a dot-notation key against a nested messages object.
 * Returns the key itself if not found (safe fallback, no crash).
 */
function resolve(messages: Messages, key: string): string {
  const parts = key.split(".");
  // Walk the nested messages tree. `unknown` (not `any`) forces the
  // object/string type guards below to narrow on each step.
  let node: unknown = messages;
  for (const part of parts) {
    if (node == null || typeof node !== "object") return key;
    node = (node as Record<string, unknown>)[part];
  }
  return typeof node === "string" ? node : key;
}

function interpolate(template: string, params?: Record<string, string>): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (_, k) => params[k] ?? `{${k}}`);
}

// ─── Context ──────────────────────────────────────────────────────────────────

const LocaleContext = createContext<LocaleContextValue>({
  locale: "ko",
  setLocale: () => {},
  t: (key) => key,
});

// ─── Provider ─────────────────────────────────────────────────────────────────

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => {
    // Server-side: default to "ko"; hydration will sync to cookie value
    return "ko";
  });

  /* Sync to cookie on mount (client only) */
  useEffect(() => {
    const saved = readLocaleCookie();
    if (saved && saved !== locale) {
      setLocaleState(saved);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    writeLocaleCookie(next);
    // Wave F (2026-05-28) — fire-and-forget backend sync so logged-in users
    // get the same locale on subsequent scheduled emails / PDF generation.
    // Anonymous users get a 401 which is silently ignored (cookie is still
    // the source of truth for them). Never await — never block the UI on
    // this. credentials:"include" carries the session cookie.
    if (typeof window !== "undefined") {
      try {
        void fetch(API.profile.locale, {
          method: "PUT",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ locale: next }),
        }).catch(() => {
          /* silent — cookie is the immediate source of truth */
        });
      } catch {
        /* never throw from setLocale */
      }
    }
  }, []);

  const t = useCallback(
    (key: string, params?: Record<string, string>) => {
      const raw = resolve(MESSAGES[locale], key);
      return interpolate(raw, params);
    },
    [locale],
  );

  return (
    <LocaleContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </LocaleContext.Provider>
  );
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useLocale() {
  return useContext(LocaleContext);
}

/**
 * Convenience alias — mirrors next-intl's useTranslations() API.
 * Usage: const t = useT(); t("nav.home")
 */
export function useT() {
  return useContext(LocaleContext).t;
}
