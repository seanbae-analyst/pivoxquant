"use client";

/**
 * <SignalMemoStrip /> — single memo row on an ivory clipboard paper.
 *
 * Rendered on paper, not on ink. Bronze hairline separator, compact
 * header with ticker + POSITIVE/NEGATIVE/NEUTRAL chip, price/change,
 * composite score. Clicking the header toggles an inline drawer that
 * unfolds the editorial observation + 4-pillar breakdown — all
 * contained within the paper (no modal).
 *
 * Legal: POSITIVE / NEGATIVE / NEUTRAL only. "observed" framing
 * preserved. No BUY/SELL/HOLD or advice language.
 */

import * as React from "react";
import { ChevronDown } from "lucide-react";

export interface MemoSignalItem {
  ticker: string;
  name: string;
  signal: string;
  score: number;
  price: number;
  change_pct: number;
  sector: string;
  currency: "USD" | "KRW";
  is_korean: boolean;
  tech_score?: number;
  fund_score?: number;
  news_score?: number;
  quant_score?: number;
}

interface Props {
  item: MemoSignalItem;
  expanded: boolean;
  onToggle: () => void;
  onOpenDetail: () => void;
}

function signalLabel(sig: string) {
  if (sig === "POSITIVE") return "Positive";
  if (sig === "NEGATIVE") return "Negative";
  return "Neutral";
}

function chipColor(sig: string) {
  if (sig === "POSITIVE") return "#4a7a52";
  if (sig === "NEGATIVE") return "#a54545";
  return "rgba(20,20,20,0.55)";
}

function formatPrice(item: MemoSignalItem): string {
  if (item?.price == null) return "—";
  if (item.currency === "KRW") {
    return `₩${Math.round(item.price).toLocaleString("ko-KR")}`;
  }
  return `$${item.price.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function fmtPct(n: number): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const sign = n >= 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

function signalExplanation(sig: string) {
  if (sig === "POSITIVE")
    return "Composite score observed above the upper threshold. Four-pillar model registered tailwinds across trend, fundamentals, news, and quant factors.";
  if (sig === "NEGATIVE")
    return "Composite score observed below the lower threshold. Four-pillar model registered headwinds across the pillars.";
  return "Composite score sits inside the observed neutral band — no single pillar reading dominates.";
}

export function SignalMemoStrip({
  item,
  expanded,
  onToggle,
  onOpenDetail,
}: Props) {
  const isPositive = (item?.change_pct ?? 0) >= 0;
  const tone = chipColor(item.signal);
  const subScores: { label: string; value: number | undefined }[] = [
    { label: "Trend", value: item.tech_score },
    { label: "Fund.", value: item.fund_score },
    { label: "News", value: item.news_score },
    { label: "Quant", value: item.quant_score },
  ];

  return (
    <li
      style={{
        borderBottom: "0.5px solid rgba(184,149,106,0.22)",
      }}
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="group w-full px-3 py-3 text-left transition-colors hover:bg-[rgba(184,149,106,0.06)]"
        style={{ display: "block" }}
      >
        <div className="flex items-center gap-3">
          {/* Left — identity */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span
                style={{
                  fontSize: 14,
                  color: "#1a1a1a",
                  letterSpacing: "-0.01em",
                  }}
                className="truncate font-serif"
              >
                {item.name || item.ticker}
              </span>
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  padding: "2px 8px",
                  fontSize: 12,
                  letterSpacing: "0.22em",
                  textTransform: "uppercase",
                  fontWeight: 600,
                  color: tone,
                  border: `0.5px solid ${tone}`,
                  borderRadius: 2,
                  background: "transparent",
                  whiteSpace: "nowrap",
                }}
              className="font-sans" >
                {signalLabel(item.signal)}
              </span>
            </div>
            <div
              style={{
                fontSize: 12,
                letterSpacing: "0.16em",
                color: "rgba(20,20,20,0.48)",
                textTransform: "uppercase",
                marginTop: 3,
              }}
            className="font-mono" >
              {item.ticker}
              {item.sector ? ` · ${item.sector}` : ""}
            </div>
          </div>

          {/* Mid — price */}
          <div style={{ textAlign: "right", minWidth: 72 }}>
            <div
              style={{
                fontSize: 14,
                fontVariantNumeric: "tabular-nums",
                color: "#1a1a1a",
              }}
            className="font-mono" >
              {formatPrice(item)}
            </div>
            <div
              style={{
                fontSize: 12,
                fontVariantNumeric: "tabular-nums",
                color: isPositive ? "#4a7a52" : "#a54545",
                marginTop: 1,
              }}
            className="font-mono" >
              {fmtPct(item?.change_pct ?? 0)}
            </div>
          </div>

          {/* Right — composite score */}
          <div style={{ textAlign: "right", width: 52 }}>
            <div
              style={{
                fontSize: 12,
                letterSpacing: "0.22em",
                textTransform: "uppercase",
                color: "rgba(20,20,20,0.48)",
                fontWeight: 600,
              }}
            className="font-sans" >
              Score
            </div>
            <div
              style={{
                fontSize: 18,
                fontVariantNumeric: "tabular-nums",
                color: "#141414",
                lineHeight: 1.1,
                marginTop: 2,
              }}
            className="font-serif" >
              {Math.round(item.score ?? 0)}
            </div>
          </div>

          <ChevronDown
            className={
              "h-3.5 w-3.5 shrink-0 transition-transform duration-300 " +
              (expanded ? "rotate-180" : "")
            }
            strokeWidth={1.5}
            style={{ color: "rgba(20,20,20,0.45)" }}
          />
        </div>
      </button>

      {/* Inline drawer — bronze hairline-bordered memo on same sheet */}
      <div
        aria-hidden={!expanded}
        style={{
          overflow: "hidden",
          maxHeight: expanded ? 400 : 0,
          opacity: expanded ? 1 : 0,
          transition:
            "max-height 360ms cubic-bezier(0.16, 1, 0.3, 1), opacity 260ms ease",
        }}
      >
        <div
          style={{
            padding: "14px 14px 18px",
            background: "rgba(184,149,106,0.05)",
            borderTop: "0.5px dashed rgba(184,149,106,0.35)",
          }}
        >
          <div
            style={{
              fontSize: 12,
              letterSpacing: "0.22em",
              textTransform: "uppercase",
              color: "rgba(20,20,20,0.55)",
              fontWeight: 600,
              marginBottom: 6,
            }}
          className="font-sans" >
            Observation
          </div>
          <p
            style={{
              fontSize: 14,
              lineHeight: 1.55,
              color: "rgba(20,20,20,0.78)",
              margin: 0,
              maxWidth: "58ch",
            }}
          className="font-serif" >
            {signalExplanation(item.signal)}
          </p>

          {/* 4-pillar breakdown */}
          <div style={{ marginTop: 14 }}>
            <div
              style={{
                fontSize: 12,
                letterSpacing: "0.22em",
                textTransform: "uppercase",
                color: "rgba(20,20,20,0.55)",
                fontWeight: 600,
                marginBottom: 8,
              }}
            className="font-sans" >
              Four-Pillar Breakdown
            </div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
                gap: 10,
              }}
            >
              {subScores.map((s) => {
                const v = Math.max(0, Math.min(100, s.value ?? 0));
                return (
                  <div key={s.label}>
                    <div className="flex items-baseline justify-between">
                      <span
                        style={{
                          fontSize: 12,
                          letterSpacing: "0.18em",
                          textTransform: "uppercase",
                          color: "rgba(20,20,20,0.55)",
                        }}
                      className="font-mono" >
                        {s.label}
                      </span>
                      <span
                        style={{
                          fontSize: 12,
                          fontVariantNumeric: "tabular-nums",
                          color: "#1a1a1a",
                        }}
                      className="font-mono" >
                        {s.value != null ? Math.round(s.value) : "—"}
                      </span>
                    </div>
                    <div
                      style={{
                        marginTop: 4,
                        height: 2,
                        width: "100%",
                        background: "rgba(20,20,20,0.1)",
                      }}
                    >
                      <div
                        style={{
                          height: "100%",
                          width: `${v}%`,
                          background: "rgba(184,149,106,0.9)",
                          transition: "width 300ms ease",
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div
            style={{
              marginTop: 14,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
              flexWrap: "wrap",
            }}
          >
            <span
              style={{
                fontSize: 11,
                color: "rgba(20,20,20,0.5)",
              }}
            className="font-serif" >
              · indicator change observed
            </span>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onOpenDetail();
              }}
              style={{
                fontSize: 10,
                letterSpacing: "0.22em",
                textTransform: "uppercase",
                color: "#B8956A",
                fontWeight: 600,
                background: "transparent",
                border: "none",
                padding: 0,
                cursor: "pointer",
              }}
              className="hover:underline font-sans"
            >
              Open file →
            </button>
          </div>
        </div>
      </div>
    </li>
  );
}

export default SignalMemoStrip;
