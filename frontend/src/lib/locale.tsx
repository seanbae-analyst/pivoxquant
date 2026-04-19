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
  document.cookie = `${COOKIE_NAME}=${locale}; path=/; max-age=${COOKIE_MAX_AGE}; SameSite=Lax`;
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
