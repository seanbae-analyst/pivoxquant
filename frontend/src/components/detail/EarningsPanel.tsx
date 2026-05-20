"use client";

/**
 * Zone3 DOSSIER — Earnings calendar (forward 30-day window).
 *
 * Backend `routes/market.py::earnings_calendar` emits only
 * { ticker, name, date, signal, score } — eps/revenue fields are NOT sent,
 * so the table is Date · Signal · Score (no currency hazard for KRW tickers).
 * Signal labels are POSITIVE/NEGATIVE/NEUTRAL only.
 */

import { CalendarDays } from "lucide-react";
import { SectionHeading } from "./shared";
import type { EarningsItem } from "./types";

export function EarningsPanel({
  displayName,
  items,
}: {
  /** Human-readable name for the empty-state copy (parent already filters the
   * rows by ticker) — never render a naked KR code (feedback_ticker_display). */
  displayName?: string;
  items: EarningsItem[];
}) {
  return (
    <section>
      <div className="mb-5">
        <SectionHeading
          eyebrow="Earnings · forward window"
          title="Earnings calendar"
          icon={
            <CalendarDays className="h-4 w-4 text-[var(--pq-bronze)]" strokeWidth={1.4} />
          }
        />
      </div>
      <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] rounded-sm p-5">
        {items.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-pq-body">
              <thead>
                <tr className="text-left border-b border-[var(--pq-ivory-line)]">
                  <th className="pb-2 font-mono uppercase tracking-[0.16em] text-pq-mono-xs text-[var(--pq-ivory-faint)]">
                    Date
                  </th>
                  <th className="pb-2 font-mono uppercase tracking-[0.16em] text-pq-mono-xs text-[var(--pq-ivory-faint)]">
                    Signal
                  </th>
                  <th className="pb-2 font-mono uppercase tracking-[0.16em] text-pq-mono-xs text-[var(--pq-ivory-faint)] text-right">
                    Score
                  </th>
                </tr>
              </thead>
              <tbody>
                {items.map((e, i) => (
                  <tr
                    key={`${e.date ?? "na"}-${i}`}
                    className="border-b border-[var(--pq-ivory-line-faint)] last:border-0"
                  >
                    <td className="py-2.5 tabular-nums text-[var(--pq-ivory-soft)]">
                      {e.date
                        ? new Date(e.date).toLocaleDateString("en-US", {
                            year: "numeric",
                            month: "short",
                            day: "numeric",
                          })
                        : "—"}
                    </td>
                    <td className="py-2.5 font-mono uppercase tracking-[0.18em] text-pq-mono-xs text-[var(--pq-ivory)]/85">
                      {(e.signal as string | undefined) ?? "—"}
                    </td>
                    <td className="py-2.5 text-right font-mono tabular-nums text-[var(--pq-ivory)]/75">
                      {typeof e.score === "number" ? e.score.toFixed(2) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="pq-detail-caption">
            Next earnings date not available for {displayName || "this stock"} in
            the forward 30-day window.
          </p>
        )}
      </div>
    </section>
  );
}
