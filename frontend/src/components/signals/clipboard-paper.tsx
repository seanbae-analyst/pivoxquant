"use client";

/**
 * <ClipboardPaper /> — one signals column rendered on ivory paper.
 *
 * Each column (Positive / Neutral / Negative) becomes a clipboard sheet
 * with a header strip (kicker + title + tally + tone stripe) and a
 * memo-list body of SignalMemoStrip rows. Drawer toggles within the
 * paper so the observation memo unfolds in place.
 *
 * Tone stripe color uses the paper-safe palette (#4a7a52 / #a54545 /
 * bronze neutral) — never the ink-terminal greens/reds.
 *
 * Pure presentation. Receives pre-filtered items and callbacks from the
 * page. SWR / endpoints untouched.
 */

import * as React from "react";
import {
  SignalMemoStrip,
  type MemoSignalItem,
} from "@/components/signals/signal-memo-strip";

type Tone = "pos" | "neu" | "neg";

interface Props {
  kicker: string;
  title: string;
  tone: Tone;
  items: MemoSignalItem[];
  expandedId: string | null;
  onToggle: (ticker: string) => void;
  onOpenDetail: (ticker: string) => void;
  emptyMessage?: string;
}

function toneColor(tone: Tone): string {
  if (tone === "pos") return "#4a7a52";
  if (tone === "neg") return "#a54545";
  return "rgba(139,111,71,0.7)";
}

function toneLabel(tone: Tone): string {
  if (tone === "pos") return "Above Threshold";
  if (tone === "neg") return "Below Threshold";
  return "Within Band";
}

export function ClipboardPaper({
  kicker,
  title,
  tone,
  items,
  expandedId,
  onToggle,
  onOpenDetail,
  emptyMessage = "No observations in this band.",
}: Props) {
  const stripe = toneColor(tone);

  return (
    <div
      style={{
        padding: "clamp(22px, 2.6vw, 34px)",
        minHeight: 420,
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Clip at top — bronze wafer */}
      <div
        aria-hidden
        style={{
          position: "absolute",
          top: -8,
          left: "50%",
          transform: "translateX(-50%)",
          width: 60,
          height: 14,
          borderRadius: 3,
          background:
            "linear-gradient(180deg, #c9a874 0%, #B8956A 55%, #5a4528 100%)",
          boxShadow:
            "inset 0 1px 0 rgba(255,255,255,0.28), inset 0 -1px 2px rgba(0,0,0,0.35), 0 2px 4px rgba(0,0,0,0.25)",
          zIndex: 2,
        }}
      />

      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: 12,
          marginBottom: 10,
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div className="pq-paper-kicker">{kicker}</div>
          <div
            style={{
              fontSize: "clamp(1.35rem, 2.2vw, 1.7rem)",
              lineHeight: 1.05,
              letterSpacing: "-0.02em",
              color: "#1a1a1a",
              marginTop: 4,
            }}
          className="font-serif" >
            {title}
          </div>
          <div
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              color: "rgba(20,20,20,0.48)",
              marginTop: 2,
            }}
          className="font-serif" >
            {toneLabel(tone)}
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              textTransform: "uppercase",
              color: "rgba(20,20,20,0.48)",
              fontWeight: 600,
            }}
          className="font-sans" >
            Count
          </div>
          <div
            style={{
              fontSize: "var(--pq-text-quote)",
              fontVariantNumeric: "tabular-nums",
              color: "#141414",
              lineHeight: 1.1,
              marginTop: 2,
            }}
          className="font-serif" >
            {items.length}
          </div>
        </div>
      </div>

      {/* Tone stripe — thin ruled line under header */}
      <div
        aria-hidden
        style={{
          height: 2,
          width: 48,
          background: stripe,
          marginBottom: 10,
          opacity: 0.75,
        }}
      />

      {/* Memo list */}
      {items.length === 0 ? (
        <div
          style={{
            marginTop: 20,
            padding: "40px 0",
            textAlign: "center",
            fontSize: "var(--pq-text-body)",
            color: "rgba(20,20,20,0.42)",
            borderTop: "0.5px solid rgba(184,149,106,0.22)",
          }}
        className="font-serif" >
          {emptyMessage}
        </div>
      ) : (
        <ul
          style={{
            listStyle: "none",
            margin: 0,
            padding: 0,
            borderTop: "0.5px solid rgba(184,149,106,0.3)",
          }}
        >
          {items.map((item) => (
            <SignalMemoStrip
              key={item.ticker}
              item={item}
              expanded={expandedId === item.ticker}
              onToggle={() => onToggle(item.ticker)}
              onOpenDetail={() => onOpenDetail(item.ticker)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

export default ClipboardPaper;
