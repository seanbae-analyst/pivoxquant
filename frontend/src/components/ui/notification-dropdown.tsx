"use client";

/**
 * NotificationDropdown — Bell icon + Bronze-accent dropdown.
 *
 * Live-wired to /api/alerts (2026-04-22). All copy is observation-only:
 * "reached", "noted", "ready", "complete". No buy / sell / recommend /
 * advice / target language anywhere in this file.
 *
 * Phone (<768px, 2026-10-09): the panel opens as a full-height bottom sheet
 * (components/ui/sheet.tsx) instead of a popover hanging off the top bar.
 */

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { Bell } from "lucide-react";

import { cn } from "@/lib/utils";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { useAuth } from "@/lib/auth";
import { useLocale } from "@/lib/locale";
import { relativeTime } from "@/lib/relative-time";
import { useIsPhone } from "@/lib/use-phone";
import { markOverlayNavigation } from "@/lib/use-back-dismiss";
import { Sheet } from "@/components/ui/sheet";

type AlertRow = {
  id: number;
  kind?: string | null;
  title?: string | null;
  body?: string | null;
  link?: string | null;
  ticker?: string | null;
  created_at: string;
  read_at?: string | null;
  is_read: boolean;
  // legacy fallback
  message?: string | null;
};

type AlertsListResponse = {
  alerts: AlertRow[];
  unread: number;
};

function fetcher<T>(url: string): Promise<T> {
  return apiFetch<T>(url);
}

// Relative-time formatter is now shared (lib/relative-time.ts). The previous
// local English-only formatter was the source of one of the loudest KR-first
// regressions on the topbar (Wave C-1 i18n sweep, 2026-05-17).

export function NotificationDropdown() {
  const router = useRouter();
  const { locale, t } = useLocale();
  const [open, setOpen] = useState(false);
  const [markingRead, setMarkingRead] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);
  const isPhone = useIsPhone();

  // BUG-8 FIX 2: unify the SWR cache key with `useAlerts()` in hooks.ts
  // so both subscriptions dedupe to a single request.
  //
  // 2026-05-10 (B-09): hooks.ts:96 was changed to `?limit=50` for the
  // /alerts page Total/Unread/Today/Week stats accuracy (Bug #2 deep
  // bug hunt). The dropdown was still on `API.alerts.list` (no qs),
  // re-introducing the duplicate cache entry the original BUG-8 fix
  // closed. Re-unifying on `?limit=50` here so SWR dedupes both
  // subscriptions onto a single in-flight fetch + cache row.
  //
  // P1 FIX (2026-05-03): unread count is derived from the same list
  // response (backend includes `unread` aggregate at routes/alerts.py:73).
  // The previous separate `useSWR(API.alerts.unreadCount)` call doubled
  // the alerts polling rate (~3-4 req/min). Now: one SWR subscription,
  // unread derived from `data.unread`. No backend change required.
  //
  // 2026-09-13: the key is null until there is a signed-in user. The top bar
  // mounts before the auth guard redirects, so an ungated key fired a
  // `401 GET /api/alerts?limit=50` on every protected route for signed-out
  // visitors (2026-09-12 sweep).
  const { user } = useAuth();
  const { data, error, isLoading, mutate } = useSWR<AlertsListResponse>(
    user ? `${API.alerts.list}?limit=50` : null,
    fetcher,
    // Bug #3 (HANDOVER v22): focus revalidate compounded duplicate fetches
    // on page nav. The 60s polling already keeps the unread badge fresh.
    { refreshInterval: 60_000, revalidateOnFocus: false },
  );

  const items = (data?.alerts ?? []).slice(0, 10);
  const unread = data?.unread ?? 0;

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      // The phone panel is a sheet portaled to <body>; taps inside it are not
      // "outside" (the sheet has its own backdrop dismissal).
      if ((e.target as Element | null)?.closest?.("[data-pq-sheet-layer]")) return;
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onEsc(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onClickOutside);
      document.removeEventListener("keydown", onEsc);
    };
  }, []);

  async function markAllRead() {
    // Guard double-submit — parity with the /alerts page (markingRead). The
    // POST is idempotent server-side, so this only avoids redundant requests.
    if (markingRead) return;
    setMarkingRead(true);
    try {
      await apiFetch(API.alerts.readAll, { method: "POST" });
    } catch {
      // swallow — mutate below will pick up server state either way
    } finally {
      setMarkingRead(false);
    }
    mutate();
  }

  async function onItemClick(item: AlertRow) {
    setOpen(false);
    if (!item.is_read) {
      try {
        await apiFetch(API.alerts.itemRead(item.id), { method: "POST" });
      } catch {
        // best-effort
      }
      mutate();
    }
    if (item.link) {
      // Leaving from inside the phone sheet: keep its back-entry cleanup from
      // racing this navigation.
      markOverlayNavigation();
      router.push(item.link);
    }
  }

  const panelBody = (
    <>
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 max-md:px-5 max-md:pt-1"
        style={{ borderBottom: "0.5px solid var(--pq-hairline)" }}
      >
        <div>
          <div
            className="text-pq-eyebrow uppercase"
            style={{ letterSpacing: "0.2em", color: "var(--pq-muted)" }}
          >
            {t("topbar.notifications")}
          </div>
          <div
            className="text-base font-serif"
            style={{ color: "var(--pq-ivory)" }}
          >
            {t("topbar.observations")}
          </div>
        </div>
        {unread > 0 && (
          <button
            onClick={markAllRead}
            type="button"
            disabled={markingRead}
            className="text-xs underline underline-offset-4 transition-colors disabled:opacity-50"
            style={{ color: "var(--pq-bronze)" }}
          >
            {t("topbar.markAllRead")}
          </button>
        )}
      </div>

      {/* List */}
      <div className="max-h-[360px] overflow-y-auto max-md:max-h-none max-md:overflow-visible">
        {isLoading ? (
          <div className="px-4 py-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className="flex items-start gap-3 py-3">
                <div
                  className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
                  style={{ background: "rgba(245,240,232,0.12)" }}
                  aria-hidden
                />
                <div className="min-w-0 flex-1 space-y-1.5">
                  <div
                    className="h-3 w-4/5 rounded"
                    style={{ background: "var(--pq-ivory-line)" }}
                  />
                  <div
                    className="h-2 w-2/5 rounded"
                    style={{ background: "var(--pq-ivory-line-soft)" }}
                  />
                </div>
              </div>
            ))}
          </div>
        ) : error ? (
          <div
            className="px-4 py-10 text-center text-sm font-serif"
            style={{ color: "var(--pq-muted)" }}
          >
            {t("topbar.unableToLoad")}
          </div>
        ) : items.length === 0 ? (
          <div
            className="px-4 py-10 text-center text-sm font-serif"
            style={{ color: "var(--pq-muted)" }}
          >
            {t("topbar.noAlertsYet")}
          </div>
        ) : (
          items.map((n, i) => {
            const unreadRow = !n.is_read;
            const title = n.title || n.message || t("topbar.observations");
            return (
              <button
                key={n.id}
                type="button"
                onClick={() => onItemClick(n)}
                className={cn(
                  "flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-[rgba(var(--pq-bronze-wash-rgb),0.05)]",
                  // Phone sheet: full-width rows on the sheet gutter.
                  "max-md:min-h-[56px] max-md:px-5",
                )}
                style={{
                  borderTop: i === 0 ? "none" : "0.5px solid var(--pq-hairline-soft)",
                }}
                role="menuitem"
              >
                <span
                  className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
                  style={{
                    background: unreadRow ? "var(--pq-bronze)" : "transparent",
                    border: unreadRow ? "none" : "0.5px solid var(--pq-hairline)",
                  }}
                  aria-hidden
                />
                <div className="min-w-0 flex-1">
                  <p
                    className="text-pq-body leading-snug font-serif"
                    style={{
                      color: unreadRow ? "var(--pq-ivory)" : "var(--pq-muted)",
                      fontWeight: unreadRow ? 600 : 400,
                    }}
                  >
                    {title}
                  </p>
                  {n.body && (
                    <p
                      className="mt-0.5 text-[9pt] leading-snug"
                      style={{ color: "var(--pq-muted)" }}
                    >
                      {n.body}
                    </p>
                  )}
                  <p
                    className="mt-1 text-pq-mono-sm uppercase tabular-nums"
                    style={{ letterSpacing: "0.12em", color: "var(--pq-muted)" }}
                  >
                    {relativeTime(n.created_at, locale, { verbose: true })}
                  </p>
                </div>
              </button>
            );
          })
        )}
      </div>
    </>
  );

  return (
    /* Mobile (<sm): the root is NOT positioned, so the panel anchors to the
       full-width TopBar <header> (relative) and spans it edge-to-edge with a
       16px gutter. Anchoring to the bell itself pushed a 340px panel ~18px
       past the left edge on a 390px iPhone (bell sits left of the avatar). */
    <div ref={ref} className="sm:relative">
      <button
        type="button"
        onClick={() => setOpen((p) => !p)}
        aria-label={t("topbar.notifications")}
        aria-expanded={open}
        /* FINDING-020: rounded-full → rounded (4px) — §0 editorial radius. */
        /* 2026-05-17 wave C-3 P2: h-10/w-10 (40px) below Apple HIG 44px tap-target.
           Bump to h-11/w-11 so notification bell is reliably tappable on mobile. */
        className="pq-topbar-icon-btn relative flex h-11 w-11 items-center justify-center rounded transition-colors hover:bg-[rgba(var(--pq-bronze-wash-rgb),0.08)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--pq-bronze)] focus-visible:ring-offset-0"
        style={{
          color: open
            ? "var(--pq-bronze)"
            : unread > 0
              ? "var(--pq-bronze)"
              : "var(--pq-ivory)",
        }}
      >
        <Bell className="h-5 w-5" strokeWidth={1.75} />
        {unread > 0 && (
          <span
            className="absolute -right-0.5 -top-0.5 flex h-4 min-w-[16px] items-center justify-center rounded-full px-1 font-mono text-pq-eyebrow font-semibold"
            style={{ background: "var(--pq-bronze)", color: "var(--pq-ivory)" }}
          >
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {open && !isPhone && (
        <div
          className="absolute inset-x-4 top-full z-[100] mt-2 overflow-hidden sm:inset-x-auto sm:right-0 sm:w-[340px] rounded-xl shadow-[0_16px_48px_-16px_rgba(10,10,10,0.3)]"
          style={{ background: "color-mix(in srgb, var(--pq-ivory) 4%, var(--pq-ink))", border: "0.5px solid rgba(245,240,232,0.12)" }}
          role="menu"
        >
          {panelBody}
        </div>
      )}

      <Sheet
        open={open && isPhone}
        onClose={() => setOpen(false)}
        ariaLabel={t("topbar.notifications")}
        phoneFullHeight
        phoneBodyClassName="px-0"
      >
        <div role="menu">{panelBody}</div>
      </Sheet>
    </div>
  );
}
