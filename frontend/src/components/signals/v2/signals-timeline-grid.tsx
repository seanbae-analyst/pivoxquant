"use client";

/**
 * <SignalsTimelineGrid /> — chronological signal stream grouped by day.
 *
 * Source: design-mockups/signals-v2/SPEC.md §4.
 * Renders a vertical list of <SignalCard /> rows with day-rule headings.
 *
 * Handles isLoading skeleton, empty state, and live-region a11y.
 */

import * as React from "react";
import type { SignalEntry } from "@/lib/types";
import { SignalCard } from "./signal-card";

interface Props {
  entries: SignalEntry[];
  isLoading?: boolean;
  resolveName: (ticker: string) => string;
}

function dayKey(iso: string | null | undefined): string {
  if (!iso) return "unknown";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "unknown";
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  } catch {
    return "unknown";
  }
}

function dayHeading(iso: string | null | undefined): { weekday: string; meta: string } {
  if (!iso) return { weekday: "Earlier", meta: "Date unavailable" };
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return { weekday: "Earlier", meta: "Date unavailable" };
    const weekday = d.toLocaleDateString("en-US", { weekday: "long" });
    const day = String(d.getDate());
    const month = d.toLocaleDateString("en-US", { month: "short" });
    return { weekday, meta: `${day} ${month}` };
  } catch {
    return { weekday: "Earlier", meta: "Date unavailable" };
  }
}

export function SignalsTimelineGrid({ entries, isLoading, resolveName }: Props) {
  const grouped = React.useMemo(() => {
    const sorted = [...entries].sort((a, b) => {
      const av = a.observed_at ? new Date(a.observed_at).getTime() : 0;
      const bv = b.observed_at ? new Date(b.observed_at).getTime() : 0;
      return bv - av;
    });
    const out: Array<{ key: string; heading: ReturnType<typeof dayHeading>; rows: SignalEntry[] }> = [];
    let last = "";
    for (const s of sorted) {
      const k = dayKey(s.observed_at);
      if (k !== last) {
        out.push({ key: k, heading: dayHeading(s.observed_at), rows: [] });
        last = k;
      }
      out[out.length - 1].rows.push(s);
    }
    return out;
  }, [entries]);

  if (isLoading && entries.length === 0) {
    return (
      <section style={{ marginBottom: 56 }} aria-busy="true">
        <div
          className="font-mono uppercase"
          style={{
            fontSize: 12,
            letterSpacing: "0.22em",
            color: "var(--pq-bronze, #B8956A)",
            marginBottom: 8,
          }}
        >
          Stream · loading
        </div>
        <div
          className="font-serif"
          style={{
            fontSize: 13,
            color: "rgba(245,240,232,0.40)",
            padding: "48px 0",
            textAlign: "center",
          }}
        >
          Reading observations…
        </div>
      </section>
    );
  }

  if (entries.length === 0) {
    return (
      <section style={{ marginBottom: 56 }}>
        <div
          className="font-mono uppercase"
          style={{
            fontSize: 12,
            letterSpacing: "0.22em",
            color: "var(--pq-bronze, #B8956A)",
            marginBottom: 8,
          }}
        >
          Stream · empty
        </div>
        <div
          style={{
            border: "1px dashed var(--pq-hairline-2, rgba(245,240,232,0.14))",
            borderRadius: "var(--pq-radius-card, 4px)",
            padding: "48px 24px",
            textAlign: "center",
          }}
        >
          <div
            className="font-display"
            style={{
              fontSize: 22,
              color: "var(--pq-ivory, #F5F0E8)",
              marginBottom: 8,
            }}
          >
            No observations match these filters.
          </div>
          <div
            className="font-serif"
            style={{
              fontSize: 13,
              color: "rgba(245,240,232,0.55)",
            }}
          >
            Widen the strength range or extend the time window to see more.
          </div>
        </div>
      </section>
    );
  }

  return (
    <section style={{ marginBottom: 56 }} aria-live="polite" aria-relevant="additions">
      <div
        className="font-mono uppercase"
        style={{
          fontSize: 12,
          letterSpacing: "0.22em",
          color: "var(--pq-bronze, #B8956A)",
          marginBottom: 8,
        }}
      >
        Stream · {entries.length} observations
      </div>
      <h2
        className="font-display"
        style={{
          fontWeight: 500,
          fontSize: "clamp(26px, 3vw, 40px)",
          letterSpacing: "-0.02em",
          color: "var(--pq-ivory, #F5F0E8)",
          margin: "0 0 22px 0",
        }}
      >
        Today&apos;s observations.
      </h2>

      {grouped.map((group) => (
        <div key={group.key}>
          {/* day rule */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "auto auto 1fr",
              gap: 16,
              alignItems: "baseline",
              padding: "20px 0 8px",
              borderTop: "1px solid var(--pq-hairline, rgba(245,240,232,0.08))",
              marginTop: 8,
            }}
          >
            <h3
              className="font-display"
              style={{
                fontWeight: 500,
                fontSize: 22,
                letterSpacing: "-0.01em",
                color: "var(--pq-ivory, #F5F0E8)",
                margin: 0,
              }}
            >
              {group.heading.weekday}
            </h3>
            <span
              className="font-mono uppercase"
              style={{
                fontSize: 12,
                letterSpacing: "0.18em",
                color: "rgba(245,240,232,0.55)",
              }}
            >
              {group.heading.meta} · {group.rows.length} observations
            </span>
            <span aria-hidden style={{ display: "block", height: 1 }} />
          </div>

          {/* rows */}
          <div>
            {group.rows.map((s, idx) => (
              <SignalCard
                key={`${s.ticker}-${s.id ?? idx}-${s.observed_at ?? ""}`}
                entry={s}
                resolveName={resolveName}
              />
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}
