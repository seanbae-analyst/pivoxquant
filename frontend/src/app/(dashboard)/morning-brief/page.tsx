"use client";

/**
 * /morning-brief — Today's pre-market briefing, Vantablack ink theme.
 *
 * Sections:
 *  - Hero: today's date + kicker
 *  - Overnight: Asia / Europe / US pre-market 3-up
 *  - Macro strip: 10Y, VIX, USD/KRW, Gold, Oil
 *  - Earnings today
 *  - Economic calendar
 *  - Archive (expandable)
 *  - Download PDF CTA
 *
 * Legal: POSITIVE / NEGATIVE / NEUTRAL only.
 */

import { useMemo, useState } from "react";
import {
  Sunrise,
  Sparkles,
  TrendingUp,
  TrendingDown,
  Minus,
  Download,
  ChevronDown,
  ChevronUp,
  CalendarDays,
} from "lucide-react";
import { useMorningBrief, useMorningBriefArchive } from "@/lib/hooks";
import { useLocale } from "@/lib/locale";
import { cn } from "@/lib/utils";
import { pctColorClass } from "@/lib/format";
import { relativeTime, useNowTick } from "@/components/market/index-card";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import {
  Caption,
  Fleuron,
  FootSignature,
  RuledKicker,
} from "@/components/ui/editorial";
import type {
  MorningBriefArchiveItem,
  MorningBriefIndex,
} from "@/lib/types";

/* ── Helpers ── */

function fmtPctSigned(pct: number | undefined): string {
  if (pct == null || !Number.isFinite(pct)) return "—";
  const s = pct >= 0 ? "+" : "";
  return `${s}${pct.toFixed(2)}%`;
}

function pctIcon(pct: number | undefined) {
  if (pct == null) return <Minus className="h-3 w-3" />;
  if (pct > 0) return <TrendingUp className="h-3 w-3" />;
  if (pct < 0) return <TrendingDown className="h-3 w-3" />;
  return <Minus className="h-3 w-3" />;
}

/* ── Index tile ── */

function IndexTile({
  label,
  data,
  region,
}: {
  label: string;
  data?: MorningBriefIndex;
  region: string;
}) {
  const pct = data?.change_pct;
  return (
    <div className="flex-1 bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-5 rounded-[2px]">
      <div className="text-[10px] tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
        {region}
      </div>
      <div className="mt-1 font-serif text-lg text-[var(--pq-ivory)]">
        {label}
      </div>
      <div
        className={cn(
          "mt-3 flex items-center gap-1.5 tabular-nums text-2xl",
          pctColorClass(pct),
        )}
      >
        {pctIcon(pct)}
        {fmtPctSigned(pct)}
      </div>
    </div>
  );
}

/* ── Macro tile (placeholder from backend macro endpoint if present) ── */

function MacroTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-4 rounded-[2px]">
      <div className="text-[10px] tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
        {label}
      </div>
      <div className="mt-2 font-mono text-lg text-[var(--pq-ivory)] tabular-nums">
        {value}
      </div>
    </div>
  );
}

/* ── Archive row ── */

function ArchiveRow({ item }: { item: MorningBriefArchiveItem }) {
  const [open, setOpen] = useState(false);
  const { locale } = useLocale();
  const date = new Date(item.date);
  const dateStr = date.toLocaleDateString(
    locale === "ko" ? "ko-KR" : "en-US",
    { month: "short", day: "numeric", weekday: "short" },
  );

  return (
    <article className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] rounded-[2px] overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="w-full flex items-center justify-between gap-3 px-5 py-4 text-left hover:bg-[rgba(255,255,255,0.01)] transition-colors"
      >
        <div className="flex items-center gap-4 min-w-0">
          <CalendarDays className="h-3.5 w-3.5 text-[var(--pq-bronze)] shrink-0" />
          <time className="font-serif text-base text-[var(--pq-ivory)]">
            {dateStr}
          </time>
          <span className={cn("text-xs tabular-nums", pctColorClass(item.content.market_summary.sp500?.change_pct))}>
            S&amp;P {fmtPctSigned(item.content.market_summary.sp500?.change_pct)}
          </span>
          <span className={cn("text-xs tabular-nums hidden sm:inline", pctColorClass(item.content.market_summary.nasdaq?.change_pct))}>
            NASDAQ {fmtPctSigned(item.content.market_summary.nasdaq?.change_pct)}
          </span>
        </div>
        {open ? (
          <ChevronUp className="h-4 w-4 text-[var(--pq-bronze)]" />
        ) : (
          <ChevronDown className="h-4 w-4 text-[var(--pq-bronze)]" />
        )}
      </button>

      {open && item.content.insight && (
        <div className="border-t border-[rgba(245,240,232,0.08)] px-5 py-4">
          <div className="flex items-start gap-2">
            <Sparkles className="mt-0.5 h-3.5 w-3.5 text-[var(--pq-bronze)] shrink-0" />
            <p className="text-sm text-[rgba(245,240,232,0.75)] leading-relaxed">
              {item.content.insight}
            </p>
          </div>
        </div>
      )}
    </article>
  );
}

/* ── Page ── */

export default function MorningBriefPage() {
  const { data: today, isLoading: todayLoading } = useMorningBrief();
  const { data: archive } = useMorningBriefArchive();
  const now = useNowTick(1000);

  const todayDate = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });

  const brief = today?.brief;
  const observedRel = relativeTime(today?.generated_at, now);
  const archiveItems = useMemo<MorningBriefArchiveItem[]>(
    () => archive?.briefs ?? [],
    [archive],
  );

  return (
    <ErrorBoundary>
      <div className="space-y-10">
        {/* ── Header ── */}
        <header className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Sunrise className="h-3 w-3 text-[var(--pq-bronze)]" />
              <RuledKicker>Morning brief &middot; {todayDate}</RuledKicker>
            </div>
            {today?.generated_at && (
              <div className="mt-1 flex items-center gap-2">
                <span
                  aria-hidden="true"
                  className="inline-block h-1 w-1 rounded-full bg-[var(--pq-bronze)] opacity-40"
                />
                <span className="font-mono text-[10px] tabular-nums text-[var(--pq-bronze)]">
                  Data observed {observedRel}
                </span>
              </div>
            )}
            <h1 className="mt-3 font-serif text-[2.25rem] leading-tight text-[var(--pq-ivory)]" style={{ letterSpacing: "-0.015em" }}>
              Good morning.
            </h1>
            <p className="mt-2 font-serif text-[15px] text-[var(--pq-ivory)]">
              Today at the desk.
            </p>
            <Caption className="mt-1">Overnight marks, macro tape, and the week&rsquo;s events.</Caption>
          </div>

          <a
            href="/samples/morning_brief_plus.pdf"
            target="_blank"
            rel="noopener noreferrer"
            className="pq-ink-btn-bronze inline-flex items-center gap-1.5"
          >
            <Download className="h-3.5 w-3.5" />
            Download PDF
          </a>
        </header>

        <DisclaimerBanner type="signal" />

        {/* ── Overnight 3-up: Asia / Europe / US ── */}
        <section>
          <h2 className="pq-ink-h2 mb-4">Overnight</h2>
          {todayLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <div
                  key={i}
                  className="h-32 rounded-[2px] bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] animate-pulse"
                />
              ))}
            </div>
          ) : brief ? (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <IndexTile
                region="Asia"
                label="KOSPI"
                data={brief.market_summary.kospi}
              />
              <IndexTile
                region="US pre-market"
                label="S&P 500"
                data={brief.market_summary.sp500}
              />
              <IndexTile
                region="US pre-market"
                label="NASDAQ"
                data={brief.market_summary.nasdaq}
              />
            </div>
          ) : (
            <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-8 rounded-[2px] text-center text-sm text-[rgba(245,240,232,0.5)]">
              Today's brief is being assembled. Check back shortly.
            </div>
          )}
        </section>

        {/* Fleuron divider */}
        <div className="flex justify-center" aria-hidden="true">
          <Fleuron size={14} />
        </div>

        {/* ── Macro strip ── */}
        <section>
          <h2 className="pq-ink-h2 mb-4">Cross-asset</h2>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            <MacroTile label="US 10Y" value="—" />
            <MacroTile label="VIX" value="—" />
            <MacroTile label="USD/KRW" value="—" />
            <MacroTile label="Gold" value="—" />
            <MacroTile label="WTI" value="—" />
          </div>
          <p className="mt-3 text-xs text-[rgba(245,240,232,0.4)]">
            Values stream from the macro tape at 9:00 KST.
          </p>
        </section>

        {/* ── Today's insight ── */}
        {brief?.insight && (
          <section>
            <h2 className="pq-ink-h2 mb-1 font-serif">Desk note</h2>
            <Caption className="mb-4">One paragraph, observed.</Caption>
            <div className="bg-[rgba(255,255,255,0.02)] border-l-2 border-[var(--pq-bronze)] px-6 py-5 relative">
              <span
                aria-hidden="true"
                className="absolute top-2 left-3 font-serif"
                style={{ fontSize: "36px", lineHeight: 1, color: "var(--pq-bronze)", opacity: 0.35 }}
              >
                &ldquo;
              </span>
              <p
                className="font-serif pl-5"
                style={{ fontSize: "15px", lineHeight: 1.6, color: "rgba(245,240,232,0.88)" }}
              >
                {brief.insight}
              </p>
              <Sparkles className="absolute bottom-3 right-3 h-3.5 w-3.5 text-[var(--pq-bronze)] opacity-60" />
            </div>
          </section>
        )}

        {/* ── Earnings today ── */}
        {brief?.events && brief.events.length > 0 && (
          <section>
            <h2 className="pq-ink-h2 mb-4">Earnings &amp; events today</h2>
            <ul className="space-y-2">
              {brief.events.map((e, i) => (
                <li
                  key={`${e.ticker}-${i}`}
                  className="flex items-start gap-3 bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-4 rounded-[2px]"
                >
                  <span className="mt-1 h-1 w-1 rounded-full bg-[var(--pq-bronze)] shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline gap-2">
                      <span className="font-serif text-base text-[var(--pq-ivory)]">
                        {e.name || e.ticker}
                      </span>
                      <span className="font-mono text-[10px] text-[rgba(245,240,232,0.4)]">
                        {e.ticker}
                      </span>
                      {e.event_time && (
                        <span className="text-xs text-[rgba(245,240,232,0.5)]">
                          · {e.event_time}
                        </span>
                      )}
                    </div>
                    <div className="mt-1 text-xs text-[rgba(245,240,232,0.6)]">
                      {e.description}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* ── Archive ── */}
        {archiveItems.length > 0 && (
          <section>
            <div className="mb-4">
              <h2 className="pq-ink-h2">Archive</h2>
              <Caption className="mt-1">Prior editions of the morning brief.</Caption>
            </div>
            <div className="space-y-2">
              {archiveItems.slice(0, 14).map((item) => (
                <ArchiveRow key={item.date} item={item} />
              ))}
            </div>
          </section>
        )}

        {/* Editorial foot signature */}
        <FootSignature note="PivoxQuant &middot; Morning brief &middot; Observational only &middot; Not investment advice" />
      </div>
    </ErrorBoundary>
  );
}
