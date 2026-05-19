"use client";

/**
 * <EarningsPreBriefCard /> — Card 3 of /home v2.
 *
 * Wired 2026-05-19 (P2 #11). Pulls GET /api/brief/earnings/upcoming?days=7
 * via `useEarningsBrief` (lib/hooks.ts) — backend cache 6h, SWR refresh 1h.
 *
 * Layout:
 *   ┌──────────────────────────────────────┐
 *   │ eyebrow                              │
 *   │ HEADLINE (issuer name · WHEN)        │
 *   │ EPS · Revenue · 30d-proxy trio       │  ← bronze metric strip
 *   │                                      │
 *   │ Queue · 7 days                       │
 *   │  · row 1                             │
 *   │  · row 2                             │
 *   │  · row 3                             │
 *   └──────────────────────────────────────┘
 *
 * Legal:
 *   - "30-day proxy" label is mandatory (true implied move requires
 *     options chains we don't ingest — backend `_implied_move_pct`
 *     uses 30d avg-move surrogate).
 *   - No advice / no recommendation vocabulary.
 *   - feedback_ticker_display: issuer name wins; ticker code shown
 *     parenthetically only when name == ticker echo.
 */

import * as React from "react";
import { HomeCard } from "./home-card";
import { useEarningsBrief } from "@/lib/hooks";
import { displayTicker, normalizeTicker } from "@/lib/format";

function fmtWhen(iso: string): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "—";
  const d = new Date(t);
  // KST friendly short label: "5월 22일 22:30"
  return d.toLocaleString("ko-KR", {
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function fmtEps(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  const sign = v < 0 ? "−" : "";
  return `${sign}$${Math.abs(v).toFixed(2)}`;
}

function fmtRevenue(millions: number | null | undefined): string {
  if (millions == null || !Number.isFinite(millions)) return "—";
  const abs = Math.abs(millions);
  if (abs >= 1000) return `$${(millions / 1000).toFixed(2)}B`;
  return `$${millions.toFixed(0)}M`;
}

function fmtMovePct(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return `${v.toFixed(2)}%`;
}

/**
 * Issuer label — name first per feedback_ticker_display. When the
 * resolved label still equals the bare ticker code, we don't suffix
 * a duplicate "(005930)" in parens.
 */
function issuerLabel(ticker: string, name: string | null | undefined): string {
  return displayTicker(ticker, name) || normalizeTicker(ticker) || ticker;
}

export function EarningsPreBriefCard() {
  const { data, isLoading, error } = useEarningsBrief(7);

  const hasNext = Boolean(data?.next_event);
  const next = data?.next_event ?? null;
  const queue = data?.queue ?? [];

  return (
    <HomeCard
      href="/reports"
      eyebrow="Pre-Brief · 7-day window"
      cornerCta="Pre-brief ›"
    >
      {/* Headline issuer + datetime */}
      <div
        className="font-display"
        style={{
          fontWeight: 500,
          fontSize: "var(--pq-text-h3)",
          lineHeight: 1.1,
          letterSpacing: "-0.02em",
          color: "var(--pq-ivory)",
          marginBottom: 8,
        }}
      >
        {isLoading || error
          ? "—"
          : hasNext && next
            ? issuerLabel(next.ticker, next.name)
            : "—"}
      </div>

      {hasNext && next ? (
        <p
          className="font-serif"
          style={{
            fontSize: "var(--pq-text-body)",
            lineHeight: 1.55,
            color: "rgba(245,240,232,0.82)",
            margin: "0 0 16px 0",
          }}
        >
          Next print · {fmtWhen(next.when)} KST
        </p>
      ) : (
        <p
          className="font-serif"
          style={{
            fontSize: "var(--pq-text-body)",
            lineHeight: 1.55,
            color: "rgba(245,240,232,0.55)",
            margin: "0 0 16px 0",
            fontStyle: "italic",
          }}
        >
          {error
            ? "Pre-brief queue is currently unavailable."
            : isLoading
              ? "Loading pre-brief queue…"
              : "다음 7일 내 예정된 실적 발표 없음."}
        </p>
      )}

      {/* EPS / Revenue / 30d-proxy trio — only when we have a headline */}
      {hasNext && next ? (
        <div
          aria-label="Estimates strip"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
            gap: 12,
            borderTop: "1px solid var(--pq-hairline-ink, rgba(245,240,232,0.10))",
            paddingTop: 12,
            marginBottom: 20,
          }}
        >
          <MetricCell label="EPS est." value={fmtEps(next.eps_est)} />
          <MetricCell label="Revenue est." value={fmtRevenue(next.rev_est)} />
          <MetricCell
            label="30-day proxy"
            value={fmtMovePct(next.implied_move)}
            tooltip="30d realised-volatility proxy — not a true implied move (options chain not ingested)."
          />
        </div>
      ) : null}

      {/* Queue · 7 days */}
      <div
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.22em",
          color: "rgba(245,240,232,0.55)",
          textTransform: "uppercase",
          marginTop: "auto",
        }}
      >
        Queue · 7 days
      </div>

      {queue.length > 0 ? (
        <ul
          style={{
            margin: "8px 0 0 0",
            padding: 0,
            listStyle: "none",
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}
        >
          {queue.slice(0, 3).map((q) => (
            <li
              key={`${q.ticker}-${q.when}`}
              className="font-serif"
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "baseline",
                gap: 12,
                fontSize: "var(--pq-text-body)",
                color: "rgba(245,240,232,0.82)",
                lineHeight: 1.4,
              }}
            >
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {issuerLabel(q.ticker, q.name)}
              </span>
              <span
                className="font-mono tabular-nums"
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  color: "rgba(245,240,232,0.55)",
                  flexShrink: 0,
                }}
              >
                {fmtWhen(q.when)}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <div
          className="font-serif"
          style={{
            fontSize: "var(--pq-text-body)",
            lineHeight: 1.6,
            color: "rgba(245,240,232,0.55)",
            margin: "8px 0 0 0",
            fontStyle: "italic",
          }}
        >
          {hasNext ? "추가 예정 항목 없음." : "—"}
        </div>
      )}
    </HomeCard>
  );
}

/* ── MetricCell — bronze label + ivory tabular value ─────────────── */
function MetricCell({
  label,
  value,
  tooltip,
}: {
  label: string;
  value: string;
  tooltip?: string;
}) {
  return (
    <div title={tooltip}>
      <div
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.22em",
          color: "var(--pq-bronze)",
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div
        className="font-mono tabular-nums"
        style={{
          fontSize: "var(--pq-text-body)",
          color: "var(--pq-ivory)",
          lineHeight: 1.2,
        }}
      >
        {value}
      </div>
    </div>
  );
}

export default EarningsPreBriefCard;
