"use client";

/**
 * /alerts — Full alerts history in the Vantablack ink theme.
 *
 * Features preserved:
 *  - SWR via useAlerts (`/api/alerts`)
 *  - Unread / kind filters
 *  - Click row → auto-read + navigate to /detail/[ticker]
 *  - Mark all read
 *  - Clear all (2-step confirm)
 *
 * Legal: POSITIVE / NEGATIVE / NEUTRAL only. DisclaimerBanner at top.
 */

import { useState, useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { API } from "@/lib/endpoints";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useAlerts } from "@/lib/hooks";
import type { AlertItem } from "@/lib/types";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import {
  Caption,
  Fleuron,
  FootSignature,
  NumDisplay,
  RuledKicker,
} from "@/components/ui/editorial";
import { BellOff, CheckCheck, Trash2 } from "lucide-react";

/* ── Helpers ── */

function relativeTime(dateStr: string): string {
  if (!dateStr) return "";
  const now = Date.now();
  const d = new Date(dateStr).getTime();
  if (Number.isNaN(d)) return "";
  const diff = now - d;
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d`;
  return `${Math.floor(days / 7)}w`;
}

function kindLabel(type: string): string {
  if (!type) return "INFO";
  if (type.startsWith("signal")) return "SIGNAL";
  if (type.startsWith("risk")) return "RISK";
  if (type.includes("trade")) return "TRADE";
  if (type.includes("artifact")) return "ARTIFACT";
  if (type.includes("price")) return "PRICE";
  if (type.includes("concentration")) return "CONCENTRATION";
  if (type.includes("macro")) return "MACRO";
  return type.toUpperCase();
}

type FilterKey = "all" | "unread" | "read";

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "unread", label: "Unread" },
  { key: "read", label: "Read" },
];

/* ── Page ── */

export default function AlertsPage() {
  const router = useRouter();
  const { data, isLoading, mutate } = useAlerts();
  const [filter, setFilter] = useState<FilterKey>("all");
  const [markingRead, setMarkingRead] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);

  const alerts = useMemo<AlertItem[]>(() => data?.alerts ?? [], [data?.alerts]);

  const stats = useMemo(() => {
    const unread = alerts.filter((a) => !a.is_read).length;
    const now = Date.now();
    const DAY = 86_400_000;
    const today = alerts.filter(
      (a) => now - new Date(a.created_at).getTime() < DAY,
    ).length;
    const week = alerts.filter(
      (a) => now - new Date(a.created_at).getTime() < 7 * DAY,
    ).length;
    return { total: alerts.length, unread, today, week };
  }, [alerts]);

  const filtered = useMemo(() => {
    if (filter === "unread") return alerts.filter((a) => !a.is_read);
    if (filter === "read") return alerts.filter((a) => a.is_read);
    return alerts;
  }, [alerts, filter]);

  /* ── Mark all read ── */
  const handleMarkAllRead = useCallback(async () => {
    setMarkingRead(true);
    try {
      await apiFetch(API.alerts.read, { method: "POST" });
      await mutate();
      toast.success("Marked all as read");
    } catch {
      toast.error("Failed to mark as read");
    } finally {
      setMarkingRead(false);
    }
  }, [mutate]);

  /* ── Clear all ── */
  const handleClearAll = useCallback(async () => {
    if (!confirmClear) {
      setConfirmClear(true);
      return;
    }
    setClearing(true);
    try {
      await apiFetch(API.alerts.clear, { method: "POST" });
      await mutate();
      toast.success("All alerts cleared");
    } catch {
      toast.error("Failed to clear");
    } finally {
      setClearing(false);
      setConfirmClear(false);
    }
  }, [confirmClear, mutate]);

  /* ── Click row ── */
  const handleAlertClick = useCallback(
    async (alert: AlertItem) => {
      // Opportunistic read-mark
      if (!alert.is_read) {
        try {
          await apiFetch(API.alerts.itemRead(alert.id), { method: "POST" });
          mutate();
        } catch {
          /* silent */
        }
      }
      if (alert.ticker) router.push(`/detail/${alert.ticker}`);
    },
    [mutate, router],
  );

  return (
    <ErrorBoundary>
      <div className="space-y-8">
        {/* ── Header ── */}
        <header className="flex items-start justify-between gap-4">
          <div>
            <RuledKicker>Signals desk &middot; Alerts history</RuledKicker>
            <h1 className="mt-2 font-serif italic text-3xl text-[var(--pq-ivory)]">
              Alerts
            </h1>
            <Caption className="mt-1">
              Every observation the desk has dispatched. Informational only.
            </Caption>
          </div>

          {stats.unread > 0 && (
            <button
              type="button"
              onClick={handleMarkAllRead}
              disabled={markingRead}
              className="pq-ink-btn-ghost inline-flex items-center gap-1.5 disabled:opacity-50"
            >
              <CheckCheck className="h-3.5 w-3.5" />
              Mark all as read
            </button>
          )}
        </header>

        {/* ── 4-stat strip ── */}
        <section className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: "Total", value: stats.total },
            { label: "Unread", value: stats.unread },
            { label: "Today", value: stats.today },
            { label: "This week", value: stats.week },
          ].map((s) => (
            <div
              key={s.label}
              className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-5 rounded-[2px]"
            >
              <div className="pq-ink-label text-[10px] tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
                {s.label}
              </div>
              <div className="mt-2">
                <NumDisplay size={26}>{s.value}</NumDisplay>
              </div>
            </div>
          ))}
        </section>

        {/* ── Disclaimer ── */}
        <DisclaimerBanner type="signal" />

        {/* ── Filter tabs ── */}
        <div className="pq-ink-tabs flex gap-6 border-b border-[rgba(245,240,232,0.08)]">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => setFilter(f.key)}
              data-active={filter === f.key}
              className="pq-ink-tab"
            >
              {f.label}
              {f.key === "unread" && stats.unread > 0 && (
                <span className="ml-1.5 text-[10px] text-[var(--pq-bronze)]">
                  {stats.unread}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* ── List ── */}
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="h-16 rounded-[2px] bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] animate-pulse"
              />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-12 rounded-[2px] text-center">
            <Fleuron size={16} />
            <p className="mt-4 font-serif italic text-xl text-[var(--pq-ivory)]">
              No observations recorded yet.
            </p>
            <Caption className="mt-2">
              Signals, risk events, and price thresholds will appear here as we observe them.
            </Caption>
            <BellOff
              className="mx-auto mt-4 h-5 w-5 text-[var(--pq-bronze)]"
              strokeWidth={1.2}
              aria-hidden="true"
            />
          </div>
        ) : (
          <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] rounded-[2px] overflow-hidden">
            <table className="pq-ink-table w-full">
              <thead>
                <tr>
                  <th className="text-left px-5 py-3 text-[10px] tracking-[0.22em] uppercase">
                    Time
                  </th>
                  <th className="text-left px-5 py-3 text-[10px] tracking-[0.22em] uppercase">
                    Kind
                  </th>
                  <th className="text-left px-5 py-3 text-[10px] tracking-[0.22em] uppercase">
                    Title
                  </th>
                  <th className="text-left px-5 py-3 text-[10px] tracking-[0.22em] uppercase">
                    Ticker
                  </th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((a) => (
                  <tr
                    key={a.id}
                    onClick={() => handleAlertClick(a)}
                    className="cursor-pointer"
                  >
                    <td className="px-5 py-3 text-xs text-[rgba(245,240,232,0.6)] tabular-nums whitespace-nowrap">
                      {relativeTime(a.created_at)}
                    </td>
                    <td className="px-5 py-3">
                      <span className="text-[10px] tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
                        {kindLabel(a.type)}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        {!a.is_read && (
                          <span className="h-1.5 w-1.5 rounded-full bg-[var(--pq-bronze)] shrink-0" />
                        )}
                        <div className="min-w-0">
                          <div
                            className={cn(
                              "font-serif italic text-base text-[var(--pq-ivory)] truncate",
                              !a.is_read && "font-semibold",
                            )}
                          >
                            {a.name || a.ticker || kindLabel(a.type)}
                          </div>
                          <div className="mt-0.5 text-xs text-[rgba(245,240,232,0.6)] truncate">
                            {a.message}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3 text-xs font-mono text-[rgba(245,240,232,0.5)]">
                      {a.ticker ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Editorial foot signature */}
        <FootSignature />

        {/* ── Clear all ── */}
        {alerts.length > 0 && (
          <div className="flex justify-center pt-4 border-t border-[rgba(245,240,232,0.08)]">
            <button
              type="button"
              onClick={handleClearAll}
              disabled={clearing}
              className={cn(
                "inline-flex items-center gap-1.5 px-5 py-2 text-xs tracking-[0.18em] uppercase transition-colors",
                confirmClear
                  ? "text-red-400"
                  : "text-[rgba(245,240,232,0.5)] hover:text-[var(--pq-bronze)]",
                "disabled:opacity-40",
              )}
            >
              <Trash2 className="h-3.5 w-3.5" />
              {confirmClear ? "Confirm · delete all" : "Clear all"}
            </button>
          </div>
        )}
      </div>
    </ErrorBoundary>
  );
}
