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

import { useState, useMemo, useCallback, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { API } from "@/lib/endpoints";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useAlerts } from "@/lib/hooks";
import type { AlertItem } from "@/lib/types";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { useLocale } from "@/lib/locale";
import { relativeTime as relativeTimeIntl } from "@/lib/relative-time";
import {
  Caption,
  Fleuron,
  FootSignature,
  NumDisplay,
  RuledKicker,
} from "@/components/ui/editorial";
import { BellOff, CheckCheck, Trash2 } from "lucide-react";

/* ── Helpers ── */

// Local relativeTime helper retired (Wave C-1, 2026-05-17). Use the shared
// locale-aware formatter from lib/relative-time.ts so the /alerts page and
// the bell dropdown stay in lockstep.

function kindLabel(type: string | null | undefined): string {
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

/* ── Page ── */

export default function AlertsPage() {
  const router = useRouter();
  const { locale, t } = useLocale();
  const { data, isLoading, mutate } = useAlerts();
  const [filter, setFilter] = useState<FilterKey>("all");

  // Filter tabs are locale-aware — built per-render so the active locale
  // resolves at the call-site (Wave C-1, 2026-05-17).
  const FILTERS: { key: FilterKey; label: string }[] = [
    { key: "all", label: t("alertsPage.filters.all") },
    { key: "unread", label: t("alertsPage.filters.unread") },
    { key: "read", label: t("alertsPage.filters.read") },
  ];
  const [markingRead, setMarkingRead] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);

  const alerts = useMemo<AlertItem[]>(() => data?.alerts ?? [], [data?.alerts]);

  // 2026-05-09 fix: force a fresh fetch on mount so the desk-vs-bell
  // counter mismatch that caused "bell shows 13 / page shows 0" can't
  // persist across SWR cache states. The bell polls every 60s; the
  // /alerts page is a deeper view, so paying for one extra fetch on
  // entry is the right trade for guaranteed source-of-truth parity.
  useEffect(() => {
    void mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stats = useMemo(() => {
    // 2026-05-09 fix: bell-vs-page count parity.
    // The bell reads `data.unread` (now an authoritative DB count after the
    // routes/alerts.py fix). Use the same value here so the two surfaces
    // can never disagree — the previous `alerts.filter(...).length` only
    // counted the limit-20 slice, and recomputing locally races the
    // backend's truth source. `data?.unread ?? alerts.filter(...).length`
    // keeps a graceful fallback for first-render before the response lands.
    const unread =
      (data as { unread?: number } | undefined)?.unread ??
      alerts.filter((a) => !a.is_read).length;
    const now = Date.now();
    const DAY = 86_400_000;
    const today = alerts.filter(
      (a) => now - new Date(a.created_at).getTime() < DAY,
    ).length;
    const week = alerts.filter(
      (a) => now - new Date(a.created_at).getTime() < 7 * DAY,
    ).length;
    return { total: alerts.length, unread, today, week };
  }, [alerts, data]);

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
      toast.success(t("alertsPage.toast.marked"));
    } catch {
      toast.error(t("alertsPage.toast.markFailed"));
    } finally {
      setMarkingRead(false);
    }
  }, [mutate, t]);

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
      toast.success(t("alertsPage.toast.cleared"));
    } catch {
      toast.error(t("alertsPage.toast.clearFailed"));
    } finally {
      setClearing(false);
      setConfirmClear(false);
    }
  }, [confirmClear, mutate, t]);

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
        {/* ── Editorial header (Wave 1, 2026-05-01) ──
            Promoted the headline to the v3 Playfair-with-italic-accent
            convention used by /portfolio v2 ("Your *book.*"), /risk v2
            ("Risk *board.*"), /signals ("*observed* … *filtered*"), and
            now /discover ("What the desk *observed.*"). Was a flat
            sans h1 "Alerts". */}
        <header className="flex items-start justify-between gap-4">
          <div>
            <RuledKicker>Signals desk &middot; Alerts history</RuledKicker>
            <h1
              className="mt-3 font-display"
              style={{
                fontWeight: 500,
                fontSize: "clamp(34px, 4.6vw, 52px)",
                lineHeight: 1.06,
                letterSpacing: "-0.022em",
                color: "var(--pq-ivory)",
              }}
            >
              When the desk{" "}
              <span style={{ fontStyle: "italic", color: "var(--pq-bronze)" }}>
                spoke.
              </span>
            </h1>
            <Caption className="mt-3 max-w-[560px]">
              Every observation the desk has dispatched — kept as a record,
              never an instruction.
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
              {t("alertsPage.actions.markAllRead")}
            </button>
          )}
        </header>

        {/* ── Hairline metric strip (Wave 1, 2026-05-01) ──
            Was a 4-card boxy grid (`bg-[rgba(255,255,255,0.02)] border ...
            rounded-[2px]`) which read as a generic SaaS dashboard tile
            row and broke from the v3 lock-in. Now ledger-style hairline
            rows: bronze eyebrow + tabular-mono numeral, divided only
            by 0.5px hairlines. Same 4 metrics, no boxes. */}
        <section
          className="grid grid-cols-2 gap-x-12 gap-y-5 sm:grid-cols-4 border-t pt-5"
          style={{
            borderTopColor: "rgba(184,149,106,0.32)",
            borderTopWidth: 0.5,
          }}
        >
          {[
            { label: t("alertsPage.stats.total"), value: stats.total },
            { label: t("alertsPage.stats.unread"), value: stats.unread },
            { label: t("alertsPage.stats.today"), value: stats.today },
            { label: t("alertsPage.stats.thisWeek"), value: stats.week },
          ].map((s) => (
            <div key={s.label} className="flex flex-col">
              <span
                className="font-mono text-pq-eyebrow uppercase"
                style={{
                  letterSpacing: "0.22em",
                  color: "var(--pq-bronze)",
                }}
              >
                {s.label}
              </span>
              <div className="mt-2">
                <NumDisplay size={28}>{s.value}</NumDisplay>
              </div>
            </div>
          ))}
        </section>

        {/* Legal disclaimer mounted by (dashboard)/layout.tsx — do not re-mount. */}

        {/* ── Filter tabs ── */}
        <div className="pq-ink-tabs flex gap-6 border-b border-[var(--pq-ivory-line)]">
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
                <span className="ml-1.5 text-pq-eyebrow text-[var(--pq-bronze)]">
                  {stats.unread}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* ── List ── */}
        {isLoading ? (
          // Editorial skeleton — hairline-divided rows match the actual
          // table rhythm, no rounded card boxes.
          <div className="border-t" style={{ borderTopColor: "var(--pq-ivory-line)", borderTopWidth: 0.5 }}>
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="h-12 border-b animate-pulse"
                style={{
                  borderBottomColor: "var(--pq-ivory-line-soft)",
                  borderBottomWidth: 0.5,
                  background: "var(--pq-ivory-line-ghost)",
                }}
              />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          // Editorial empty state — Fleuron + serif headline + italic
          // caption, no card wrapper. Matches /watchlist empty state +
          // FootSignature pattern in /portfolio v2 / /risk v2.
          <div className="flex flex-col items-center gap-3 py-16 text-center">
            <Fleuron size={16} />
            <p
              className="mt-2 font-display"
              style={{
                fontSize: "var(--pq-text-quote)",
                lineHeight: 1.2,
                color: "var(--pq-ivory)",
              }}
            >
              The desk has been{" "}
              <span style={{ fontStyle: "italic", color: "var(--pq-bronze)" }}>
                quiet.
              </span>
            </p>
            <Caption className="max-w-md">
              Signals, risk events, and price thresholds will be recorded
              here as we observe them.
            </Caption>
            <BellOff
              className="mt-2 h-4 w-4 opacity-50"
              style={{ color: "var(--pq-bronze)" }}
              strokeWidth={1.2}
              aria-hidden="true"
            />
          </div>
        ) : (
          // Bare hairline table — drop the rounded card wrapper that was
          // out of step with /portfolio v2, /risk v2, /signals, /discover.
          // Mobile (P2 Wave B): card layout to avoid horizontal scroll.
          <>
            {/* Desktop / tablet — hairline table */}
            <div className="hidden md:block overflow-x-auto">
              <table className="pq-ink-table w-full min-w-[460px]">
                <thead>
                  <tr>
                    <th className="text-left px-5 py-3 text-pq-eyebrow tracking-[0.22em] uppercase">
                      {t("alertsPage.table.time")}
                    </th>
                    <th className="text-left px-5 py-3 text-pq-eyebrow tracking-[0.22em] uppercase">
                      {t("alertsPage.table.kind")}
                    </th>
                    <th className="text-left px-5 py-3 text-pq-eyebrow tracking-[0.22em] uppercase">
                      {t("alertsPage.table.title")}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((a) => (
                    // Bug #6 fix (2026-05-09 deep bug hunt): cursor-pointer
                    // implied interactivity but rows without a ticker
                    // (account_sync / macro_event / watchlist_event) just
                    // marked-as-read and stayed put — no navigation, no
                    // feedback. Conditional cursor matches actual behaviour.
                    <tr
                      key={a.id}
                      onClick={() => handleAlertClick(a)}
                      className={a.ticker ? "cursor-pointer" : "cursor-default"}
                    >
                      <td className="px-5 py-3 text-xs text-[rgba(245,240,232,0.6)] tabular-nums whitespace-nowrap">
                        {relativeTimeIntl(a.created_at, locale)}
                      </td>
                      <td className="px-5 py-3">
                        <span className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
                          {kindLabel(a.kind)}
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
                                "font-serif text-base text-[var(--pq-ivory)] truncate",
                                !a.is_read && "font-semibold",
                              )}
                            >
                              {a.name || a.ticker || kindLabel(a.kind)}
                            </div>
                            {/* PR #212 follow-up: drop the redundant Ticker
                                column (was duplicated next to a.name).
                                Promote ticker to a small subline under the
                                hero name so the symbol code is still visible
                                without the extra column. */}
                            {a.name && a.ticker && (
                              <div className="mt-0.5 text-pq-eyebrow tracking-[0.06em] font-mono text-[rgba(245,240,232,0.45)] truncate">
                                {a.ticker}
                              </div>
                            )}
                            <div className="mt-0.5 text-xs text-[rgba(245,240,232,0.6)] truncate">
                              {a.title || a.message}
                            </div>
                            {(a.body || a.message)?.includes("set capital for sizing") && (
                              <Link
                                href="/settings#capital"
                                onClick={(e) => e.stopPropagation()}
                                className="mt-1 inline-block text-pq-eyebrow uppercase tracking-[0.18em] text-[var(--pq-bronze)] hover:underline"
                              >
                                → Set capital in Settings
                              </Link>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile — hairline-divided card list */}
            <ul
              className="md:hidden border-t"
              style={{
                borderTopColor: "var(--pq-ivory-line)",
                borderTopWidth: 0.5,
              }}
            >
              {filtered.map((a) => (
                <li
                  key={a.id}
                  onClick={() => handleAlertClick(a)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      handleAlertClick(a);
                    }
                  }}
                  role="button"
                  tabIndex={0}
                  className="cursor-pointer px-1 py-3 focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--pq-bronze)] focus-visible:outline-offset-2"
                  style={{
                    borderBottom: "0.5px solid var(--pq-ivory-line-soft)",
                  }}
                >
                  {/* Row 1 — Time · Kind
                      PR #212 follow-up: drop the right-aligned ticker chip
                      (duplicated `a.name` already on Row 2). Ticker is now
                      a small subline under the hero name. */}
                  <div className="flex items-center gap-2 min-w-0">
                    {!a.is_read && (
                      <span className="h-1.5 w-1.5 rounded-full bg-[var(--pq-bronze)] shrink-0" />
                    )}
                    <span className="text-xs text-[rgba(245,240,232,0.6)] tabular-nums whitespace-nowrap">
                      {relativeTimeIntl(a.created_at, locale)}
                    </span>
                    <span className="text-pq-eyebrow tracking-[0.18em] uppercase text-[var(--pq-bronze)] whitespace-nowrap">
                      {kindLabel(a.kind)}
                    </span>
                  </div>

                  {/* Row 2 — Title / message */}
                  <div className="mt-1.5">
                    <div
                      className={cn(
                        "font-serif text-pq-lead text-[var(--pq-ivory)] leading-snug",
                        !a.is_read && "font-semibold",
                      )}
                    >
                      {a.name || a.ticker || kindLabel(a.kind)}
                    </div>
                    {a.name && a.ticker && (
                      <div className="mt-0.5 text-pq-eyebrow tracking-[0.06em] font-mono text-[rgba(245,240,232,0.45)]">
                        {a.ticker}
                      </div>
                    )}
                    {(a.title || a.message) && (
                      <div className="mt-0.5 text-xs text-[rgba(245,240,232,0.6)] leading-relaxed">
                        {a.title || a.message}
                      </div>
                    )}
                    {(a.body || a.message)?.includes("set capital for sizing") && (
                      <Link
                        href="/settings#capital"
                        onClick={(e) => e.stopPropagation()}
                        className="mt-1 inline-block text-pq-eyebrow uppercase tracking-[0.18em] text-[var(--pq-bronze)] hover:underline"
                      >
                        → Set capital in Settings
                      </Link>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}

        {/* Editorial foot signature */}
        <FootSignature />

        {/* ── Clear all ── */}
        {alerts.length > 0 && (
          <div className="flex justify-center pt-4 border-t border-[var(--pq-ivory-line)]">
            <button
              type="button"
              onClick={handleClearAll}
              disabled={clearing}
              className={cn(
                "inline-flex items-center gap-1.5 px-5 py-2 text-xs tracking-[0.18em] uppercase transition-colors",
                confirmClear
                  ? "text-[var(--pq-error)]"
                  : "text-[rgba(245,240,232,0.5)] hover:text-[var(--pq-bronze)]",
                "disabled:opacity-40",
              )}
            >
              <Trash2 className="h-3.5 w-3.5" />
              {confirmClear
                ? t("alertsPage.actions.confirmClear")
                : t("alertsPage.actions.clearAll")}
            </button>
          </div>
        )}
      </div>
    </ErrorBoundary>
  );
}
