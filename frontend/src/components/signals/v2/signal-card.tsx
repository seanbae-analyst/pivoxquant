"use client";

/**
 * <SignalCard /> — single observation row in the v2 timeline.
 *
 * Source: design-mockups/signals-v2/SPEC.md §4 (SignalRow).
 * Grid: 1fr 280px 120px (desktop), stacks on mobile.
 *
 *   Left:  name-main Playfair 22px ivory
 *          ticker-sub mono 11px dim ("AAPL · NASDAQ")
 *          rationale Source Serif 4 14px ivory-soft (2-3 sentences)
 *   Mid:   label pill + "strength 0.91" + 3px bronze bar + price line
 *   Right: timestamp "09:42 KST" mono 11px + "3h ago" subline
 *
 * Whole row is <a href="/detail/${ticker}">. aria-label per SPEC.
 *
 * Legal: POSITIVE / NEGATIVE / NEUTRAL only. "observed" framing.
 */

import * as React from "react";
import Link from "next/link";
import type { SignalEntry, SignalLabel } from "@/lib/types";

interface Props {
  entry: SignalEntry;
  resolveName: (ticker: string) => string;
}

function strengthOf(s: SignalEntry): number {
  if (typeof s.strength === "number") return Math.max(0, Math.min(1, s.strength));
  if (typeof s.score === "number") return Math.max(0, Math.min(1, s.score / 100));
  return 0;
}

function labelOf(s: SignalEntry): SignalLabel {
  const v = (s.label ?? s.signal ?? "").toString().toUpperCase();
  if (v === "POSITIVE") return "POSITIVE";
  if (v === "NEGATIVE") return "NEGATIVE";
  return "NEUTRAL";
}

function labelTone(label: SignalLabel) {
  if (label === "POSITIVE")
    return { fg: "var(--pq-positive, #dc2626)", bg: "rgba(220,38,38,0.08)", display: "Positive" };
  if (label === "NEGATIVE")
    return { fg: "var(--pq-negative, #2563eb)", bg: "rgba(37,99,235,0.08)", display: "Negative" };
  return { fg: "rgba(245,240,232,0.55)", bg: "rgba(245,240,232,0.04)", display: "Neutral" };
}

function fmtPrice(s: SignalEntry): string {
  if (s.price == null) return "—";
  if (s.currency === "KRW" || s.is_korean) {
    return `₩${Math.round(s.price).toLocaleString("ko-KR")}`;
  }
  return `$${s.price.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function fmtPct(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const sign = n >= 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

function fmtKstClock(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "—";
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    return `${hh}:${mm} KST`;
  } catch {
    return "—";
  }
}

function fmtAgo(iso: string | null | undefined): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    const diff = Date.now() - d.getTime();
    if (diff < 0) return "just now";
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  } catch {
    return "";
  }
}

export function SignalCard({ entry, resolveName }: Props) {
  const name = entry.name || resolveName(entry.ticker);
  const label = labelOf(entry);
  const tone = labelTone(label);
  const strength = strengthOf(entry);
  const pct = entry.change_pct ?? null;
  const pctTone =
    pct == null
      ? "rgba(245,240,232,0.55)"
      : pct >= 0
        ? "var(--pq-positive, #dc2626)"
        : "var(--pq-negative, #2563eb)";

  const observed = entry.observed_at ?? null;

  return (
    <Link
      href={`/detail/${entry.ticker}${entry.id != null ? `?signal=${entry.id}` : ""}`}
      prefetch={false}
      aria-label={`${name} · ${entry.ticker} · ${tone.display} · strength ${strength.toFixed(2)} · ${fmtKstClock(observed)}`}
      style={{ textDecoration: "none", color: "inherit" }}
    >
      <article
        className="signal-row"
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 280px 120px",
          gap: 28,
          padding: "20px 0",
          borderBottom: "1px solid var(--pq-hairline, rgba(245,240,232,0.08))",
          transition: "background 200ms cubic-bezier(0.16, 1, 0.3, 1), border-color 200ms",
        }}
      >
        {/* LEFT — name + ticker + rationale */}
        <div style={{ minWidth: 0 }}>
          <div
            className="font-display"
            style={{
              fontSize: 24,
              fontWeight: 500,
              letterSpacing: "-0.01em",
              color: "var(--pq-ivory, #F5F0E8)",
              lineHeight: 1.15,
            }}
          >
            {name}
          </div>
          <div
            className="font-mono"
            style={{
              fontSize: 12,
              letterSpacing: "0.14em",
              color: "rgba(245,240,232,0.45)",
              marginTop: 4,
            }}
          >
            {entry.ticker}
            {entry.exchange ? ` · ${entry.exchange}` : ""}
          </div>
          {entry.rationale && (
            <p
              className="font-serif"
              style={{
                fontSize: 14,
                lineHeight: 1.55,
                color: "rgba(245,240,232,0.78)",
                margin: "10px 0 0 0",
              }}
            >
              {entry.rationale}
            </p>
          )}
        </div>

        {/* MIDDLE — label + strength bar + price */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span
              className="font-mono uppercase"
              style={{
                fontSize: 12,
                letterSpacing: "0.2em",
                padding: "3px 8px",
                border: `1px solid ${tone.fg}`,
                borderRadius: "var(--pq-radius-cta, 2px)",
                background: tone.bg,
                color: tone.fg,
              }}
            >
              {tone.display}
            </span>
            <span
              className="font-mono"
              style={{
                fontSize: 12,
                letterSpacing: "0.04em",
                color: "rgba(245,240,232,0.55)",
                fontVariantNumeric: "tabular-nums",
              }}
            >
              strength {strength.toFixed(2)}
            </span>
            {entry.is_stale && (
              <span
                className="font-mono uppercase"
                title="Cached observation past freshness TTL"
                style={{
                  fontSize: 10,
                  letterSpacing: "0.18em",
                  padding: "2px 6px",
                  border: "1px solid rgba(245,240,232,0.20)",
                  borderRadius: "var(--pq-radius-cta, 2px)",
                  color: "rgba(245,240,232,0.45)",
                  background: "rgba(245,240,232,0.04)",
                }}
              >
                stale
              </span>
            )}
          </div>
          <div
            aria-hidden
            style={{
              height: 3,
              width: "100%",
              background: "rgba(245,240,232,0.06)",
              borderRadius: 2,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                height: "100%",
                width: `${(strength * 100).toFixed(1)}%`,
                background:
                  "linear-gradient(90deg, var(--pq-bronze-deep, #6F5636), var(--pq-bronze, #B8956A))",
              }}
            />
          </div>
          <div
            className="font-mono"
            style={{
              fontSize: 12,
              fontVariantNumeric: "tabular-nums",
              display: "flex",
              gap: 10,
              alignItems: "baseline",
            }}
          >
            <span style={{ color: "rgba(245,240,232,0.78)" }}>{fmtPrice(entry)}</span>
            <span style={{ color: pctTone }}>{fmtPct(pct)}</span>
          </div>
        </div>

        {/* RIGHT — timestamp */}
        <div style={{ textAlign: "right" }}>
          <div
            className="font-mono"
            style={{
              fontSize: 12,
              fontVariantNumeric: "tabular-nums",
              color: "rgba(245,240,232,0.55)",
            }}
          >
            {fmtKstClock(observed)}
          </div>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: 12,
              letterSpacing: "0.06em",
              color: "rgba(245,240,232,0.55)",
              marginTop: 4,
            }}
          >
            {fmtAgo(observed)}
          </div>
        </div>
      </article>
      <style jsx>{`
        :global(.signal-row:hover) {
          background: rgba(184, 149, 106, 0.025);
          border-bottom-color: var(--pq-bronze, #b8956a) !important;
        }
        @media (max-width: 767px) {
          :global(.signal-row) {
            grid-template-columns: 1fr !important;
            gap: 12px !important;
          }
        }
      `}</style>
    </Link>
  );
}
