"use client";

/**
 * NotificationDropdown — Bell icon + Bronze-accent dropdown.
 *
 * Mock notifications only (no backend roundtrip yet). Compliance: labels use
 * "observation" / "alert" / "ready" / "noted" — no buy/sell/recommend/target.
 */

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Bell } from "lucide-react";
import { cn } from "@/lib/utils";

type Notification = {
  id: string;
  title: string;
  time: string;          // display string (e.g. "1h ago")
  unread: boolean;
  href?: string;
};

const MOCK_NOTIFICATIONS: Notification[] = [
  { id: "n1", title: "AAPL reached 52-week high", time: "1h ago", unread: true, href: "/detail/AAPL" },
  { id: "n2", title: "Portfolio concentration alert — Tech 34.2%", time: "2h ago", unread: true, href: "/risk" },
  { id: "n3", title: "FOMC meeting tomorrow, 2 PM ET", time: "6h ago", unread: true, href: "/market" },
  { id: "n4", title: "Weekly Memo ready", time: "1d ago", unread: false, href: "/reports" },
  { id: "n5", title: "KIS account sync complete", time: "2d ago", unread: false, href: "/settings" },
  { id: "n6", title: "NVDA observation noted in Discover scan", time: "3d ago", unread: false, href: "/discover" },
];

export function NotificationDropdown() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Notification[]>(MOCK_NOTIFICATIONS);
  const ref = useRef<HTMLDivElement | null>(null);

  const unread = items.filter((n) => n.unread).length;

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

  function markAllRead() {
    setItems((prev) => prev.map((n) => ({ ...n, unread: false })));
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
            {unread}
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
                className="text-base italic"
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
            {items.length === 0 ? (
              <div
                className="px-4 py-10 text-center text-sm italic"
                style={{ fontFamily: "var(--font-serif), serif", color: "var(--pq-muted)" }}
              >
                Nothing observed yet.
              </div>
            ) : (
              items.map((n, i) => (
                <Link
                  key={n.id}
                  href={n.href ?? "#"}
                  onClick={() => setOpen(false)}
                  className={cn(
                    "flex items-start gap-3 px-4 py-3 transition-colors",
                  )}
                  style={{
                    borderTop: i === 0 ? "none" : "0.5px solid var(--pq-hairline-soft)",
                  }}
                >
                  <span
                    className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
                    style={{
                      background: n.unread ? "var(--pq-bronze)" : "transparent",
                      border: n.unread ? "none" : "0.5px solid var(--pq-hairline)",
                    }}
                    aria-hidden
                  />
                  <div className="min-w-0 flex-1">
                    <p
                      className="text-[14px] leading-snug"
                      style={{
                        fontFamily: "var(--font-serif), serif",
                        color: n.unread ? "var(--pq-ink)" : "var(--pq-muted)",
                        fontWeight: n.unread ? 500 : 400,
                      }}
                    >
                      {n.title}
                    </p>
                    <p
                      className="mt-0.5 text-[11px] uppercase"
                      style={{ letterSpacing: "0.12em", color: "var(--pq-muted)" }}
                    >
                      {n.time}
                    </p>
                  </div>
                </Link>
              ))
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
