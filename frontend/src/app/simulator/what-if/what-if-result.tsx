"use client";

/**
 * What-If Simulator — Result Card
 *
 * Large share-friendly card (~1:1 ratio on mobile, wider on desktop)
 * containing: headline, value/return hero numbers, chart, benchmark,
 * milestones, share bar, watermark.
 *
 * The card is given id="what-if-share-card" so html2canvas (or any external
 * screenshot tool) can target it. We intentionally render the DOM at full
 * fidelity — no canvas-ink shortcuts — so the browser-native "Save Image"
 * uses native paint.
 */

import { useCallback, useRef } from "react";
import { motion } from "motion/react";
import {
  Sparkles,
  MessageCircle,
  Share2,
  Download,
  Link as LinkIcon,
  Trophy,
} from "lucide-react";
import { toast } from "sonner";
import { useT, useLocale } from "@/lib/locale";
import type { WhatIfSuccessResponse } from "@/lib/types";
import { WhatIfChart } from "./what-if-chart";
import { cn } from "@/lib/utils";

interface WhatIfResultProps {
  data: WhatIfSuccessResponse;
  shareUrl: string;
}

/* ── Number formatters ── */

function fmtMoney(v: number, currency: "USD" | "KRW"): string {
  if (currency === "KRW") {
    const abs = Math.abs(v);
    if (abs >= 100_000_000)
      return `₩${(v / 100_000_000).toLocaleString("ko-KR", {
        maximumFractionDigits: 2,
      })}억`;
    if (abs >= 10_000)
      return `₩${(v / 10_000).toLocaleString("ko-KR", {
        maximumFractionDigits: 0,
      })}만`;
    return `₩${Math.round(v).toLocaleString("ko-KR")}`;
  }
  return `$${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

function fmtPctStrong(v: number): string {
  const s = v >= 0 ? "+" : "";
  return `${s}${v.toFixed(1)}%`;
}

/* ── Dynamic headline based on return magnitude ── */

function pickHeadlineKey(returnPct: number): string {
  if (returnPct > 1000) return "whatIf.headlines.legendary";
  if (returnPct > 500) return "whatIf.headlines.crazy";
  if (returnPct > 100) return "whatIf.headlines.strong";
  if (returnPct > 20) return "whatIf.headlines.solid";
  if (returnPct > -10) return "whatIf.headlines.flat";
  return "whatIf.headlines.negative";
}

/* ── Component ── */

export function WhatIfResult({ data, shareUrl }: WhatIfResultProps) {
  const t = useT();
  const { locale } = useLocale();
  const cardRef = useRef<HTMLDivElement | null>(null);

  const {
    ticker,
    start_date,
    recurring,
    amount_initial,
    total_invested,
    end_value,
    return_pct,
    annualized_return_pct,
    duration_days,
    currency: dataCurrency,
    chart_data,
    milestones,
    benchmark,
  } = data;
  const currency: "USD" | "KRW" = dataCurrency || "USD";
  const isPositive = return_pct >= 0;
  const headlineKey = pickHeadlineKey(return_pct);
  const annualizedValue = annualized_return_pct ?? 0;

  /* ── Share handlers ── */

  const onCopyLink = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      toast.success(t("whatIf.result.copied"));
    } catch {
      // Safari older — fall back to a prompt-y toast
      toast.error("Copy failed");
    }
  }, [shareUrl, t]);

  const onKakaoShare = useCallback(() => {
    // Native Web Share API first — covers mobile KakaoTalk via system share sheet.
    if (typeof navigator !== "undefined" && "share" in navigator) {
      navigator
        .share({
          title: "PivoxQuant What-If",
          text: t("whatIf.result.headline", {
            date: start_date,
            ticker,
            amount: fmtMoney(amount_initial, currency),
          }),
          url: shareUrl,
        })
        .catch(() => {
          // user dismissed — no-op
        });
      return;
    }
    // Desktop fallback: copy link + toast instructing user to paste into KakaoTalk.
    void onCopyLink();
  }, [amount_initial, currency, onCopyLink, shareUrl, start_date, t, ticker]);

  const onTwitterShare = useCallback(() => {
    const text = `${t(headlineKey)} · ${ticker} ${fmtPctStrong(return_pct)}`;
    const u = new URL("https://twitter.com/intent/tweet");
    u.searchParams.set("text", text);
    u.searchParams.set("url", shareUrl);
    window.open(u.toString(), "_blank", "noopener,noreferrer");
  }, [headlineKey, return_pct, shareUrl, t, ticker]);

  const onSaveImage = useCallback(async () => {
    // No heavy DOM-to-canvas dep: we rely on the browser-native
    // "Save image" or "Screenshot" affordances. On mobile this is the
    // expected flow (long-press → save / system screenshot); on desktop
    // we kick off window.print() scoped to the card via CSS @media print.
    const node = cardRef.current;
    if (!node) return;
    try {
      if (typeof window !== "undefined" && typeof window.print === "function") {
        window.print();
      } else {
        toast.info("Long-press the card to save as image");
      }
    } catch {
      toast.error(t("whatIf.errors.generic"));
    }
  }, [t]);

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      className="mt-6"
    >
      {/* Share card — screenshot target */}
      <div
        ref={cardRef}
        id="what-if-share-card"
        className="overflow-hidden rounded-2xl border border-slate-200 bg-white"
      >
        {/* Hero band */}
        <div className="px-5 py-5 sm:px-8 sm:py-6 bg-slate-50">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-slate-600">
            <Sparkles className="h-3.5 w-3.5" />
            {t(headlineKey)}
          </div>
          <h2 className="mt-2 text-base font-bold leading-snug text-slate-900 sm:text-lg">
            {t("whatIf.result.headline", {
              date: start_date,
              ticker,
              amount: fmtMoney(amount_initial, currency),
            })}
          </h2>
        </div>

        {/* Hero numbers */}
        <div className="grid grid-cols-2 divide-x divide-slate-100 border-b border-slate-100">
          <div className="px-5 py-5 sm:px-8 sm:py-6">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              {t("whatIf.result.currentValue")}
            </div>
            <div className="mt-1 font-mono text-2xl font-bold tabular-nums text-slate-900 sm:text-3xl">
              {fmtMoney(end_value, currency)}
            </div>
          </div>
          <div className="px-5 py-5 sm:px-8 sm:py-6">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              {t("whatIf.result.returnPct")}
            </div>
            <div
              className={cn(
                "mt-1 font-mono text-2xl font-bold tabular-nums sm:text-3xl",
                isPositive ? "up-color" : "down-color",
              )}
            >
              {fmtPctStrong(return_pct)}
            </div>
          </div>
        </div>

        {/* Sub-stats */}
        <div className="grid grid-cols-3 divide-x divide-slate-100 border-b border-slate-100 text-center">
          <div className="px-3 py-3 sm:px-5 sm:py-4">
            <div className="text-[10px] font-semibold uppercase text-slate-400">
              {t("whatIf.result.invested")}
            </div>
            <div className="mt-0.5 font-mono text-xs font-semibold tabular-nums text-slate-700 sm:text-sm">
              {fmtMoney(total_invested, currency)}
            </div>
          </div>
          <div className="px-3 py-3 sm:px-5 sm:py-4">
            <div className="text-[10px] font-semibold uppercase text-slate-400">
              {t("whatIf.result.annualized")}
            </div>
            <div
              className={cn(
                "mt-0.5 font-mono text-xs font-semibold tabular-nums sm:text-sm",
                annualizedValue >= 0
                  ? "up-color"
                  : "down-color",
              )}
            >
              {annualized_return_pct === null
                ? "—"
                : fmtPctStrong(annualizedValue)}
            </div>
          </div>
          <div className="px-3 py-3 sm:px-5 sm:py-4">
            <div className="text-[10px] font-semibold uppercase text-slate-400">
              {t("whatIf.result.duration")}
            </div>
            <div className="mt-0.5 font-mono text-xs font-semibold tabular-nums text-slate-700 sm:text-sm">
              {Math.round((duration_days / 365.25) * 10) / 10}{" "}
              {t("whatIf.result.years")}
            </div>
          </div>
        </div>

        {/* Chart */}
        <div className="px-3 pb-4 pt-5 sm:px-5">
          <div className="mb-2 px-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            {t("whatIf.result.chartTitle")}
          </div>
          <WhatIfChart
            data={chart_data}
            currency={currency}
            showInvestedLine={recurring !== "none"}
          />
        </div>

        {/* Benchmark */}
        {benchmark ? (
          <div className="mx-4 mb-4 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 sm:mx-6">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-600">
              {t("whatIf.result.vsBenchmark")}
            </div>
            <div className="mt-1 flex items-baseline justify-between gap-3 text-sm">
              <div>
                <span className="font-mono font-bold tabular-nums text-slate-900">
                  {fmtMoney(benchmark.end_value, currency)}
                </span>
                <span className="ml-2 font-mono text-xs tabular-nums text-slate-500">
                  ({fmtPctStrong(benchmark.return_pct)})
                </span>
              </div>
              <div
                className={cn(
                  "font-mono text-xs font-semibold tabular-nums",
                  end_value >= benchmark.end_value
                    ? "up-color"
                    : "down-color",
                )}
              >
                {t(
                  end_value >= benchmark.end_value
                    ? "whatIf.result.moreThanBench"
                    : "whatIf.result.lessThanBench",
                  {
                    amount: fmtMoney(
                      Math.abs(end_value - benchmark.end_value),
                      currency,
                    ),
                  },
                )}
              </div>
            </div>
          </div>
        ) : null}

        {/* Milestones */}
        {milestones?.length ? (
          <div className="border-t border-slate-100 px-5 py-4 sm:px-8">
            <div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              <Trophy className="h-3.5 w-3.5" />
              {t("whatIf.result.milestones")}
            </div>
            <ul className="space-y-1.5">
              {milestones.slice(0, 5).map((m, i) => (
                <li
                  key={`${m.date}-${i}`}
                  className="flex items-baseline justify-between gap-3 text-xs sm:text-sm"
                >
                  <span className="font-mono tabular-nums text-slate-500">
                    {m.date}
                  </span>
                  <span className="flex-1 text-right font-medium text-slate-700">
                    {(locale === "ko" && m.label_kr) || m.label}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {/* Watermark */}
        <div className="flex items-center justify-between border-t border-slate-100 bg-slate-50 px-5 py-3 sm:px-8">
          <div className="flex items-center gap-1.5">
            <div className="h-5 w-5 rounded-md bg-slate-900" />
            <span className="text-[11px] font-bold text-slate-700">
              PivoxQuant
            </span>
          </div>
          <span className="text-[10px] text-slate-500">
            {t("whatIf.result.watermark")}
          </span>
        </div>
      </div>

      {/* Share bar — outside the screenshot card */}
      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <button
          type="button"
          onClick={onKakaoShare}
          className="flex h-11 items-center justify-center gap-1.5 rounded-xl bg-[#FEE500] text-xs font-bold text-[#3C1E1E] transition hover:brightness-95 active:scale-[0.98]"
        >
          <MessageCircle className="h-4 w-4" />
          {t("whatIf.result.kakao")}
        </button>
        <button
          type="button"
          onClick={onTwitterShare}
          className="flex h-11 items-center justify-center gap-1.5 rounded-xl bg-slate-900 text-xs font-bold text-white transition hover:bg-slate-800 active:scale-[0.98]"
        >
          <Share2 className="h-4 w-4" />
          {t("whatIf.result.twitter")}
        </button>
        <button
          type="button"
          onClick={onSaveImage}
          className="flex h-11 items-center justify-center gap-1.5 rounded-xl border border-slate-300 bg-white text-xs font-bold text-slate-800 transition hover:border-slate-400 hover:bg-slate-50 active:scale-[0.98]"
        >
          <Download className="h-4 w-4" />
          {t("whatIf.result.saveImage")}
        </button>
        <button
          type="button"
          onClick={onCopyLink}
          className="flex h-11 items-center justify-center gap-1.5 rounded-xl border border-slate-300 bg-white text-xs font-bold text-slate-800 transition hover:border-slate-400 hover:bg-slate-50 active:scale-[0.98]"
        >
          <LinkIcon className="h-4 w-4" />
          {t("whatIf.result.copyLink")}
        </button>
      </div>
    </motion.section>
  );
}
