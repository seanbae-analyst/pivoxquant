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
import useSWR from "swr";
import { useRealtimeContext } from "@/lib/realtime";
import { sanitizeKrIndex } from "@/lib/format";
import { MARKET_INDICES, API } from "@/lib/endpoints";
import { apiFetch } from "@/lib/api";

/* Macro feed via /api/market/indices — SSE portfolio-stream carries position
 * tickers only, so the ribbon's macro symbols (SPX/NDX/KOSPI/KOSDAQ/VIX) used
 * to render permanent em-dashes (HANDOVER P1-9). Two SWR polls (US + KR) at
 * 60s give live levels without opening a second EventSource. */
interface IndexBlock {
  ticker: string;
  name: string;
  level: number;
  change_1d_pct: number;
  is_stale?: boolean;
  proxy_ticker?: string;
}
const fetchIndices = async (url: string): Promise<IndexBlock[]> =>
  apiFetch<IndexBlock[]>(url);

type Snapshot = {
  symbol: string;
  label: string;
  level: string;
  delta: string;
  dir: "up" | "down" | "flat";
};

// Macro symbols the strip tracks. Levels are NEVER hard-coded — every cell
// renders an em-dash placeholder until the SSE stream delivers a real quote.
// (2026-04-28: prior FALLBACK constant carried 2024-vintage levels that drifted
//  60%+ from reality, e.g. KOSPI 2,623 vs actual 6,641. Showing stale numbers
//  as if live is a capital-markets-law misrepresentation risk.)
const PLACEHOLDER_DELTA = "—";
const TRACKED: readonly { symbol: string; label: string }[] = [
  { symbol: "SPX",    label: "S&P 500" },
  { symbol: "NDX",    label: "NASDAQ"  },
  { symbol: "KOSPI",  label: "KOSPI"   },
  { symbol: "KOSDAQ", label: "KOSDAQ"  },
  { symbol: "USDKRW", label: "USD/KRW" },
  { symbol: "VIX",    label: "VIX"     },
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

/** Map a /market/indices block onto our ribbon symbol. */
function _macroFromIndex(block: IndexBlock | undefined, symbol: string):
  | { level: string; pct: number }
  | null {
  if (!block || typeof block.level !== "number") return null;
  // KR sanity boundary at the consumer too — protects from cached
  // stale payloads that bypass the backend filter.
  let level = block.level;
  if (symbol === "KOSPI" || symbol === "KOSDAQ") {
    const safe = sanitizeKrIndex(symbol, level);
    if (safe == null) return null;
    level = safe;
  }
  const pct = typeof block.change_1d_pct === "number" ? block.change_1d_pct : 0;
  // Format level — KR indices use comma-grouping with 2 decimals, USD/KRW
  // is a 4-digit FX value, US/VIX use 2 decimals.
  let levelStr: string;
  if (symbol === "USDKRW") {
    levelStr = level.toLocaleString("ko-KR", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    });
  } else {
    levelStr = level.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }
  return { level: levelStr, pct };
}

const RIBBON_SWR_OPTS = {
  refreshInterval: 60_000,
  revalidateOnFocus: false,
  revalidateOnReconnect: true,
  dedupingInterval: 30_000,
  errorRetryCount: 1,
} as const;

export function TopTicker() {
  const rt = useRealtimeContext();

  // Macro feed — two SWR polls (US + KR) populate the ribbon symbols that
  // SSE doesn't carry. portfolio-stream remains the price source for
  // user-held tickers; this is purely additive.
  const { data: usIdx } = useSWR<IndexBlock[]>(
    `${MARKET_INDICES}?region=us`,
    fetchIndices,
    RIBBON_SWR_OPTS,
  );
  const { data: krIdx } = useSWR<IndexBlock[]>(
    `${MARKET_INDICES}?region=kr`,
    fetchIndices,
    RIBBON_SWR_OPTS,
  );
  const { data: fxData } = useSWR<{ usd_krw?: number; is_stale?: boolean }>(
    API.market.fx,
    fetchIndices as unknown as (u: string) => Promise<{ usd_krw?: number }>,
    RIBBON_SWR_OPTS,
  );

  // Build a symbol → block lookup once per data change.
  const macroMap = useMemo(() => {
    const m = new Map<string, IndexBlock>();
    const find = (arr: IndexBlock[] | undefined, ticker: string) =>
      (arr ?? []).find((b) => b.ticker === ticker);
    const spy = find(usIdx, "^GSPC");
    if (spy) m.set("SPX", spy);
    const ixic = find(usIdx, "^IXIC");
    if (ixic) m.set("NDX", ixic);
    const vix = find(usIdx, "^VIX");
    if (vix) m.set("VIX", vix);
    const ks = find(krIdx, "^KS11");
    if (ks) m.set("KOSPI", ks);
    const kq = find(krIdx, "^KQ11");
    if (kq) m.set("KOSDAQ", kq);
    if (typeof fxData?.usd_krw === "number" && fxData.usd_krw > 0) {
      // Pull change_1d_pct from the KR indices payload when available — the
      // /api/market/fx endpoint only carries the level, but
      // /api/market/indices?region=kr already exposes USDKRW with a daily
      // change. Falls back to 0 when the indices endpoint is empty/loading.
      const krUsdKrw = find(krIdx, "USDKRW");
      m.set("USDKRW", {
        ticker: "USDKRW",
        name: "USD/KRW",
        level: fxData.usd_krw,
        change_1d_pct: krUsdKrw?.change_1d_pct ?? 0,
      });
    }
    return m;
  }, [usIdx, krIdx, fxData]);

  // Start with null so the server and the first client render agree
  // (both produce the placeholder). The real time is filled in after
  // mount, avoiding a hydration mismatch on the KST clock span.
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  // Build rows: SSE detail wins (intra-second freshness for held tickers);
  // SWR macro feed fills the rest. Either path renders "—" if the symbol
  // has no live data (legal: never fabricate a level).
  const rows: Snapshot[] = useMemo(() => {
    return TRACKED.map((t) => {
      const sse = rt.details[t.symbol];
      if (sse) {
        if (t.symbol === "KOSPI" || t.symbol === "KOSDAQ") {
          if (sanitizeKrIndex(t.symbol, sse.price) == null) {
            return {
              symbol: t.symbol,
              label: t.label,
              level: PLACEHOLDER_DELTA,
              delta: PLACEHOLDER_DELTA,
              dir: "flat" as const,
            };
          }
        }
        const pct = sse.change_pct;
        const dir: Snapshot["dir"] =
          typeof pct === "number" && pct > 0
            ? "up"
            : typeof pct === "number" && pct < 0
              ? "down"
              : "flat";
        const deltaStr =
          typeof pct === "number"
            ? `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`
            : PLACEHOLDER_DELTA;
        return {
          symbol: t.symbol,
          label: t.label,
          level: sse.price_display || PLACEHOLDER_DELTA,
          delta: deltaStr,
          dir,
        };
      }
      // Fallback: macro SWR feed for ribbon-only symbols (SPX/NDX/KOSPI/...).
      const macro = _macroFromIndex(macroMap.get(t.symbol), t.symbol);
      if (macro) {
        const dir: Snapshot["dir"] =
          macro.pct > 0 ? "up" : macro.pct < 0 ? "down" : "flat";
        return {
          symbol: t.symbol,
          label: t.label,
          level: macro.level,
          delta:
            macro.pct === 0
              ? PLACEHOLDER_DELTA
              : `${macro.pct >= 0 ? "+" : ""}${macro.pct.toFixed(2)}%`,
          dir,
        };
      }
      return {
        symbol: t.symbol,
        label: t.label,
        level: PLACEHOLDER_DELTA,
        delta: PLACEHOLDER_DELTA,
        dir: "flat" as const,
      };
    });
  }, [rt.details, macroMap]);

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
