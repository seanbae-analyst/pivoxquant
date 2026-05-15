"use client";

/**
 * TopTicker — PivoxQuant Terminal top strip.
 *
 * 32px-tall Bloomberg-style live ribbon that spans the full width of the
 * dashboard stage. Renders a KST clock, USD/KRW, VIX, and the four
 * headline indices (S&P 500 / NASDAQ 100 / KOSPI / KOSDAQ). Reads live prices
 * from the existing <RealtimeProvider/> SSE stream so we don't open a
 * second EventSource; falls back to a static snapshot when the stream is
 * unavailable or the ticker hasn't been observed yet.
 *
 * Visual language:
 *   - Dark terminal tone: `var(--pq-terminal-bg)` bg, `var(--pq-terminal-line)` hairline rule.
 *   - Bronze (`var(--pq-bronze)`) for the brand pip + delimiters.
 *   - KR convention tick flashes on price change, 0.3s: red (`var(--pq-terminal-up)`) up, blue (`var(--pq-terminal-down)`) down.
 *
 * Legal: observation-only. No BUY/SELL/HOLD. No recommend / advise copy.
 */

import {
  useEffect,
  useMemo,
  useRef,
  useSyncExternalStore,
} from "react";
import useSWR from "swr";
import { useRealtimeContext } from "@/lib/realtime";
import { sanitizeKrIndex } from "@/lib/format";
import { MARKET_INDICES, API } from "@/lib/endpoints";
import { apiFetch } from "@/lib/api";

/* Module-level 1Hz clock — useSyncExternalStore source.
   Subscribers share a single setInterval; cleanup happens when none remain.   */
let nowSnapshot: Date | null = null;
const nowSubs = new Set<() => void>();
let nowTimer: ReturnType<typeof setInterval> | null = null;
function ensureNowTimer(): void {
  if (nowTimer || typeof window === "undefined") return;
  nowSnapshot = new Date();
  nowTimer = setInterval(() => {
    nowSnapshot = new Date();
    nowSubs.forEach((l) => l());
  }, 1000);
}
function subscribeNow(listener: () => void): () => void {
  ensureNowTimer();
  nowSubs.add(listener);
  return () => {
    nowSubs.delete(listener);
    if (nowSubs.size === 0 && nowTimer) {
      clearInterval(nowTimer);
      nowTimer = null;
    }
  };
}
function getNowSnapshot(): Date | null {
  return nowSnapshot;
}
function getNowServerSnapshot(): Date | null {
  // Match the previous behavior: server and first client render see null.
  return null;
}

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
  // True when the upstream feed marked the block stale (KR EOD outside
  // session hours, FMP intraday lag, etc.). Cells dim to ~60% opacity and
  // tag a "STALE" mini-label so users can tell live ribbon values from
  // last-observed values without ambiguity.
  isStale?: boolean;
  // Bug #3 (2026-05-14): when the backend serves a US index level via a
  // liquid ETF proxy (FMP $29 plan 402s on caret-prefixed index symbols),
  // the displayed "level" is the ETF price (e.g. SPY 742.31), NOT the
  // underlying index level (S&P 500 ≈ 5,700). The /market page already
  // discloses this with a "via SPY · ETF proxy" pill — the ribbon used to
  // render the bare "S&P 500" label with no disclosure, which is a
  // capital-markets-law misrepresentation risk. When set, the Cell renders
  // a "VIA <proxy>" chip so the reader knows the number is an ETF proxy.
  proxyTicker?: string;
  // Bug #6 (2026-05-14): when the KR indices SWR poll has SETTLED (data
  // arrived or errored) but carries no usable KOSPI/KOSDAQ block, the
  // ribbon used to render the same "— · —" placeholder it shows during
  // the initial loading window — indistinguishable from "still loading".
  // When `unavailable` is true the Cell renders an explicit "관측 대기"
  // (awaiting observation) state instead. Distinct from `isStale`, which
  // means "we have a value, it's just delayed". Resolution of the upstream
  // KR data path is backend-dev's Bug #2 — this is the honest empty state
  // for the meantime.
  unavailable?: boolean;
};

// Macro symbols the strip tracks. Levels are NEVER hard-coded — every cell
// renders an em-dash placeholder until the SSE stream delivers a real quote.
// (2026-04-28: prior FALLBACK constant carried 2024-vintage levels that drifted
//  60%+ from reality, e.g. KOSPI 2,623 vs actual 6,641. Showing stale numbers
//  as if live is a capital-markets-law misrepresentation risk.)
const PLACEHOLDER_DELTA = "—";
// Note: the `NDX` map key is an internal alias only. Backend keys US indices
// by their ^-prefixed Yahoo symbols (^GSPC, ^IXIC, ^VIX) and proxies `^IXIC`
// via QQQ which tracks NASDAQ 100 (routes/market.py:_US_INDEX_PROXY). The
// user-facing label MUST be "NASDAQ 100" — a bare "NASDAQ" label is
// misleading (NASDAQ Composite ≠ NASDAQ 100; capital-markets-law
// misrepresentation risk per PR #343 audit).
const TRACKED: readonly { symbol: string; label: string }[] = [
  { symbol: "SPX",    label: "S&P 500"    },
  { symbol: "NDX",    label: "NASDAQ 100" },
  { symbol: "KOSPI",  label: "KOSPI"      },
  { symbol: "KOSDAQ", label: "KOSDAQ"     },
  { symbol: "USDKRW", label: "USD/KRW"    },
  { symbol: "VIX",    label: "VIX"        },
];

// Korean market convention (CEO directive 2026-04-26): ▲ red, ▼ blue.
// Resolves to `var(--pq-terminal-up)` / `var(--pq-terminal-down)` defined in
// `globals.css` §6 (W14.2 terminal palette tokens).
const DIR_COLOR = {
  up: "var(--pq-terminal-up)",
  down: "var(--pq-terminal-down)",
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
  // bug-hunter Bug #13: KR indices can return is_stale=true (KOSDAQ outside
  // 09:00-15:30 KST or when the proxy ETF feed is paused). The ribbon used
  // to render the same level/delta as a live cell — visually indistinguishable.
  // Dim to 60% + add a STALE chip so users know the value is last-observed,
  // not live. Resolves the capital-markets-law misrepresentation guard noted
  // in the file header.
  const stale = snap.isStale === true;
  // Bug #3 (2026-05-14): ETF-proxy disclosure. When the level is an ETF
  // price standing in for a caret-prefixed index symbol, surface a
  // "VIA <proxy>" chip so the reader doesn't mistake e.g. SPY 742.31 for
  // the S&P 500 index level (~5,700). Mirrors the /market page disclosure.
  const proxy =
    typeof snap.proxyTicker === "string" && snap.proxyTicker
      ? snap.proxyTicker
      : null;
  // Bug #6 (2026-05-14): the KR poll settled with no usable block. Render an
  // explicit "관측 대기" (awaiting observation) state so the reader can tell
  // this apart from the loading placeholder. Upstream KR data path is
  // backend-dev's Bug #2 — once it returns data this branch is never hit.
  const unavailable = snap.unavailable === true;
  // Direct DOM-mutation flash: avoids setState-in-effect by writing the
  // tinted background straight to the element via ref, then clearing it
  // after 300ms. Behaves identically to the previous setState/setTimeout.
  const cellRef = useRef<HTMLSpanElement>(null);
  const prevFlashRef = useRef<"up" | "down" | null>(null);
  useEffect(() => {
    const prev = prevFlashRef.current;
    prevFlashRef.current = flashDir;
    if (!flashDir || flashDir === prev) return;
    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduced) return;
    const el = cellRef.current;
    if (!el) return;
    el.style.background =
      flashDir === "up"
        ? "rgba(125,180,135,0.22)"
        : "rgba(209,136,136,0.22)";
    const id = window.setTimeout(() => {
      if (cellRef.current) cellRef.current.style.background = "transparent";
    }, 300);
    return () => window.clearTimeout(id);
  }, [flashDir]);

  const color = DIR_COLOR[snap.dir];

  // Respect reduced-motion at render time too, so the background transition
  // property is dropped entirely rather than merely starved of state changes.
  const reducedMotion =
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  return (
    <span
      ref={cellRef}
      className="inline-flex items-center gap-2 whitespace-nowrap px-3 font-mono tabular-nums"
      style={{
        fontSize: "var(--pq-text-eyebrow)",
        lineHeight: 1,
        background: "transparent",
        transition: reducedMotion ? "none" : "background-color 0.3s ease",
        opacity: stale ? 0.6 : 1,
      }}
      title={
        unavailable
          ? `${snap.label} — market data temporarily unavailable`
          : stale
            ? `${snap.label} — last observed (delayed)`
            : proxy
              ? `Level sourced from ${proxy} ETF proxy — this is the ETF price, not the underlying ${snap.label} index level.`
              : undefined
      }
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
      {unavailable ? (
        <span
          style={{
            color: "rgba(245,240,232,0.45)",
            letterSpacing: "0.04em",
          }}
        >
          관측 대기
        </span>
      ) : (
        <>
          <span style={{ color: "rgba(245,240,232,0.92)" }}>{snap.level}</span>
          <span style={{ color }}>
            <span style={{ marginRight: 2 }}>{DIR_GLYPH[snap.dir]}</span>
            {snap.delta}
          </span>
        </>
      )}
      {!unavailable && proxy && (
        <span
          className="uppercase"
          aria-label={`Level via ${proxy} ETF proxy`}
          style={{
            fontSize: "var(--pq-text-kicker)",
            letterSpacing: "0.18em",
            padding: "1px 4px",
            border: "0.5px solid rgba(184,149,106,0.4)",
            color: "var(--pq-bronze, #B8956A)",
            borderRadius: 2,
          }}
        >
          via {proxy}
        </span>
      )}
      {!unavailable && stale && (
        <span
          className="uppercase"
          aria-label="Stale market data"
          style={{
            fontSize: "var(--pq-text-kicker)",
            letterSpacing: "0.18em",
            padding: "1px 4px",
            border: "0.5px solid rgba(245,240,232,0.25)",
            color: "rgba(245,240,232,0.55)",
            borderRadius: 2,
          }}
        >
          STALE
        </span>
      )}
    </span>
  );
}

/** Map a /market/indices block onto our ribbon symbol. */
function _macroFromIndex(block: IndexBlock | undefined, symbol: string):
  | { level: string; pct: number | null; isStale: boolean; proxyTicker?: string }
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
  // Bug #11: preserve null when the upstream block omits change_1d_pct so
  // a missing-data state is distinguishable from a real flat 0.00% day.
  // The render layer maps null → "—" placeholder, while 0 → "0.00%".
  const pct: number | null =
    typeof block.change_1d_pct === "number" ? block.change_1d_pct : null;
  // Format level — KR indices use comma-grouping with 2 decimals, USD/KRW
  // is a 4-digit FX value with 2 decimals (Bug #11: prior `maximumFractionDigits: 0`
  // truncated "1,487.48" to "1,487", which combined with the missing
  // change% rendered as "1,487 · —" — visually identical to a clipped
  // value. KR FX desks quote USDKRW to 2 decimals.)
  let levelStr: string;
  if (symbol === "USDKRW") {
    levelStr = level.toLocaleString("ko-KR", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  } else {
    levelStr = level.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }
  // Bug #3: forward proxy_ticker so the ribbon can disclose ETF-proxied
  // US index levels. KR indices and FX never carry one.
  return {
    level: levelStr,
    pct,
    isStale: block.is_stale === true,
    proxyTicker:
      typeof block.proxy_ticker === "string" && block.proxy_ticker
        ? block.proxy_ticker
        : undefined,
  };
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
  const { data: krIdx, error: krError } = useSWR<IndexBlock[]>(
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
      // change. If the indices payload doesn't carry a numeric change yet,
      // prefer the KR-block fallback rather than synthesizing 0%, so the
      // delta cell shows "—" only when the upstream truly omits it. (Bug
      // #11: previous `?? 0` coerced missing data to 0 → "—" placeholder
      // was indistinguishable from a real flat day, and visually clipped
      // the line to "1,487 · —".)
      const krUsdKrw = find(krIdx, "USDKRW");
      const krPct =
        typeof krUsdKrw?.change_1d_pct === "number"
          ? krUsdKrw.change_1d_pct
          : null;
      m.set("USDKRW", {
        ticker: "USDKRW",
        name: "USD/KRW",
        level: fxData.usd_krw,
        // `null as unknown as number` — IndexBlock declares change_1d_pct
        // as required; _macroFromIndex below already guards with typeof.
        change_1d_pct: (krPct ?? null) as unknown as number,
        // Forward `is_stale` so the ribbon dims when /api/market/fx is stale
        // (offline FX feed) — Bug #13 follow-through.
        is_stale: fxData.is_stale === true,
      });
    }
    return m;
  }, [usIdx, krIdx, fxData]);

  // Start with null so the server and the first client render agree
  // (both produce the placeholder). The real time is filled in after
  // mount, avoiding a hydration mismatch on the KST clock span.
  const now = useSyncExternalStore(
    subscribeNow,
    getNowSnapshot,
    getNowServerSnapshot,
  );

  // Bug #6: the KR indices poll has SETTLED once SWR has either delivered a
  // payload (`krIdx` defined) or surfaced an error (`krError`). Before that
  // we're genuinely still loading and "— · —" is the honest placeholder.
  const krSettled = krIdx !== undefined || krError != null;

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
        // Bug #11: macro.pct === null now means "upstream didn't carry a
        // change" (render placeholder) while macro.pct === 0 means
        // "upstream sent a flat 0.00%" (render "0.00%"). Resolves the
        // USDKRW "1,487 · —" ambiguity.
        const dir: Snapshot["dir"] =
          macro.pct == null
            ? "flat"
            : macro.pct > 0
              ? "up"
              : macro.pct < 0
                ? "down"
                : "flat";
        return {
          symbol: t.symbol,
          label: t.label,
          level: macro.level,
          delta:
            macro.pct == null
              ? PLACEHOLDER_DELTA
              : `${macro.pct >= 0 ? "+" : ""}${macro.pct.toFixed(2)}%`,
          dir,
          isStale: macro.isStale,
          proxyTicker: macro.proxyTicker,
        };
      }
      // Bug #6: no SSE detail, no macro block. For KR indices, if the KR
      // poll has already settled this is "data unavailable" — render the
      // explicit 관측 대기 state rather than a loading-looking "— · —".
      // For US symbols (or KR before settle) keep the neutral placeholder.
      const isKr = t.symbol === "KOSPI" || t.symbol === "KOSDAQ";
      return {
        symbol: t.symbol,
        label: t.label,
        level: PLACEHOLDER_DELTA,
        delta: PLACEHOLDER_DELTA,
        dir: "flat" as const,
        unavailable: isKr && krSettled,
      };
    });
  }, [rt.details, macroMap, krSettled]);

  return (
    /* Mobile fix (2026-05-05): the 6 cells + brand pip total ~700px which
       overflows 375px viewport. overflow-x-auto already lets the strip
       scroll; we add a right-fade mask so users discover the scrollable
       content, and hide the scrollbar to keep the editorial tone. */
    <div
      className="flex items-center overflow-x-auto scrollbar-hide"
      role="status"
      aria-label="Market ticker"
      style={{
        height: 32,
        width: "100%",
        background: "var(--pq-terminal-bg)",
        borderTop: "1px solid var(--pq-terminal-line)",
        borderBottom: "1px solid var(--pq-terminal-line)",
        WebkitMaskImage:
          "linear-gradient(to right, black 0%, black 88%, transparent 100%)",
        maskImage:
          "linear-gradient(to right, black 0%, black 88%, transparent 100%)",
      }}
    >
      {/* Brand + clock pip */}
      <span
        className="inline-flex items-center gap-2 whitespace-nowrap pl-4 pr-3 font-mono"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          lineHeight: 1,
          color: "var(--pq-bronze, #B8956A)",
          letterSpacing: "0.2em",
          borderRight: "1px solid var(--pq-terminal-line)",
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
                borderRight: "1px solid var(--pq-terminal-line)",
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
          fontSize: "var(--pq-text-kicker)",
          letterSpacing: "0.22em",
          color: rt.connected
            ? "rgba(125,180,135,0.85)"
            : "rgba(245,240,232,0.55)",
          textTransform: "uppercase",
        }}
      >
        {rt.connected ? "● Live" : "○ Delayed"}
      </span>
    </div>
  );
}

export default TopTicker;
