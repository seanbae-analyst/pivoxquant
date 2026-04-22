"use client";

/**
 * NotificationDropdown — Bell icon + Bronze-accent dropdown.
 *
 * Live-wired to /api/alerts (2026-04-22). All copy is observation-only:
 * "reached", "noted", "ready", "complete". No buy / sell / recommend /
 * advice / target language anywhere in this file.
 */

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { Bell } from "lucide-react";

import { cn } from "@/lib/utils";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";

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

type UnreadCountResponse = { count: number };

function fetcher<T>(url: string): Promise<T> {
  return apiFetch<T>(url);
}

function relativeTime(iso: string): string {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const diff = Date.now() - t;
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  const weeks = Math.floor(days / 7);
  return `${weeks}w ago`;
}

export function NotificationDropdown() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  const { data, error, isLoading, mutate } = useSWR<AlertsListResponse>(
    `${API.alerts.list}?limit=10`,
    fetcher,
    { refreshInterval: 60_000, revalidateOnFocus: true },
  );
  const { data: countData, mutate: mutateCount } = useSWR<UnreadCountResponse>(
    API.alerts.unreadCount,
    fetcher,
    { refreshInterval: 60_000, revalidateOnFocus: true },
  );

  const items = data?.alerts ?? [];
  const unread = countData?.count ?? 0;

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
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
    try {
      await apiFetch(API.alerts.readAll, { method: "POST" });
    } catch {
      // swallow — mutate below will pick up server state either way
    }
    mutate();
    mutateCount();
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
      mutateCount();
    }
    if (item.link) {
      router.push(item.link);
    }
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((p) => !p)}
        aria-label="Notifications"
        aria-expanded={open}
        className="relative flex h-10 w-10 items-center justify-center rounded-full transition-colors hover:bg-[rgba(139,111,71,0.08)]"
        style={{ color: "var(--pq-ink)" }}
      >
        <Bell className="h-[18px] w-[18px]" />
        {unread > 0 && (
          <span
            className="absolute right-1.5 top-1.5 flex h-4 min-w-[16px] items-center justify-center rounded-full px-1 font-mono text-[10px] font-semibold"
            style={{ background: "var(--pq-bronze)", color: "var(--pq-ivory)" }}
          >
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          className="absolute right-0 top-full z-50 mt-2 w-[340px] overflow-hidden rounded-xl shadow-[0_16px_48px_-16px_rgba(10,10,10,0.3)]"
          style={{ background: "var(--pq-ivory)", border: "0.5px solid var(--pq-hairline)" }}
          role="menu"
        >
          {/* Header */}
          <div
            className="flex items-center justify-between px-4 py-3"
            style={{ borderBottom: "0.5px solid var(--pq-hairline)" }}
          >
            <div>
              <div
                className="text-[10px] uppercase"
                style={{ letterSpacing: "0.2em", color: "var(--pq-muted)" }}
              >
                Notifications
              </div>
              <div
                className="text-base"
                style={{ fontFamily: "var(--font-serif), serif", color: "var(--pq-ink)" }}
              >
                Observations
              </div>
            </div>
            {unread > 0 && (
              <button
                onClick={markAllRead}
                type="button"
                className="text-xs underline underline-offset-4 transition-colors"
                style={{ color: "var(--pq-bronze)" }}
              >
                Mark all as read
              </button>
            )}
          </div>

          {/* List */}
          <div className="max-h-[360px] overflow-y-auto">
            {isLoading ? (
              <div className="px-4 py-3">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="flex items-start gap-3 py-3">
                    <div
                      className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
                      style={{ background: "var(--pq-hairline)" }}
                      aria-hidden
                    />
                    <div className="min-w-0 flex-1 space-y-1.5">
                      <div
                        className="h-3 w-4/5 rounded"
                        style={{ background: "var(--pq-hairline-soft, rgba(0,0,0,0.06))" }}
                      />
                      <div
                        className="h-2 w-2/5 rounded"
                        style={{ background: "var(--pq-hairline-soft, rgba(0,0,0,0.04))" }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            ) : error ? (
              <div
                className="px-4 py-10 text-center text-sm"
                style={{ fontFamily: "var(--font-serif), serif", color: "var(--pq-muted)" }}
              >
                Unable to load alerts
              </div>
            ) : items.length === 0 ? (
              <div
                className="px-4 py-10 text-center text-sm"
                style={{ fontFamily: "var(--font-serif), serif", color: "var(--pq-muted)" }}
              >
                No alerts yet. Signals will appear here as we observe them.
              </div>
            ) : (
              items.map((n, i) => {
                const unreadRow = !n.is_read;
                const title = n.title || n.message || "Observation";
                return (
                  <button
                    key={n.id}
                    type="button"
                    onClick={() => onItemClick(n)}
                    className={cn(
                      "flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-[rgba(139,111,71,0.05)]",
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
                        className="text-[14px] leading-snug"
                        style={{
                          fontFamily: "var(--font-serif), serif",
                          color: unreadRow ? "var(--pq-ink)" : "var(--pq-muted)",
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
                        className="mt-1 text-[11px] uppercase tabular-nums"
                        style={{ letterSpacing: "0.12em", color: "var(--pq-muted)" }}
                      >
                        {relativeTime(n.created_at)}
                      </p>
                    </div>
                  </button>
                );
              })
            )}
          </div>

          {/* Footer */}
          <Link
            href="/alerts"
            onClick={() => setOpen(false)}
            className="flex items-center justify-center px-4 py-3 text-xs uppercase transition-colors hover:bg-[rgba(139,111,71,0.08)]"
            style={{
              borderTop: "0.5px solid var(--pq-hairline)",
              letterSpacing: "0.18em",
              color: "var(--pq-bronze)",
            }}
          >
            View all
          </Link>
        </div>
      )}
    </div>
  );
}
