"use client";

/**
 * /home — PivoxQuant Executive Dossier.
 *
 * Radical departure from the card-grid paradigm. The home screen is
 * now a desk: Vantablack ink + ivory spotlight + three stacked paper
 * documents that the user peers down onto like morning briefing pages
 * on a mahogany desk.
 *
 * Data, SWR hooks, SSE real-time stream, legal scrub, KRW/USD split,
 * DisclaimerBanner — all preserved from the previous /home. Only the
 * render layer has been redesigned.
 *
 * Papers:
 *   1. ThisMorningPaper      — editorial hero + NAV count-up (front)
 *   2. PositionsLedgerPaper  — editorial positions table (middle, -4°)
 *   3. SignalPaper           — observation of the day (back, -7°)
 *
 * Click any paper → lifts flat + front; others dim + recede.
 * Pointer tilt across desk → whole stack rocks ±1.5°. Disabled under
 * prefers-reduced-motion and < 768px viewports (stacks vertically).
 *
 * Legal: POSITIVE / NEGATIVE / NEUTRAL only. DisclaimerBanner retained
 * at the foot of the page — lifted from the prior implementation.
 */

import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";

import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { FootSignature } from "@/components/ui/editorial";
import { MarketTicker } from "@/components/landing/market-ticker";

import { DossierDesk } from "@/components/home/dossier-desk";
import { PaperDocument } from "@/components/home/paper-document";
import { ThisMorningPaper } from "@/components/home/this-morning-paper";
import { PositionsLedgerPaper } from "@/components/home/positions-ledger-paper";
import { SignalPaper } from "@/components/home/signal-paper";

import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  API,
  PORTFOLIO_SUMMARY,
  PORTFOLIO_POSITIONS,
} from "@/lib/endpoints";
import { liveRefresh, isMarketOpen } from "@/lib/market-hours";
import { relativeTime } from "@/components/ui/price-with-timestamp";
import type { Position } from "@/components/portfolio/types";

/* ── Response shapes ── */

interface SummaryResponse {
  totalNav?: number;
  todayPnl?: number;
  todayPnlPct?: number;
  unrealized?: number;
  positionCount?: number;
  observed_at?: string;
}
interface PositionsResponse {
  positions?: Position[];
}
interface MorningBriefBody {
  insight?: string;
  summary?: string;
}
interface MorningBriefResponse {
  available?: boolean;
  brief?: MorningBriefBody;
}

const fetcher = <T,>(url: string) => apiFetch<T>(url);

/** Format the top-strip date: "DAILY DOSSIER · 2026-04-22 · TUESDAY · 08:32 KST" */
function fmtDeskDate(d: Date): string {
  const weekday = d
    .toLocaleDateString("en-US", { weekday: "long" })
    .toUpperCase();
  const iso = d.toISOString().slice(0, 10);
  const time = d.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return `DAILY DOSSIER · ${iso} · ${weekday} · ${time} KST`;
}

/* ── Page ── */

export default function HomePage() {
  const { user } = useAuth();

  // Live SWR options — match legacy cadence so the SSE provider still
  // enjoys the same dedupe window and focus-revalidation behaviour.
  const liveOpts = {
    refreshInterval: () => liveRefresh(5_000, 60_000),
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    dedupingInterval: 2_000,
    errorRetryCount: 2,
    errorRetryInterval: 5_000,
  } as const;
  const briefOpts = {
    refreshInterval: 600_000,
    revalidateOnFocus: false,
    revalidateOnReconnect: true,
    dedupingInterval: 60_000,
    errorRetryCount: 2,
    errorRetryInterval: 10_000,
  } as const;

  const { data: summary } = useSWR<SummaryResponse>(
    PORTFOLIO_SUMMARY,
    fetcher,
    liveOpts,
  );
  const { data: posData } = useSWR<PositionsResponse>(
    PORTFOLIO_POSITIONS,
    fetcher,
    liveOpts,
  );
  const { data: brief } = useSWR<MorningBriefResponse>(
    API.market.morningBriefToday,
    fetcher,
    briefOpts,
  );

  const positions = useMemo(() => posData?.positions ?? [], [posData]);

  const positionCount = summary?.positionCount ?? positions.length;

  // Currency — if every loaded position is KRW, render the book in KRW.
  // Otherwise default to USD (the backend summary is USD-normalised).
  const bookCurrency: "USD" | "KRW" =
    positions.length > 0 && positions.every((p) => p.currency === "KRW")
      ? "KRW"
      : "USD";

  const briefText =
    brief?.available !== false
      ? brief?.brief?.insight ?? brief?.brief?.summary ?? null
      : null;

  const displayName = user?.name?.split(" ")[0] || "Observer";

  /* ── Top-strip clock ── */
  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 30_000);
    return () => clearInterval(id);
  }, []);
  const now = new Date(nowMs);
  const marketOpen = isMarketOpen();
  const observedAt = summary?.observed_at;

  /* ── Active-paper controller ── */
  type PaperId = "morning" | "ledger" | "signal";
  const [active, setActive] = useState<PaperId | null>(null);
  const onSelect = (id: PaperId) =>
    setActive((cur) => (cur === id ? null : id));

  return (
    <ErrorBoundary>
      {/* ═══════════ TOP STRIP — embossed seal + ticker ═══════════ */}
      <header
        className="flex flex-col gap-3"
        style={{
          marginTop: "-8px",
          marginBottom: 28,
          borderBottom: "0.5px solid rgba(184,149,106,0.22)",
          paddingBottom: 14,
        }}
      >
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3 min-w-0">
            <span className="pq-emboss-seal" aria-hidden>
              PivoxQuant
            </span>
            <span
              className="font-mono uppercase hidden sm:inline-block"
              style={{
                fontSize: 9.5,
                letterSpacing: "0.26em",
                color: "rgba(245,240,232,0.55)",
                borderLeft: "0.5px solid rgba(184,149,106,0.3)",
                paddingLeft: 14,
                whiteSpace: "nowrap",
              }}
            >
              {fmtDeskDate(now)}
            </span>
          </div>
          <div className="hidden md:flex items-center gap-1.5 font-mono tabular-nums text-[10px]">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                marketOpen
                  ? "bg-[#7db487] animate-pulse"
                  : "bg-[var(--pq-bronze)] opacity-50"
              }`}
            />
            <span
              className="uppercase tracking-[0.22em]"
              style={{ color: "var(--pq-bronze)" }}
            >
              {marketOpen ? "Live" : "After Hours"}
            </span>
            {observedAt && (
              <span style={{ color: "rgba(245,240,232,0.5)" }}>
                · observed {relativeTime(observedAt, nowMs)}
              </span>
            )}
          </div>
        </div>
        <div
          style={{
            marginLeft: -32,
            marginRight: -40,
            borderTop: "0.5px solid rgba(184,149,106,0.18)",
            borderBottom: "0.5px solid rgba(184,149,106,0.18)",
          }}
        >
          <MarketTicker />
        </div>
      </header>

      {/* ═══════════ THE DESK ═══════════ */}
      <DossierDesk>
        {/* ── Desktop: 3D stacked papers ── */}
        <div
          className="hidden md:block relative"
          style={{ margin: "0 auto", maxWidth: 980, padding: "60px 0 40px" }}
        >
          {/* Paper 3 — Signal (deepest, left fan) */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              top: 80,
              zIndex: active === "signal" ? 30 : 1,
            }}
          >
            <PaperDocument
              rotation={-6.5}
              zOffset={-90}
              xOffset={-70}
              active={active === "signal"}
              dimmed={active !== null && active !== "signal"}
              onClick={() => onSelect("signal")}
              ariaLabel="Today's signal paper"
            >
              <SignalPaper positions={positions} />
            </PaperDocument>
          </div>

          {/* Paper 2 — Ledger (mid, right fan) */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              top: 40,
              zIndex: active === "ledger" ? 30 : 2,
            }}
          >
            <PaperDocument
              rotation={-3.5}
              zOffset={-40}
              xOffset={48}
              active={active === "ledger"}
              dimmed={active !== null && active !== "ledger"}
              onClick={() => onSelect("ledger")}
              ariaLabel="Positions ledger paper"
            >
              <PositionsLedgerPaper positions={positions} />
            </PaperDocument>
          </div>

          {/* Paper 1 — This Morning (front) */}
          <div
            style={{
              position: "relative",
              zIndex: active === "morning" || active === null ? 20 : 10,
            }}
          >
            <PaperDocument
              rotation={0}
              zOffset={0}
              xOffset={0}
              active={active === "morning"}
              dimmed={active !== null && active !== "morning"}
              onClick={() => onSelect("morning")}
              ariaLabel="This morning editorial paper"
            >
              <ThisMorningPaper
                totalNav={summary?.totalNav}
                todayPnl={summary?.todayPnl}
                todayPnlPct={summary?.todayPnlPct}
                positionCount={positionCount}
                currency={bookCurrency}
                brief={briefText}
                displayName={displayName}
                active={active === "morning"}
              />
            </PaperDocument>
          </div>

          {/* Spacer reserves footprint for the deepest paper */}
          <div aria-hidden style={{ height: 560 }} />

          <p
            style={{
              textAlign: "center",
              fontFamily: "var(--font-serif), Georgia, serif",
              fontSize: 11.5,
              color: "rgba(245,240,232,0.4)",
              letterSpacing: "0.02em",
              marginTop: 36,
            }}
          >
            {active
              ? "Click the surfaced sheet again to return it to the stack."
              : "Click any sheet to draw it forward."}
          </p>
        </div>

        {/* ── Mobile: vertical flat stack ── */}
        <div
          className="md:hidden flex flex-col gap-5"
          style={{ padding: "16px 0 24px" }}
        >
          <PaperDocument
            rotation={0}
            zOffset={0}
            xOffset={0}
            ariaLabel="This morning editorial paper"
          >
            <ThisMorningPaper
              totalNav={summary?.totalNav}
              todayPnl={summary?.todayPnl}
              todayPnlPct={summary?.todayPnlPct}
              positionCount={positionCount}
              currency={bookCurrency}
              brief={briefText}
              displayName={displayName}
              active
            />
          </PaperDocument>

          <PaperDocument
            rotation={0}
            zOffset={0}
            xOffset={0}
            ariaLabel="Positions ledger paper"
          >
            <PositionsLedgerPaper positions={positions} />
          </PaperDocument>

          <PaperDocument
            rotation={0}
            zOffset={0}
            xOffset={0}
            ariaLabel="Today's signal paper"
          >
            <SignalPaper positions={positions} />
          </PaperDocument>
        </div>
      </DossierDesk>

      {/* Foot signature + legal */}
      <FootSignature />
      <DisclaimerBanner type="signal" />
    </ErrorBoundary>
  );
}
