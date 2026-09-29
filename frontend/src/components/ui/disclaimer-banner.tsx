"use client";

import { useState } from "react";
import { ShieldAlert, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

/* ── Disclaimer content per variant ── */

const DISCLAIMER_CONTENT = {
  // Record surfaces — /pre-trade, /portfolio, /settings, /support (the
  // layout's fallback). These screens organise what the user typed or imported
  // themselves; nothing is generated for them. 2026-09-29: replaced "signal"
  // (algorithmic signals — that surface is gone) and "coaching" (an AI
  // assistant — AI was deleted on 2026-09-01), which described features that
  // no longer exist. Legal meaning kept: not a solicitation, not advice, the
  // user is responsible. "ai-analysis" and "backtest" had no route mapped to
  // them and were removed at the same time.
  record: {
    ko: "본 화면은 이용자가 직접 입력하거나 가져온 기록을 정리해 보여줍니다. 특정 종목의 매수 또는 매도를 권유하지 않으며 개인별 투자자문이 아닙니다. 표시된 정보의 정확성을 보장하지 않으며, 투자 판단의 책임은 이용자 본인에게 있습니다.",
    en: "This screen organizes records you entered or imported yourself. It does not recommend buying or selling any specific security and is not personalized investment advice. The accuracy of the displayed information is not guaranteed. All investment decisions are your sole responsibility.",
  },
  // Behavior-Mirror section — factual statistics computed from the user's own
  // trade records (disposition mirror) AND current holdings (concentration
  // mirror). One shared disclaimer covers every mirror on the section, so the
  // wording must stay generic across trade-records + holdings. Explicitly NOT a
  // medical/psychological/mental-health service and NOT a recommendation
  // (legal-confirmed wording 2026-05-30; unified copy 2026-05-30 for N mirrors).
  "behavior-mirror": {
    ko: "본 화면은 귀하의 거래 기록 및 보유 종목에서 산출된 통계를 사실 그대로 표시합니다. 의료기기·심리상담·정신건강 서비스가 아니며, 특정 종목의 매수·매도를 권유하지 않습니다. 투자 판단의 책임은 이용자 본인에게 있습니다.",
    en: "This screen displays factual statistics computed from your own trade records and current holdings. It is not a medical device, psychological service, or mental health service, and does not constitute a recommendation to buy or sell any financial instrument. All investment decisions are your sole responsibility.",
  },
  // REMOVED 2026-05-10 per legal: "auto-trade" kind retired (autotrader.py 2026-05-05 물리 삭제, 표시광고법 §3 ① 4호 기만광고 회피)
} as const;

const COMMON_DISCLAIMER = {
  ko: "본 서비스는 투자자문이 아니며, 투자 판단의 책임은 이용자에게 있습니다.",
  en: "This service does not constitute investment advice. All investment decisions are your own responsibility.",
};

type DisclaimerType = keyof typeof DISCLAIMER_CONTENT;
type DisclaimerTheme = "dark" | "light";

interface DisclaimerBannerProps {
  type: DisclaimerType;
  /** Force the banner to always stay expanded (used for high-risk variants) */
  alwaysExpanded?: boolean;
  /** Theme — defaults to dark (Vantablack dashboard). Use "light" on ivory feature pages. */
  theme?: DisclaimerTheme;
  className?: string;
}

export function DisclaimerBanner({
  type,
  alwaysExpanded = false,
  theme = "dark",
  className,
}: DisclaimerBannerProps) {
  // CEO 2026-05-28: "면책 시각적 별로" — hierarchy uplift.
  //   • Collapsed by default (was expanded) → stately, calmer baseline
  //   • Top hairline accent in bronze-light (dark) / slate (light)
  //   • Playfair "Disclaimer" kicker (was 9px mono kicker, hard to read)
  //   • Primary summary at --pq-text-body-sm (14px) instead of 11px mono
  //   • 18px / 20px row padding (was 8px tight) — breathing room
  //   • Expand body in serif lead with KR/EN explicit subheads
  // Behavior preserved: alwaysExpanded prop, toggle, aria, content keys.
  const [expanded, setExpanded] = useState(false);
  const content = DISCLAIMER_CONTENT[type];

  const isExpanded = alwaysExpanded || expanded;
  const isDark = theme === "dark";

  return (
    <div
      className={cn(
        "rounded-[3px] transition-colors duration-300",
        isDark
          ? "border border-[rgba(245,240,232,0.12)] border-t-[var(--pq-bronze-light)] border-t-[1.5px] bg-[rgba(255,255,255,0.02)]"
          : "rounded-xl border border-slate-200 border-t-slate-400 border-t-[1.5px] bg-slate-50",
        className,
      )}
    >
      <button
        type="button"
        onClick={() => !alwaysExpanded && setExpanded((prev) => !prev)}
        className={cn(
          "flex w-full items-start gap-3 px-5 py-4 text-left md:px-6 md:py-5",
          !alwaysExpanded && "cursor-pointer",
          alwaysExpanded && "cursor-default",
        )}
        aria-expanded={isExpanded}
        aria-controls="disclaimer-panel"
      >
        <ShieldAlert
          className={cn(
            "h-4 w-4 shrink-0 mt-0.5",
            isDark ? "text-[var(--pq-bronze-light)]" : "text-slate-500",
          )}
          aria-hidden="true"
        />
        <div className="flex-1 min-w-0">
          {isDark && (
            <div
              className="font-display"
              style={{
                fontWeight: 500,
                fontSize: "var(--pq-text-h5)",
                lineHeight: 1.2,
                letterSpacing: "0.01em",
                color: "var(--pq-bronze-light)",
                marginBottom: 6,
              }}
            >
              Disclaimer
            </div>
          )}
          <p
            className={cn(
              "leading-relaxed",
              isDark
                ? "text-[rgba(245,240,232,0.88)]"
                : "text-slate-700 font-medium",
            )}
            style={{
              fontSize: "var(--pq-text-body-sm)",
              margin: 0,
            }}
          >
            {COMMON_DISCLAIMER.ko}
          </p>
        </div>
        {!alwaysExpanded && (
          <ChevronDown
            className={cn(
              "h-4 w-4 shrink-0 mt-1 transition-transform duration-200",
              isDark ? "text-[var(--pq-ivory-dim)]" : "text-slate-500",
              isExpanded && "rotate-180",
            )}
            aria-hidden="true"
          />
        )}
      </button>

      {isExpanded && (
        <div
          id="disclaimer-panel"
          role="region"
          className={cn(
            "px-5 pb-5 pt-3 border-t md:px-6 md:pb-6",
            isDark
              ? "border-[var(--pq-ivory-line)]"
              : "border-slate-200",
          )}
        >
          {/* KR detail */}
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: isDark
                ? "var(--pq-bronze-light)"
                : "rgb(100,116,139)",
              marginBottom: 8,
            }}
          >
            한국어 안내
          </div>
          <p
            className="font-serif"
            style={{
              fontSize: "var(--pq-text-body-sm)",
              lineHeight: 1.65,
              color: isDark ? "rgba(245,240,232,0.78)" : "rgb(71,85,105)",
              margin: 0,
            }}
          >
            {content.ko}
          </p>

          {/* EN detail */}
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: isDark
                ? "var(--pq-ivory-faint)"
                : "rgb(100,116,139)",
              marginTop: 18,
              marginBottom: 8,
            }}
          >
            English notice
          </div>
          <p
            className="font-serif"
            style={{
              fontSize: "var(--pq-text-body-sm)",
              lineHeight: 1.6,
              color: isDark ? "rgba(245,240,232,0.62)" : "rgb(100,116,139)",
              margin: 0,
            }}
          >
            {content.en}
          </p>
          <p
            className="font-serif"
            style={{
              fontSize: "var(--pq-text-body-sm)",
              lineHeight: 1.6,
              color: isDark ? "rgba(245,240,232,0.55)" : "rgb(100,116,139)",
              margin: "8px 0 0",
            }}
          >
            {COMMON_DISCLAIMER.en}
          </p>
        </div>
      )}
    </div>
  );
}
