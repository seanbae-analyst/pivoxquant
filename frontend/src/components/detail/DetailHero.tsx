"use client";

/**
 * Zone1 TERMINAL — Hero "cover".
 *
 * The price is the protagonist: company name (Playfair UPRIGHT) + a giant
 * mono price as the #1 visual. sector / market cap / listing demote to a
 * small supporting line. A one-line company summary (profile.summary, fetched
 * but previously unused) sits directly under the identity. 52W rail + signal
 * label + composite score + a 4-pillar mini-summary answer "why this signal"
 * right at the top. DisclaimerBanner(signal) docked at the base — legal.
 *
 * A sticky compact header (StickyTicker) condenses name + price + 1D delta
 * once the hero scrolls past, so the price is always visible on mobile.
 *
 * Signals: POSITIVE / NEGATIVE / NEUTRAL only. KR convention colours via
 * lib/format helpers (carmine rise / indigo fall).
 */

import { useEffect, useRef, useState } from "react";
import { Check, Plus, Minus } from "lucide-react";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/locale";
import {
  fmtPct,
  pctColorClass,
  priceGlyph,
} from "@/lib/format";
import { FieldLabel } from "@/components/ui/editorial";
import { Eyebrow } from "@/components/landing/eyebrow";
import { Skeleton } from "@/components/ui/loading-skeleton";
import { relativeTime } from "@/components/ui/price-with-timestamp";
import { LoadFailure } from "./shared";
import type { SignalDetail } from "./types";
import { fmtPrice, fmtMcap, splitMcap, pillarToken } from "./types";

/* ── giant mono price ── */
function formatHeroPrice(
  price: number | null | undefined,
  krw: boolean,
): string {
  if (price == null) return "—";
  const n = typeof price === "number" ? price : Number(price);
  if (!Number.isFinite(n)) return "—";
  if (krw) return "KRW " + Math.round(n).toLocaleString("ko-KR");
  if (Math.abs(n) < 1) return "USD " + n.toFixed(4);
  return "USD " + n.toFixed(2);
}

/* Hero price split into a demoted currency code + full-size digits, so the
   KRW/USD code does not balloon at the giant Tier-1 size (CEO: "기호 존나 큼"). */
function splitHeroPrice(
  price: number | null | undefined,
  krw: boolean,
): { symbol: string; digits: string } {
  const s = formatHeroPrice(price, krw);
  if (s === "—") return { symbol: "", digits: "—" };
  // ISO currency-code prefix ("KRW "/"USD ") demoted; digits stay full-size.
  const m = s.match(/^([A-Z]{3}\s)(.*)$/);
  return m ? { symbol: m[1].trim(), digits: m[2] } : { symbol: "", digits: s };
}

/** Pillar mini-summary — "why this signal" in one bronze-labelled row. */
function PillarMini({
  label,
  score,
}: {
  label: string;
  score: number | null | undefined;
}) {
  const safe =
    score != null && Number.isFinite(score)
      ? Math.max(0, Math.min(100, score))
      : null;
  const tone: "pos" | "neg" | "neu" =
    safe == null ? "neu" : safe >= 65 ? "pos" : safe <= 35 ? "neg" : "neu";
  const color =
    tone === "pos"
      ? "text-[var(--up)]"
      : tone === "neg"
        ? "text-[var(--down)]"
        : "text-[var(--pq-ivory)]";
  return (
    <div className="flex items-center gap-2 min-w-0">
      <span className="text-pq-h5 uppercase tracking-[0.04em] text-[var(--pq-ivory-soft)] font-sans font-medium shrink-0">
        {label}
      </span>
      <span className="h-px flex-1 bg-[var(--pq-ivory-line)] min-w-2" />
      <span
        className={cn("font-mono tabular-nums text-pq-h5 shrink-0", color)}
      >
        {safe == null ? "—" : safe.toFixed(0)}
      </span>
    </div>
  );
}

export interface DetailHeroProps {
  displayTicker: string;
  /** Raw ticker WITH exchange suffix (".KS"/".KQ") — displayTicker has it
   *  stripped, so KOSPI/KOSDAQ disambiguation must read this. */
  rawTicker: string;
  displayName: string;
  summary?: string | null;
  sectorLine: string;
  industry?: string | null;
  krw: boolean;
  mcap: number | null;
  signal: SignalDetail | undefined;
  loadingSignal: boolean;
  /** P0 resilience: signals source failed / timed out. */
  signalError: boolean;
  /** 403 ticker_not_in_user_scope — the ticker is outside the user's
   *  held/watchlist scope (§101). Distinct from a timeout/server error:
   *  surfaces a "add to watchlist" CTA rather than a retry. */
  signalScopeDenied?: boolean;
  onRetrySignal: () => void;
  signalRetrying: boolean;
  inWatchlist: boolean;
  onWatchlistToggle: () => void;
}

export function DetailHero(props: DetailHeroProps) {
  const {
    displayTicker,
    rawTicker,
    displayName,
    summary,
    sectorLine,
    industry,
    krw,
    mcap,
    signal,
    loadingSignal,
    signalError,
    signalScopeDenied,
    onRetrySignal,
    signalRetrying,
    inWatchlist,
    onWatchlistToggle,
  } = props;

  const t = useT();

  /* sticky compact header — shows once the hero scrolls out of view. */
  const sentinelRef = useRef<HTMLDivElement>(null);
  const [stuck, setStuck] = useState(false);
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const obs = new IntersectionObserver(
      ([entry]) => setStuck(!entry.isIntersecting),
      { rootMargin: "-64px 0px 0px 0px", threshold: 0 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // `now` ticks every 60 s so the relative "관측 N분 전" label stays fresh.
  // The lazy useState initializer keeps Date.now() OUT of the render body
  // (react-hooks/purity) and the only setState lives inside the interval
  // callback — never synchronously in the effect (react-hooks set-state-in-
  // effect). Mirrors the proven pattern in components/ui/price-with-timestamp.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(id);
  }, []);

  const signalToken =
    signal?.signal === "POSITIVE" || signal?.signal === "NEGATIVE"
      ? signal.signal
      : "NEUTRAL";
  const signalTone: "pos" | "neg" | "neu" =
    signalToken === "POSITIVE" ? "pos" : signalToken === "NEGATIVE" ? "neg" : "neu";
  const signalChipClass =
    signalToken === "POSITIVE"
      ? "pq-ink-pill pq-ink-pill--pos"
      : signalToken === "NEGATIVE"
        ? "pq-ink-pill pq-ink-pill--neg"
        : "pq-ink-pill pq-ink-pill--neu";

  const week52Low = signal?.snapshot?.week52_low;
  const week52High = signal?.snapshot?.week52_high;
  const hasRange =
    week52Low != null && week52High != null && week52High > week52Low;
  const rangePos =
    hasRange && signal?.price != null
      ? Math.min(
          100,
          Math.max(
            0,
            ((signal.price - (week52Low as number)) /
              ((week52High as number) - (week52Low as number))) *
              100,
          ),
        )
      : null;

  const hasPillars =
    signal?.tech_score != null ||
    signal?.fund_score != null ||
    signal?.news_score != null ||
    signal?.quant_score != null;

  const heroPrice = formatHeroPrice(signal?.price, krw);
  const heroSplit = splitHeroPrice(signal?.price, krw);
  const obsRel = signal?.observed_at
    ? relativeTime(signal.observed_at, now)
    : null;

  /* ── Quote-density stats — all DERIVED from existing data (no new fetch) ── */
  // 1D absolute change: prev = price / (1 + pct/100); guard pct === -100 (div-by-zero).
  const changeAbs =
    signal?.price != null &&
    signal?.change_pct != null &&
    Number.isFinite(signal.price) &&
    Number.isFinite(signal.change_pct) &&
    signal.change_pct !== -100
      ? signal.price - signal.price / (1 + signal.change_pct / 100)
      : null;
  // % distance from the 52-week extremes — terminal-grade price context.
  const pctFromHigh =
    hasRange && signal?.price != null && week52High
      ? ((signal.price - (week52High as number)) / (week52High as number)) * 100
      : null;
  const pctFromLow =
    hasRange && signal?.price != null && week52Low
      ? ((signal.price - (week52Low as number)) / (week52Low as number)) * 100
      : null;
  // Avg volume (3mo), compact — full value still lives in the Fundamentals panel.
  const avgVolStr = (() => {
    const v = signal?.snapshot?.avg_volume;
    if (v == null || !Number.isFinite(v)) return null;
    return new Intl.NumberFormat(krw ? "ko-KR" : "en-US", {
      notation: "compact",
      maximumFractionDigits: 1,
    }).format(v);
  })();

  return (
    <>
      {/* ── sticky compact header (mobile keeps price visible) ── */}
      <div
        className={cn(
          "sticky top-0 z-30 -mx-4 px-4 md:-mx-6 md:px-6 transition-all duration-200",
          stuck
            ? "opacity-100 translate-y-0 pointer-events-auto"
            : "opacity-0 -translate-y-2 pointer-events-none",
        )}
        aria-hidden={!stuck}
      >
        <div className="flex items-center justify-between gap-3 py-2.5 border-b border-[var(--pq-ivory-line)] bg-[rgba(5,5,5,0.92)] backdrop-blur-sm">
          <div className="min-w-0">
            <p className="font-display text-pq-body text-[var(--pq-ivory)] truncate leading-tight">
              {displayName}
            </p>
            <p className="font-mono text-pq-mono-xs text-[var(--pq-ivory-faint)] leading-tight">
              {displayTicker}
            </p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <span className="font-mono tabular-nums text-pq-body text-[var(--pq-ivory)]">
              {heroPrice}
            </span>
            <span
              className={cn(
                "font-mono tabular-nums text-pq-body-sm inline-flex items-center gap-1",
                pctColorClass(signal?.change_pct),
              )}
            >
              <span aria-hidden>{priceGlyph(signal?.change_pct)}</span>
              {fmtPct(signal?.change_pct)}
            </span>
          </div>
        </div>
      </div>

      {/* Zone1 TERMINAL — elevated surface: slightly stronger base + bronze top accent.
          The top border is the "cover" moment that anchors the page visually. */}
      <section className="bg-[rgba(255,255,255,0.03)] border border-[var(--pq-ivory-line)] rounded-sm" style={{ borderTopColor: "var(--pq-bronze)", borderTopWidth: "1px" }}>
        {/* sentinel — top of hero, observed for sticky toggle */}
        <div ref={sentinelRef} aria-hidden className="h-px" />

        {/* Kicker strip + watchlist toggle */}
        <div className="flex items-center justify-between gap-3 px-6 md:px-8 pt-6 md:pt-7 flex-wrap">
          <Eyebrow>
            Pivoxquant · Equity Dossier ·{" "}
            {new Date().toLocaleDateString("en-US", {
              year: "numeric",
              month: "short",
              day: "numeric",
            })}
          </Eyebrow>
          <button
            type="button"
            onClick={onWatchlistToggle}
            className={cn(
              "inline-flex items-center gap-1.5",
              inWatchlist ? "pq-ink-btn-ghost" : "pq-ink-btn-bronze",
            )}
          >
            {inWatchlist ? (
              <>
                <Check className="h-3.5 w-3.5" />
                In watchlist
              </>
            ) : (
              <>
                <Plus className="h-3.5 w-3.5" />
                Add to watchlist
              </>
            )}
          </button>
        </div>

        {/* ── Hero body: price-first cover ── */}
        <div className="px-6 md:px-8 pt-6 pb-6 md:pb-7">
          {/* Identity — name is the headline, ticker the sub-label */}
          <h1 className="pq-detail-ticker-display">{displayName}</h1>
          <p className="mt-2 font-mono tabular-nums text-pq-h5 font-medium text-[var(--pq-ivory-soft)] leading-snug">
            {displayTicker}
          </p>

          {/* One-line company summary (profile.summary) — for first-time
              investors. Collapses entirely when absent (no em-dash). */}
          {summary && summary.trim() ? (
            <p className="mt-3 font-serif text-pq-body leading-[1.55] text-[var(--pq-ivory-soft)] max-w-2xl line-clamp-2">
              {summary.trim()}
            </p>
          ) : null}

          {/* Supporting line — sector › industry · listing · market cap */}
          <div className="mt-4 flex items-center gap-x-3 gap-y-1.5 flex-wrap text-pq-h5 font-sans font-medium text-[var(--pq-ivory-soft)]">
            {(() => {
              const sec = sectorLine && sectorLine !== "—" ? sectorLine : "";
              // Treat "UNKNOWN" (any case) as empty — same guard as sectorLine above.
              const indRaw = (industry || "").trim();
              const ind = indRaw.toUpperCase() === "UNKNOWN" ? "" : indRaw;
              const taxon =
                sec && ind && ind.toUpperCase() !== sec.toUpperCase()
                  ? `${sec} › ${ind}`
                  : sec || ind;
              return taxon ? (
                <span className="uppercase tracking-[0.12em]">{taxon}</span>
              ) : null;
            })()}
            {/* Only render the separator when there IS a taxon before it */}
            {(() => {
              const sec = sectorLine && sectorLine !== "—" ? sectorLine : "";
              const indRaw = (industry || "").trim();
              const ind = indRaw.toUpperCase() === "UNKNOWN" ? "" : indRaw;
              const taxon =
                sec && ind && ind.toUpperCase() !== sec.toUpperCase()
                  ? `${sec} › ${ind}`
                  : sec || ind;
              return taxon ? (
                <span className="text-[var(--pq-ivory-line)]" aria-hidden>·</span>
              ) : null;
            })()}
            <span className="uppercase tracking-[0.12em]">
              {krw
                ? rawTicker.toUpperCase().endsWith(".KQ")
                  ? "KRW · KOSDAQ"
                  : "KRW · KOSPI"
                : "USD · US Listed"}
            </span>
            {(() => {
              const { num, suffix } = splitMcap(fmtMcap(mcap, krw));
              if (num === "—") return null;
              return (
                <>
                  <span className="text-[var(--pq-ivory-line)]" aria-hidden>
                    ·
                  </span>
                  <span className="uppercase tracking-[0.12em] inline-flex items-baseline gap-1">
                    시총{" "}
                    <span className="font-mono tabular-nums text-pq-h5 normal-case text-[var(--pq-ivory-soft)]">
                      {num}
                      {suffix}
                    </span>
                  </span>
                </>
              );
            })()}
          </div>

          {/* ── Price + Signal terminal row ── */}
          {signalScopeDenied ? (
            // 403 ticker_not_in_user_scope — honest watchlist CTA, NOT a
            // timeout. §101: analysis is limited to held / watchlisted names.
            <div className="mt-6">
              <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-6 rounded-sm text-center">
                <p className="font-serif text-pq-body text-[var(--pq-ivory-mid)]">
                  이 종목을 관심 목록에 추가하면 분석을 볼 수 있습니다.
                </p>
                <p className="mt-1.5 text-pq-mono-xs font-mono text-[var(--pq-ivory-faint)]">
                  Add this ticker to your watchlist to see analysis.
                </p>
                <button
                  type="button"
                  onClick={onWatchlistToggle}
                  className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 text-pq-mono-xs uppercase tracking-[0.18em] border border-[var(--pq-bronze)] text-[var(--pq-bronze)] hover:bg-[rgba(184,149,106,0.08)] hover:text-[var(--pq-bronze-light)] transition-colors rounded-sm"
                >
                  <Plus size={13} aria-hidden />
                  관심 목록에 추가 · Add to watchlist
                </button>
              </div>
            </div>
          ) : signalError ? (
            <div className="mt-6">
              <LoadFailure
                label="시그널·가격 데이터를 불러오지 못했습니다."
                note="signals 응답 지연 또는 오류 (timeout)"
                onRetry={onRetrySignal}
                retrying={signalRetrying}
              />
            </div>
          ) : (
            <div className="mt-6 grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 items-start">
              {/* Giant price — the protagonist */}
              <div className="lg:col-span-6">
                <FieldLabel size="var(--pq-text-h5)">{t("detail.currentPrice")}</FieldLabel>
                <div className="mt-1.5">
                  {loadingSignal && !signal ? (
                    <Skeleton className="h-14 w-56" />
                  ) : (
                    <div
                      className="font-mono tabular-nums text-[var(--pq-ivory)] leading-none"
                      style={{
                        /* Tier 1 — hero numeric. 40–56px (CEO: "좀 더 키워").
                           Currency code below is demoted to 0.5em so the
                           KRW/USD prefix does not balloon at this size. */
                        fontSize: "clamp(2.5rem, 6.5vw, 3.5rem)",
                        letterSpacing: "-0.025em",
                        fontFeatureSettings: '"tnum" 1, "lnum" 1',
                      }}
                    >
                      {heroSplit.symbol && (
                        <span className="text-[0.5em] text-[var(--pq-ivory-mid)] align-baseline mr-2.5">
                          {heroSplit.symbol}
                        </span>
                      )}
                      {heroSplit.digits}
                    </div>
                  )}
                </div>
                {/* 1D delta + observation freshness */}
                <div className="mt-3 flex items-center gap-4 flex-wrap">
                  {loadingSignal && !signal ? (
                    <Skeleton className="h-4 w-24" />
                  ) : (
                    <span
                      className={cn(
                        "inline-flex items-center gap-1.5 tabular-nums font-mono text-pq-h5",
                        pctColorClass(signal?.change_pct),
                      )}
                    >
                      {signal?.change_pct == null ? (
                        <Minus className="h-4 w-4" />
                      ) : (
                        <span aria-hidden className="text-[0.85em]">
                          {priceGlyph(signal.change_pct)}
                        </span>
                      )}
                      {changeAbs != null
                        ? fmtPrice(Math.abs(changeAbs), krw)
                        : fmtPct(signal?.change_pct)}
                      {changeAbs != null && (
                        <span className="text-[0.82em] opacity-80">
                          ({fmtPct(signal?.change_pct)})
                        </span>
                      )}
                      <span className="ml-1 text-pq-eyebrow-sm tracking-[0.12em] uppercase text-[var(--pq-ivory-faint)] font-sans">
                        · 1D
                      </span>
                    </span>
                  )}
                  {obsRel ? (
                    <span className="inline-flex items-center gap-1.5 font-mono text-pq-mono-xs uppercase tracking-[0.12em] text-[var(--pq-ivory-faint)]">
                      <span
                        className="h-1.5 w-1.5 rounded-full bg-[var(--pq-bronze)] opacity-70"
                        aria-hidden
                      />
                      {obsRel === "live" ? "관측 · live" : `관측 ${obsRel}`}
                    </span>
                  ) : null}
                </div>

                {/* Quote stats — derived (52W distance + avg volume), fills the
                    formerly empty right half of the price column. */}
                {(pctFromLow != null || pctFromHigh != null || avgVolStr) && (
                  <div className="mt-4 flex items-center gap-x-6 gap-y-2 flex-wrap font-mono text-pq-h5 font-medium tracking-[0.01em] text-[var(--pq-ivory-soft)]">
                    {pctFromLow != null && (
                      <span>
                        52주 저점대비{" "}
                        <span className={cn("font-medium tabular-nums", pctColorClass(pctFromLow))}>
                          {fmtPct(pctFromLow)}
                        </span>
                      </span>
                    )}
                    {pctFromHigh != null && (
                      <span>
                        고점대비{" "}
                        <span className={cn("font-medium tabular-nums", pctColorClass(pctFromHigh))}>
                          {fmtPct(pctFromHigh)}
                        </span>
                      </span>
                    )}
                    {avgVolStr && (
                      <span>
                        평균 거래량{" "}
                        <span className="font-medium tabular-nums text-[var(--pq-ivory-soft)]">
                          {avgVolStr}
                        </span>
                      </span>
                    )}
                  </div>
                )}

                {/* 52W rail */}
                {hasRange && (
                  <div className="mt-6 max-w-md">
                    <div className="flex items-baseline justify-between font-mono tabular-nums font-medium text-[var(--pq-ivory-soft)]">
                      <span className="text-pq-h5">
                        {fmtPrice(week52Low, krw)}
                      </span>
                      <span className="text-pq-mono-xs tracking-[0.12em] uppercase text-[var(--pq-bronze)]">
                        52W Range
                      </span>
                      <span className="text-pq-h5">
                        {fmtPrice(week52High, krw)}
                      </span>
                    </div>
                    <div className="mt-2 h-1 bg-[var(--pq-ivory-line)] relative rounded-[1px]">
                      {rangePos != null && (
                        <div
                          className="absolute top-1/2 h-2.5 w-2.5 rounded-full bg-[var(--pq-bronze)] shadow-[0_0_8px_rgba(var(--pq-bronze-wash-rgb),0.5)]"
                          style={{
                            left: `${rangePos}%`,
                            transform: "translate(-50%, -50%)",
                          }}
                        />
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Signal + composite + 4-pillar mini "why" */}
              <div className="lg:col-span-6 lg:border-l lg:border-[var(--pq-ivory-line)] lg:pl-8">
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div>
                    <FieldLabel size="var(--pq-text-h5)">{t("detail.signal")}</FieldLabel>
                    <div className="mt-1.5">
                      <span className={signalChipClass}>
                        {pillarToken(signalToken)}
                      </span>
                    </div>
                  </div>
                  <div className="text-right">
                    <FieldLabel tone="muted" size="var(--pq-text-h5)">{t("detail.composite")}</FieldLabel>
                    <div
                      className={cn(
                        /* Unified to text-pq-h5 (18px) with the rest of the hero
                           secondary content (CEO 2026-05-26: "다 같은 사이즈로"). */
                        "font-mono tabular-nums leading-none mt-1 text-pq-h5",
                        signalTone === "pos"
                          ? "text-[var(--up)]"
                          : signalTone === "neg"
                            ? "text-[var(--down)]"
                            : "text-[var(--pq-ivory)]",
                      )}
                    >
                      {signal?.score != null && Number.isFinite(signal.score)
                        ? signal.score
                        : "—"}
                      <span className="text-pq-body-sm text-[var(--pq-ivory-faint)] ml-1 font-sans tracking-[0.06em]">
                        / 100
                      </span>
                    </div>
                  </div>
                </div>

                {/* 4-pillar mini summary — answers "왜 이 시그널인가" up top.
                    Each row has shrink-0 label + shrink-0 score, so on narrow
                    viewports (≤360 Galaxy S) min-content exceeds half the
                    container and pushed the whole page ~12px wide. Stack
                    to a single column under 380px; resume 2-col from
                    iPhone 14/15 (390) and up. */}
                {hasPillars ? (
                  <div className="mt-5 grid grid-cols-1 min-[380px]:grid-cols-2 gap-x-6 gap-y-2.5">
                    <PillarMini label={t("detail.pillar.technical")} score={signal?.tech_score} />
                    <PillarMini label={t("detail.pillar.fundamental")} score={signal?.fund_score} />
                    <PillarMini label={t("detail.pillar.sentiment")} score={signal?.news_score} />
                    <PillarMini label={t("detail.pillar.quant")} score={signal?.quant_score} />
                  </div>
                ) : (
                  <p className="mt-5 font-serif text-pq-body-sm text-[var(--pq-ivory-dim)]">
                    {t("detail.compositeTooltip")}
                  </p>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Legal disclaimer mounted once at the bottom by (dashboard)/layout.tsx
            — hero-base banner removed (CEO 2026-05-24: disclaimer only at the
            bottom, every page). */}
      </section>
    </>
  );
}
