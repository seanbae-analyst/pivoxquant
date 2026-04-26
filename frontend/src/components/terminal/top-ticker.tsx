"use client";

/**
 * TopTicker — PivoxQuant Terminal top strip.
 *
 * 32px-tall Bloomberg-style live ribbon that spans the full width of the
 * dashboard stage. Renders a KST clock, USD/KRW, VIX, and the four
 * headline indices (S&P 500 / NASDAQ / KOSPI / KOSDAQ). Reads live prices
 * from the existing <RealtimeProvider/> SSE stream so we don't open a
 * second EventSource; falls back to a static snapshot when the stream is
 * unavailable or the ticker hasn't been observed yet.
 *
 * Visual language:
 *   - Dark terminal tone: #0B0E14 bg, #1A1F2E hairline rule.
 *   - Bronze (#B8956A) for the brand pip + delimiters.
 *   - KR convention tick flashes on price change, 0.3s: red (#D18888) up, blue (#7AA0C8) down.
 *
 * Legal: observation-only. No BUY/SELL/HOLD. No recommend / advise copy.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useRealtimeContext } from "@/lib/realtime";

type Snapshot = {
  symbol: string;
  label: string;
  level: string;
  delta: string;
  dir: "up" | "down" | "flat";
};

// Static fallback levels — sourced from the existing landing marquee so
// the strip is populated on first paint before SSE resolves.
const FALLBACK: readonly Snapshot[] = [
  { symbol: "SPX",    label: "S&P 500",  level: "5,812.44", delta: "+0.12%", dir: "up" },
  { symbol: "NDX",    label: "NASDAQ",   level: "20,437.12", delta: "-0.38%", dir: "down" },
  { symbol: "KOSPI",  label: "KOSPI",    level: "2,623.30", delta: "+0.46%", dir: "up" },
  { symbol: "KOSDAQ", label: "KOSDAQ",   level: "744.83",   delta: "-0.21%", dir: "down" },
  { symbol: "USDKRW", label: "USD/KRW",  level: "1,438.20", delta: "+0.04%", dir: "flat" },
  { symbol: "VIX",    label: "VIX",      level: "17.23",    delta: "+1.83%", dir: "up" },
];

// Korean market convention (CEO directive 2026-04-26): ▲ red, ▼ blue.
const DIR_COLOR = {
  up: "#D18888",
  down: "#7AA0C8",
  flat: "rgba(245,240,232,0.55)",
} as const;

const DIR_GLYPH = {
  up: "▲",
  down: "▼",
  flat: "·",
} as const;

function fmtKST(d: Date): string {
  // Render wall clock in KST regardless of user locale.
  const hh = d.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZone: "Asia/Seoul",
    hour12: false,
  });
  return `${hh} KST`;
}

function Cell({ snap, flashDir }: { snap: Snapshot; flashDir: "up" | "down" | null }) {
  const [flash, setFlash] = useState<"up" | "down" | null>(null);
  const prevFlashRef = useRef<"up" | "down" | null>(null);
  useEffect(() => {
    if (flashDir && flashDir !== prevFlashRef.current) {
      const reduced =
        typeof window !== "undefined" &&
        window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      prevFlashRef.current = flashDir;
      if (!reduced) {
        setFlash(flashDir);
        const id = setTimeout(() => setFlash(null), 300);
        return () => clearTimeout(id);
      }
      return;
    }
    prevFlashRef.current = flashDir;
  }, [flashDir]);

  const color = DIR_COLOR[snap.dir];
  const bgFlash =
    flash === "up"
      ? "rgba(125,180,135,0.22)"
      : flash === "down"
        ? "rgba(209,136,136,0.22)"
        : "transparent";

  // Respect reduced-motion at render time too, so the background transition
  // property is dropped entirely rather than merely starved of state changes.
  const reducedMotion =
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  return (
    <span
      className="inline-flex items-center gap-2 whitespace-nowrap px-3 font-mono tabular-nums"
      style={{
        fontSize: 10.5,
        lineHeight: 1,
        background: bgFlash,
        transition: reducedMotion ? "none" : "background-color 0.3s ease",
      }}
    >
      <span
        className="uppercase"
        style={{
          letterSpacing: "0.18em",
          color: "rgba(245,240,232,0.52)",
        }}
      >
        {snap.label}
      </span>
      <span style={{ color: "rgba(245,240,232,0.92)" }}>{snap.level}</span>
      <span style={{ color }}>
        <span style={{ marginRight: 2 }}>{DIR_GLYPH[snap.dir]}</span>
        {snap.delta}
      </span>
    </span>
  );
}

export function TopTicker() {
  const rt = useRealtimeContext();
  // Start with null so the server and the first client render agree
  // (both produce the placeholder). The real time is filled in after
  // mount, avoiding a hydration mismatch on the KST clock span.
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  // Merge SSE details (if any tickers overlap) into the static snapshot.
  const rows: Snapshot[] = useMemo(() => {
    return FALLBACK.map((s) => {
      const d = rt.details[s.symbol];
      if (!d) return s;
      const pct = d.change_pct;
      const dir: Snapshot["dir"] =
        typeof pct === "number" && pct > 0
          ? "up"
          : typeof pct === "number" && pct < 0
            ? "down"
            : "flat";
      const deltaStr =
        typeof pct === "number" ? `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%` : s.delta;
      return {
        ...s,
        level: d.price_display || s.level,
        delta: deltaStr,
        dir,
      };
    });
  }, [rt.details]);

  return (
    <div
      className="flex items-center overflow-x-auto"
      role="status"
      aria-label="Market ticker"
      style={{
        height: 32,
        width: "100%",
        background: "#0B0E14",
        borderTop: "1px solid #1A1F2E",
        borderBottom: "1px solid #1A1F2E",
      }}
    >
      {/* Brand + clock pip */}
      <span
        className="inline-flex items-center gap-2 whitespace-nowrap pl-4 pr-3 font-mono"
        style={{
          fontSize: 10.5,
          lineHeight: 1,
          color: "var(--pq-bronze, #B8956A)",
          letterSpacing: "0.2em",
          borderRight: "1px solid #1A1F2E",
        }}
      >
        <span
          aria-hidden
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: "var(--pq-bronze, #B8956A)",
            boxShadow: "0 0 8px rgba(184,149,106,0.5)",
            display: "inline-block",
          }}
        />
        <span className="uppercase">PIVOX</span>
        <span style={{ color: "rgba(245,240,232,0.72)" }}>
          {now ? fmtKST(now) : "--:--:-- KST"}
        </span>
      </span>

      {/* Ticker cells */}
      <div className="flex items-center" style={{ gap: 0 }}>
        {rows.map((snap) => {
          const dirFromRt = rt.updatedTickers.get(snap.symbol) ?? null;
          return (
            <span
              key={snap.symbol}
              style={{
                borderRight: "1px solid #1A1F2E",
                display: "inline-flex",
                alignItems: "center",
                height: 32,
              }}
            >
              <Cell snap={snap} flashDir={dirFromRt} />
            </span>
          );
        })}
      </div>

      {/* Connection pip on the far right */}
      <span
        className="ml-auto pr-4 font-mono"
        style={{
          fontSize: 9,
          letterSpacing: "0.22em",
          color: rt.connected
            ? "rgba(125,180,135,0.85)"
            : "rgba(245,240,232,0.35)",
          textTransform: "uppercase",
        }}
      >
        {rt.connected ? "● Live" : "○ Delayed"}
      </span>
    </div>
  );
}

export default TopTicker;
