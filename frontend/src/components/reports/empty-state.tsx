"use client";

/**
 * <EmptyState /> — Reports preview empty-state surface.
 *
 * Wave 2 (2026-04-29). Each `/reports/preview/<slug>` page renders this
 * surface when the user has no artifact of that type yet, or when the
 * backend returned an Empty response (`no_positions` / `no_trades` /
 * `not_in_portfolio` / `insufficient_history`).
 *
 * Design: v3 lock-in tokens — Vantablack ground, Bronze hairline + accent,
 * Playfair Display headline, Source Serif body, IBM Plex Mono eyebrow.
 * No bg-white. No bg-slate. No purple/blue.
 *
 * Compliance: copy never uses BUY/SELL/HOLD/추천/조언. Pure observational
 * "자동 생성" + "추가" verbs only.
 */

import * as React from "react";
import Link from "next/link";
import { ArrowRight, FileText } from "lucide-react";
import type { ArtifactType } from "@/lib/types";

export type EmptyStateReason =
  | "no_positions"
  | "no_trades"
  | "not_in_portfolio"
  | "insufficient_history"
  | "interactive"
  // Default fallback — no artifact of this type yet, no specific backend reason.
  | "no_artifact";

interface CopyEntry {
  eyebrow: string;
  title: string;
  body: string;
  ctaLabel: string;
  ctaHref: string;
}

/**
 * Per-reason copy matrix (한국어 우선 — KR convention §5).
 * The CTA is a sensible default; callers can override via `ctaHref`/`ctaLabel`.
 */
const COPY: Record<EmptyStateReason, CopyEntry> = {
  no_positions: {
    eyebrow: "PORTFOLIO REQUIRED",
    title: "아직 보유 종목이 없어요",
    body:
      "첫 매입 기록 후 자동으로 생성됩니다. 포트폴리오에 포지션을 추가하면 다음 주기에 리포트가 도착해요.",
    ctaLabel: "포지션 추가",
    ctaHref: "/portfolio",
  },
  no_trades: {
    eyebrow: "TRADES REQUIRED",
    title: "아직 거래 내역이 없어요",
    body:
      "첫 거래 후 자동으로 생성됩니다. 매입·매각 기록이 쌓이면 리포트에 반영돼요.",
    ctaLabel: "거래 추가",
    ctaHref: "/portfolio",
  },
  not_in_portfolio: {
    eyebrow: "WATCHLIST REQUIRED",
    title: "보유 종목만 분석 가능합니다",
    body:
      "이 리포트는 사용자의 포트폴리오 또는 관심 종목을 기반으로 작성됩니다. 종목을 먼저 추가해 주세요.",
    ctaLabel: "관심 종목 추가",
    ctaHref: "/watchlist",
  },
  insufficient_history: {
    eyebrow: "MORE HISTORY NEEDED",
    title: "거래 기록이 충분하지 않아요",
    body:
      "거래가 6개월 이상 쌓이면 자동으로 생성됩니다. 그동안은 주간 메모와 KPI 대시보드를 활용해 주세요.",
    ctaLabel: "주간 메모 보기",
    ctaHref: "/reports/preview/weekly-memo",
  },
  interactive: {
    eyebrow: "INTERACTIVE REPORT",
    title: "이 리포트는 입력이 필요합니다",
    body:
      "DD 체크리스트는 사용자가 직접 항목을 채워야 완성됩니다. 종목을 선택하고 체크리스트를 시작해 주세요.",
    ctaLabel: "체크리스트 열기",
    ctaHref: "/reports",
  },
  no_artifact: {
    eyebrow: "NOT YET GENERATED",
    title: "아직 생성된 리포트가 없어요",
    body:
      "이 유형의 리포트는 아직 생성되지 않았습니다. 다음 자동 발송 주기에 도착하거나, 직접 생성을 요청할 수 있어요.",
    ctaLabel: "내 리포트 보기",
    ctaHref: "/reports",
  },
};

interface EmptyStateProps {
  /** Artifact type — used only for analytics/debugging breadcrumbs. */
  type?: ArtifactType;
  /** Reason from backend Empty response. Defaults to `"no_artifact"`. */
  reason?: EmptyStateReason;
  /** Override default CTA href. */
  ctaHref?: string;
  /** Override default CTA label. */
  ctaLabel?: string;
}

export function EmptyState({
  type,
  reason = "no_artifact",
  ctaHref,
  ctaLabel,
}: EmptyStateProps) {
  const copy = COPY[reason] ?? COPY.no_artifact;
  const href = ctaHref ?? copy.ctaHref;
  const label = ctaLabel ?? copy.ctaLabel;

  return (
    <div
      role="status"
      aria-live="polite"
      data-pq-empty-type={type ?? "unknown"}
      data-pq-empty-reason={reason}
      style={{
        // Vantablack ground (v3). NEVER bg-white.
        backgroundColor: "#0A0A0A",
        border: "1px solid rgba(184,149,106,0.20)",
        borderRadius: 4,
        padding: "64px 56px",
        maxWidth: 720,
        margin: "48px auto",
      }}
    >
      {/* Bronze hairline + eyebrow */}
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 10,
          marginBottom: 24,
        }}
      >
        <span
          aria-hidden
          style={{
            display: "inline-block",
            width: 28,
            height: 1,
            backgroundColor: "rgba(184,149,106,0.7)",
          }}
        />
        <span
          className="font-mono uppercase tabular-nums"
          style={{
            fontSize: 10.5,
            letterSpacing: "0.22em",
            color: "var(--pq-bronze, #B8956A)",
          }}
        >
          {copy.eyebrow}
        </span>
      </div>

      {/* Icon block */}
      <div
        aria-hidden
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 56,
          height: 56,
          borderRadius: 4,
          border: "0.5pt solid rgba(184,149,106,0.32)",
          backgroundColor: "rgba(139,111,71,0.10)",
          marginBottom: 24,
        }}
      >
        <FileText
          size={22}
          strokeWidth={1.6}
          style={{ color: "var(--pq-bronze, #B8956A)" }}
        />
      </div>

      {/* Headline — Playfair (pq-detail-h2 token) */}
      <h2
        className="pq-detail-h2"
        style={{
          fontFamily:
            'var(--pq-font-display,"Playfair Display",Georgia,serif)',
          fontWeight: 500,
          fontSize: 30,
          lineHeight: 1.18,
          letterSpacing: "-0.01em",
          color: "var(--pq-ivory, #F5F0E8)",
          margin: 0,
        }}
      >
        {copy.title}
      </h2>

      {/* Body — Source Serif */}
      <p
        className="font-serif"
        style={{
          fontFamily: 'var(--pq-font-serif,"Source Serif 4",Georgia,serif)',
          fontSize: 14.5,
          lineHeight: 1.7,
          color: "rgba(245,240,232,0.72)",
          marginTop: 16,
          marginBottom: 32,
          maxWidth: "56ch",
        }}
      >
        {copy.body}
      </p>

      {/* CTA — bronze inline link */}
      <Link
        href={href}
        className="pq-ink-btn-bronze"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          fontFamily:
            'var(--pq-font-mono,"IBM Plex Mono",ui-monospace,monospace)',
          fontSize: 11,
          letterSpacing: "0.18em",
          textTransform: "uppercase",
          color: "var(--pq-ink, #050505)",
          backgroundColor: "var(--pq-bronze, #B8956A)",
          padding: "12px 18px",
          borderRadius: 2,
          textDecoration: "none",
          transition: "opacity 200ms ease",
        }}
      >
        {label}
        <ArrowRight size={14} strokeWidth={1.8} />
      </Link>
    </div>
  );
}

export default EmptyState;
