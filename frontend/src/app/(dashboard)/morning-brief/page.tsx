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
import { useSWRConfig } from "swr";
import Link from "next/link";
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
  Loader2,
  Lock,
} from "lucide-react";
import { useMorningBrief, useMorningBriefArchive, useMacro } from "@/lib/hooks";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { useLocale } from "@/lib/locale";
import { cn } from "@/lib/utils";
import { pctColorClass, sanitizeKrIndex } from "@/lib/format";
import { relativeTime, useNowTick } from "@/components/market/index-card";
import { ErrorBoundary } from "@/components/ui/error-boundary";
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

/* ── Tier helper ── */

const TIER_RANK: Record<string, number> = { free: 0, pro: 1, premium: 2 };
function isProOrAbove(tier?: string): boolean {
  const norm = (tier ?? "free").toLowerCase();
  return (TIER_RANK[norm] ?? 0) >= 1;
}

/* ── EmptyBriefState — empty state with generate-now CTA (Pro+) or upgrade CTA (Free) ── */

function EmptyBriefState({ onGenerated }: { onGenerated: () => void }) {
  const { user } = useAuth();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const proPlus = isProOrAbove(user?.subscription_tier);

  async function handleGenerate() {
    setBusy(true);
    setErr(null);
    try {
      // apiFetch throws on non-2xx and returns parsed JSON of type T.
      await apiFetch<{ ok?: boolean; brief?: unknown }>(
        API.market.morningBriefGenerate,
        { method: "POST", timeoutMs: 60_000 },
      );
      onGenerated();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-10 rounded-[2px] text-center">
      <Sunrise className="h-6 w-6 text-[var(--pq-bronze)] mx-auto mb-3 opacity-60" />
      <h3 className="font-serif text-[18px] text-[var(--pq-ivory)] mb-2">
        오늘 브리핑이 아직 준비되지 않았어요
      </h3>
      <p className="text-sm text-[rgba(245,240,232,0.55)] mb-6 font-serif">
        매일 06:00 KST 에 자동 생성됩니다. 그 전에 미리 보고 싶다면 아래에서 직접 요청하세요.
      </p>
      {proPlus ? (
        <button
          type="button"
          disabled={busy}
          onClick={handleGenerate}
          className="pq-ink-btn-bronze inline-flex items-center gap-1.5 disabled:opacity-50"
        >
          {busy ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              생성 중… (10–30초)
            </>
          ) : (
            <>
              <Sparkles className="h-3.5 w-3.5" />
              지금 생성하기
            </>
          )}
        </button>
      ) : (
        <div className="space-y-2">
          <Link
            href="/pricing"
            className="pq-ink-btn-bronze inline-flex items-center gap-1.5"
          >
            <Lock className="h-3.5 w-3.5" />
            Pro로 업그레이드 (₩9,900/월)
          </Link>
          <p className="text-[11px] text-[rgba(245,240,232,0.4)]">
            Free 티어는 자동 생성만 — 즉시 생성은 Pro 이상에서.
          </p>
        </div>
      )}
      {err && (
        <p className="mt-3 text-xs text-red-400">에러: {err}</p>
      )}
    </div>
  );
}

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
  // KR index sanity guard — drop level if outside [KOSPI 1500-3500 / KOSDAQ
  // 500-1500] (2026-04-28 KIS scaling glitch defense). pct intentionally
  // kept since direction is independent of an out-of-range level.
  const safeLevel =
    label === "KOSPI" || label === "KOSDAQ"
      ? sanitizeKrIndex(label, data?.price)
      : data?.price;
  const pct = safeLevel == null ? undefined : data?.change_pct;
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
  const { data: macro, isLoading: macroLoading } = useMacro();
  const { mutate } = useSWRConfig();
  const now = useNowTick(1000);
  const refreshBrief = () => {
    mutate(API.market.morningBriefToday);
    mutate(API.market.morningBriefArchive);
  };

  // Cross-asset tape — formatted strings ready for MacroTile
  const macroTiles = useMemo(() => {
    const fmt = (v: number | undefined, opts?: { decimals?: number; prefix?: string }) =>
      v == null || !Number.isFinite(v)
        ? "—"
        : `${opts?.prefix ?? ""}${v.toLocaleString(undefined, {
            minimumFractionDigits: opts?.decimals ?? 2,
            maximumFractionDigits: opts?.decimals ?? 2,
          })}`;
    return {
      us10y: fmt(macro?.treasury_10y, { decimals: 2 }) + (macro?.treasury_10y != null ? "%" : ""),
      vix: fmt(macro?.vix, { decimals: 2 }),
      usdkrw: fmt(macro?.usdkrw?.price, { decimals: 2 }),
      gold: fmt(macro?.gold?.price, { decimals: 2, prefix: "$" }),
      wti: fmt(macro?.oil_wti?.price, { decimals: 2, prefix: "$" }),
    };
  }, [macro]);

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
            {/* pq-ink-h1: Playfair Display italic — site-wide H1 token
                (globals.css:1141). Source Serif 4 했던 거 다른 페이지 H1과 폰트 달라
                CEO 지적 2026-04-29 "morning brief 그리고 이 페이지 폰트 동일한거냐". */}
            <h1 className="pq-ink-h1 mt-3">
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

        {/* Legal disclaimer mounted by (dashboard)/layout.tsx — do not re-mount. */}

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
            <EmptyBriefState onGenerated={refreshBrief} />
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
            <MacroTile label="US 10Y" value={macroLoading ? "…" : macroTiles.us10y} />
            <MacroTile label="VIX" value={macroLoading ? "…" : macroTiles.vix} />
            <MacroTile label="USD/KRW" value={macroLoading ? "…" : macroTiles.usdkrw} />
            <MacroTile label="Gold" value={macroLoading ? "…" : macroTiles.gold} />
            <MacroTile label="WTI" value={macroLoading ? "…" : macroTiles.wti} />
          </div>
          <p className="mt-3 text-xs text-[rgba(245,240,232,0.4)]">
            Live · refreshes every 60s. FRED + FMP + Alpaca composite tape.
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
