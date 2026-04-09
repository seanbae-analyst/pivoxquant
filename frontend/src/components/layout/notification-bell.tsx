"use client";

import { useEffect, useRef, useState } from "react";
import useSWR, { mutate } from "swr";
import Link from "next/link";
import { API } from "@/lib/endpoints";

interface Alert {
  id: number;
  ticker: string;
  message: string;
  signal: string;
  score: number;
  created_at: string;
  is_read: boolean;
}

interface AlertsResponse {
  alerts: Alert[];
  unread: number;
}

const fetcher = (url: string) =>
  fetch(url, { credentials: "include" }).then((r) => {
    if (!r.ok) throw new Error(r.statusText);
    return r.json();
  });

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const { data } = useSWR<AlertsResponse>(API.alerts.list, fetcher, {
    refreshInterval: 30_000,
    revalidateOnFocus: true,
    dedupingInterval: 10_000,
  });

  const unread = data?.unread ?? 0;
  const alerts = data?.alerts ?? [];

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const markAllRead = async () => {
    await fetch(API.alerts.read, {
      method: "POST",
      credentials: "include",
    });
    mutate(API.alerts.list);
  };

  const handleToggle = () => {
    setOpen((prev) => !prev);
    // Mark as read when opening
    if (!open && unread > 0) {
      markAllRead();
    }
  };

  return (
    <div ref={ref} className="relative">
      {/* Bell button */}
      <button
        onClick={handleToggle}
        className="relative flex h-8 w-8 items-center justify-center rounded-lg transition-all duration-200 hover:bg-[rgba(255,255,255,0.06)]"
        aria-label={`Notifications${unread > 0 ? ` (${unread} unread)` : ""}`}
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="text-zinc-500"
        >
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>

        {/* Unread badge */}
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-emerald-500 px-1 text-[9px] font-bold text-black shadow-[0_0_8px_rgba(16,185,129,0.4)]">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute right-0 top-full z-[200] mt-2 w-[340px] overflow-hidden rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0d0d12] shadow-[0_20px_60px_rgba(0,0,0,0.6)]">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-[rgba(255,255,255,0.04)] px-4 py-3">
            <span className="text-[13px] font-semibold text-white">
              Notifications
            </span>
            <Link
              href="/alerts"
              onClick={() => setOpen(false)}
              className="text-[11px] text-emerald-400 hover:text-emerald-300 transition-colors"
            >
              View All
            </Link>
          </div>

          {/* Alert list */}
          <div className="max-h-[360px] overflow-y-auto scrollbar-thin">
            {alerts.length === 0 ? (
              <div className="py-10 text-center">
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  className="mx-auto text-zinc-800"
                >
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                  <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                </svg>
                <p className="mt-2 text-[12px] text-zinc-700">
                  No notifications
                </p>
              </div>
            ) : (
              alerts.slice(0, 8).map((a) => (
                <Link
                  key={a.id}
                  href="/alerts"
                  onClick={() => setOpen(false)}
                  className={`flex items-start gap-3 px-4 py-3 transition-colors hover:bg-[rgba(255,255,255,0.03)] ${
                    !a.is_read
                      ? "bg-emerald-500/[0.02]"
                      : ""
                  }`}
                >
                  {/* Signal badge */}
                  <span
                    className={`mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[8px] font-bold ${
                      a.signal === "BUY"
                        ? "bg-emerald-500/15 text-emerald-400"
                        : a.signal === "SELL"
                          ? "bg-red-500/15 text-red-400"
                          : "bg-amber-500/15 text-amber-400"
                    }`}
                  >
                    {a.signal}
                  </span>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[12px] font-semibold text-white">
                        {a.ticker}
                      </span>
                      {!a.is_read && (
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                      )}
                    </div>
                    <p className="mt-0.5 line-clamp-2 text-[11px] leading-relaxed text-zinc-500">
                      {a.message}
                    </p>
                    <span className="mt-1 block text-[10px] text-zinc-700">
                      {formatRelativeTime(a.created_at)}
                    </span>
                  </div>
                </Link>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;

  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString();
}
