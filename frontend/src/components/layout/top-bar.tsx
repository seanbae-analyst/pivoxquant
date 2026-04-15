"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Search,
  Bell,
  ChevronDown,
  X,
  Settings,
  LogOut,
  ExternalLink,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { cn } from "@/lib/utils";
import { fmtPct } from "@/lib/format";
import type { AlertItem, LookupResult } from "@/lib/types";
import { ModalShell } from "@/components/ui/modal-shell";
import { useT } from "@/lib/locale";
import { LanguageToggle } from "@/components/ui/language-toggle";

/* ─────────────────────── helpers ─────────────────────── */

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function alertTypeIcon(type: string): string {
  switch (type) {
    case "price":
      return "$";
    case "signal":
      return "S";
    case "risk":
      return "!";
    case "trade":
      return "T";
    default:
      return "N";
  }
}

/* ─────────────────── click-outside hook ────────────────── */

function useClickOutside(
  ref: React.RefObject<HTMLElement | null>,
  handler: () => void,
) {
  useEffect(() => {
    function onMouseDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        handler();
      }
    }
    document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, [ref, handler]);
}

/* ═══════════════════════ TopBar ═══════════════════════ */

export function TopBar() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const t = useT();
  const [isMac, setIsMac] = useState(false);

  /* ── detect platform ── */
  useEffect(() => {
    setIsMac(
      typeof navigator !== "undefined" && /mac/i.test(navigator.userAgent),
    );
  }, []);

  /* ── initials ── */
  const initials = user?.name
    ? user.name
        .split(" ")
        .map((w) => w[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "SP";

  /* ───────────── Search Command Palette ───────────── */
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<LookupResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const openSearch = useCallback(() => {
    setSearchOpen(true);
    setSearchQuery("");
    setSearchResults([]);
  }, []);

  const closeSearch = useCallback(() => {
    setSearchOpen(false);
    setSearchQuery("");
    setSearchResults([]);
  }, []);

  /* Cmd/Ctrl+K shortcut */
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setSearchOpen((prev) => {
          if (prev) return false;
          setSearchQuery("");
          setSearchResults([]);
          return true;
        });
      }
      if (e.key === "Escape" && searchOpen) {
        closeSearch();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [searchOpen, closeSearch]);

  /* auto-focus input when opened */
  useEffect(() => {
    if (searchOpen) {
      requestAnimationFrame(() => searchInputRef.current?.focus());
    }
  }, [searchOpen]);

  /* debounced search */
  useEffect(() => {
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);

    const q = searchQuery.trim();
    if (!q) {
      setSearchResults([]);
      setSearchLoading(false);
      return;
    }

    setSearchLoading(true);
    searchTimerRef.current = setTimeout(async () => {
      try {
        const data = await apiFetch<LookupResult>(
          `/api/lookup/${encodeURIComponent(q)}`,
        );
        setSearchResults(data ? [data] : []);
      } catch {
        setSearchResults([]);
      } finally {
        setSearchLoading(false);
      }
    }, 350);

    return () => {
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    };
  }, [searchQuery]);

  function handleResultClick(ticker: string) {
    closeSearch();
    router.push(`/detail/${ticker}`);
  }

  /* ───────────── Notification Bell ───────────── */
  const [bellOpen, setBellOpen] = useState(false);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [alertsLoading, setAlertsLoading] = useState(false);
  const bellRef = useRef<HTMLDivElement | null>(null);

  const unreadCount = alerts.filter((a) => !a.is_read).length;

  const fetchAlerts = useCallback(async () => {
    setAlertsLoading(true);
    try {
      const data = await apiFetch<{ alerts: AlertItem[] }>(API.alerts.list);
      setAlerts(data.alerts ?? []);
    } catch {
      setAlerts([]);
    } finally {
      setAlertsLoading(false);
    }
  }, []);

  function toggleBell() {
    const next = !bellOpen;
    setBellOpen(next);
    setProfileOpen(false);
    if (next) fetchAlerts();
  }

  async function markAllRead() {
    try {
      await apiFetch(API.alerts.read, { method: "POST" });
      setAlerts((prev) => prev.map((a) => ({ ...a, is_read: true })));
    } catch {
      /* silent */
    }
  }

  useClickOutside(bellRef, () => setBellOpen(false));

  /* ───────────── Profile Dropdown ───────────── */
  const [profileOpen, setProfileOpen] = useState(false);
  const profileRef = useRef<HTMLDivElement | null>(null);

  function toggleProfile() {
    setProfileOpen((prev) => !prev);
    setBellOpen(false);
  }

  async function handleLogout() {
    setProfileOpen(false);
    await logout();
    router.push("/");
  }

  useClickOutside(profileRef, () => setProfileOpen(false));

  /* ═══════════════════════ Render ═══════════════════════ */

  return (
    <>
      <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-4 md:px-6">
        {/* ── Search bar trigger ── */}
        <button
          className="flex h-10 w-full max-w-md items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 text-sm text-slate-400 transition-colors duration-200 hover:border-slate-300 hover:bg-white"
          onClick={openSearch}
          type="button"
        >
          <Search className="h-4 w-4 shrink-0" />
          <span className="flex-1 text-left">{t("topbar.searchPlaceholder")}</span>
          <kbd className="hidden rounded-md border border-slate-200 bg-white px-1.5 py-0.5 text-[11px] font-medium text-slate-400 sm:inline-block">
            {isMac ? "\u2318" : "Ctrl+"}K
          </kbd>
        </button>

        {/* ── Right side ── */}
        <div className="ml-4 flex items-center gap-2">
          {/* Language Toggle */}
          <LanguageToggle />

          {/* Notifications */}
          <div ref={bellRef} className="relative">
            <button
              className="relative flex h-10 w-10 items-center justify-center rounded-xl text-slate-500 transition-colors duration-200 hover:bg-slate-100 hover:text-slate-700"
              type="button"
              onClick={toggleBell}
            >
              <Bell className="h-[18px] w-[18px]" />
              {unreadCount > 0 && (
                <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-red-500" />
              )}
              <span className="sr-only">{t("topbar.notifications")}</span>
            </button>

            {/* Bell dropdown */}
            {bellOpen && (
              <div className="sp-card absolute right-0 top-full z-50 mt-2 w-80 rounded-xl border border-slate-200 bg-white shadow-lg">
                <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
                  <h3 className="text-sm font-semibold text-slate-900">
                    {t("topbar.notifications")}
                  </h3>
                  {unreadCount > 0 && (
                    <button
                      onClick={markAllRead}
                      className="text-xs font-medium text-purple-600 transition-colors hover:text-purple-800"
                      type="button"
                    >
                      {t("topbar.markAllRead")}
                    </button>
                  )}
                </div>

                <div className="max-h-80 overflow-y-auto">
                  {alertsLoading ? (
                    <div className="px-4 py-8 text-center text-sm text-slate-400">
                      {t("topbar.loading")}
                    </div>
                  ) : alerts.length === 0 ? (
                    <div className="px-4 py-8 text-center text-sm text-slate-400">
                      {t("topbar.noNotifications")}
                    </div>
                  ) : (
                    alerts.map((alert) => (
                      <button
                        key={alert.id}
                        className={cn(
                          "flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-slate-50",
                          !alert.is_read && "bg-purple-50/50",
                        )}
                        type="button"
                        onClick={() => {
                          if (alert.ticker) {
                            setBellOpen(false);
                            router.push(`/detail/${alert.ticker}`);
                          }
                        }}
                      >
                        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-xs font-bold text-slate-600">
                          {alertTypeIcon(alert.type)}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p
                            className={cn(
                              "text-sm leading-snug",
                              alert.is_read
                                ? "text-slate-500"
                                : "font-medium text-slate-900",
                            )}
                          >
                            {alert.message}
                          </p>
                          <p className="mt-0.5 text-xs text-slate-400">
                            {timeAgo(alert.created_at)}
                          </p>
                        </div>
                        {!alert.is_read && (
                          <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-purple-500" />
                        )}
                      </button>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Avatar / Profile */}
          <div ref={profileRef} className="relative">
            <button
              className="flex items-center gap-2 rounded-xl py-1 pl-1 pr-2 transition-colors duration-200 hover:bg-slate-100"
              type="button"
              onClick={toggleProfile}
            >
              {user?.avatar_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={user.avatar_url}
                  alt={user.name || "User"}
                  className="h-8 w-8 rounded-lg object-cover"
                />
              ) : (
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-100 text-xs font-bold text-purple-700">
                  {initials}
                </div>
              )}
              <ChevronDown
                className={cn(
                  "hidden h-3.5 w-3.5 text-slate-400 transition-transform sm:block",
                  profileOpen && "rotate-180",
                )}
              />
            </button>

            {/* Profile dropdown */}
            {profileOpen && (
              <div className="sp-card absolute right-0 top-full z-50 mt-2 w-56 rounded-xl border border-slate-200 bg-white shadow-lg">
                {/* User info */}
                <div className="border-b border-slate-100 px-4 py-3">
                  <p className="truncate text-sm font-semibold text-slate-900">
                    {user?.name || "User"}
                  </p>
                  <p className="truncate text-xs text-slate-400">
                    {user?.email}
                  </p>
                </div>

                {/* Menu items */}
                <div className="p-1.5">
                  <Link
                    href="/settings"
                    onClick={() => setProfileOpen(false)}
                    className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-slate-700 transition-colors hover:bg-slate-50"
                  >
                    <Settings className="h-4 w-4 text-slate-400" />
                    {t("common.settings")}
                  </Link>
                  <button
                    onClick={handleLogout}
                    className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-red-600 transition-colors hover:bg-red-50"
                    type="button"
                  >
                    <LogOut className="h-4 w-4" />
                    {t("common.signOut")}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* ═══════════ Search Command Palette Modal ═══════════ */}
      {searchOpen && (
        <ModalShell
          onClose={closeSearch}
          ariaLabel="Search stocks"
          className="!items-start !pt-[15vh]"
        >
          <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white shadow-2xl">
            {/* Search input */}
            <div className="flex items-center gap-3 border-b border-slate-100 px-4 py-3">
              <Search className="h-5 w-5 shrink-0 text-slate-400" />
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={t("topbar.searchTicker")}
                className="flex-1 bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400"
                onKeyDown={(e) => {
                  if (e.key === "Escape") closeSearch();
                  if (e.key === "Enter" && searchResults.length > 0) {
                    handleResultClick(searchResults[0].ticker);
                  }
                }}
              />
              <button
                onClick={closeSearch}
                className="flex h-6 w-6 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
                type="button"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Results */}
            <div className="max-h-72 overflow-y-auto">
              {searchLoading && (
                <div className="px-4 py-6 text-center text-sm text-slate-400">
                  {t("topbar.searching")}
                </div>
              )}

              {!searchLoading &&
                searchQuery.trim() !== "" &&
                searchResults.length === 0 && (
                  <div className="px-4 py-6 text-center text-sm text-slate-400">
                    {t("topbar.noResults", { query: searchQuery })}
                  </div>
                )}

              {!searchLoading &&
                searchResults.map((r) => (
                  <button
                    key={r.ticker}
                    className="flex w-full items-center gap-4 px-4 py-3 text-left transition-colors hover:bg-slate-50"
                    type="button"
                    onClick={() => handleResultClick(r.ticker)}
                  >
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-xs font-bold text-slate-700">
                      {r.ticker.slice(0, 3)}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-slate-900">
                        {r.ticker}
                      </p>
                      <p className="truncate text-xs text-slate-400">
                        {r.name}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-medium text-slate-900">
                        ${r.price?.toFixed(2)}
                      </p>
                      <p
                        className={cn(
                          "text-xs font-medium",
                          (r.change_pct ?? 0) >= 0
                            ? "text-emerald-600"
                            : "text-red-500",
                        )}
                      >
                        {fmtPct(r.change_pct)}
                      </p>
                    </div>
                    <ExternalLink className="h-3.5 w-3.5 shrink-0 text-slate-300" />
                  </button>
                ))}
            </div>

            {/* Footer hint */}
            <div className="flex items-center justify-between border-t border-slate-100 px-4 py-2">
              <span className="text-[11px] text-slate-400">
                {t("topbar.typeToSearch")}
              </span>
              <kbd className="rounded-md border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[11px] font-medium text-slate-400">
                ESC
              </kbd>
            </div>
          </div>
        </ModalShell>
      )}
    </>
  );
}
