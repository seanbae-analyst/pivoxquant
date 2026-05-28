"use client";

/**
 * <SignalsHeroV2 /> — editorial hero for /signals v2.
 *
 * Source: design-mockups/signals-v2/SPEC.md §1.
 * 80/64 padding, no card border, hairline-bottom seal.
 * H1 Playfair 500 / 48px / 1.05 line. Bronze italic accents on
 * "observed" and "filtered". Inline counts use mono tabular.
 *
 * Legal: POSITIVE / NEGATIVE / NEUTRAL only. Static editorial copy.
 */

import * as React from "react";
import { useT, useLocale } from "@/lib/locale";

interface Counts {
  positive: number;
  negative: number;
  neutral: number;
  symbols: number;
}

interface Props {
  eyebrow?: string;
  counts: Counts;
  loading?: boolean;
}

export function SignalsHeroV2({ eyebrow, counts, loading = false }: Props) {
  const t = useT();
  const { locale } = useLocale();
  const resolvedEyebrow = eyebrow ?? t("signals.eyebrow");

  // Locale-specific headline rendering.
  // KO: original Korean editorial prose with bronze italic spans.
  // EN: English equivalent with same bronze italic accents.
  const Headline =
    locale === "ko" ? (
      <>
        스트림은{" "}
        <span style={{ fontStyle: "italic", color: "var(--pq-bronze, #B8956A)" }}>관측</span>될 뿐,
        <br />
        조언이 아닙니다 —{" "}
        <span style={{ fontStyle: "italic", color: "var(--pq-bronze, #B8956A)" }}>보유</span>
        하신 종목으로 좁혔습니다.
      </>
    ) : (
      <>
        The stream is{" "}
        <span style={{ fontStyle: "italic", color: "var(--pq-bronze, #B8956A)" }}>observed</span>,
        <br />
        not advised — filtered to your{" "}
        <span style={{ fontStyle: "italic", color: "var(--pq-bronze, #B8956A)" }}>holdings</span>.
      </>
    );

  const loadingBody =
    locale === "ko"
      ? "오늘의 관측을 집계 중입니다 — 보유 종목 전반의 신호를 읽고 있어요."
      : t("signals.heroLoadingBody");

  const countsBody =
    locale === "ko" ? (
      <>
        오늘 시스템이 표면화한 관측은{" "}
        <span className="font-mono" style={{ fontVariantNumeric: "tabular-nums", color: "var(--pq-positive, #b8956a)" }}>{counts.positive}</span>건 긍정,{" "}
        <span className="font-mono" style={{ fontVariantNumeric: "tabular-nums", color: "var(--pq-negative, #d18888)" }}>{counts.negative}</span>건 부정,{" "}
        <span className="font-mono" style={{ fontVariantNumeric: "tabular-nums", color: "rgba(245,240,232,0.55)" }}>{counts.neutral}</span>건 중립이며, 총{" "}
        <span className="font-mono" style={{ fontVariantNumeric: "tabular-nums", color: "var(--pq-ivory, #F5F0E8)" }}>{counts.symbols}</span>개 종목에 걸쳐 있습니다. 이는 매매 지시가 아닙니다.
      </>
    ) : (
      <>
        Today the system surfaced{" "}
        <span className="font-mono" style={{ fontVariantNumeric: "tabular-nums", color: "var(--pq-positive, #b8956a)" }}>{counts.positive}</span>{" positive, "}
        <span className="font-mono" style={{ fontVariantNumeric: "tabular-nums", color: "var(--pq-negative, #d18888)" }}>{counts.negative}</span>{" negative, "}
        <span className="font-mono" style={{ fontVariantNumeric: "tabular-nums", color: "rgba(245,240,232,0.55)" }}>{counts.neutral}</span>{" neutral across "}
        <span className="font-mono" style={{ fontVariantNumeric: "tabular-nums", color: "var(--pq-ivory, #F5F0E8)" }}>{counts.symbols}</span>{" symbols. Not a trading directive."}
      </>
    );

  return (
    <header
      style={{
        padding: "80px 0 64px",
        borderBottom: "1px solid var(--pq-hairline, var(--pq-ivory-line))",
        marginBottom: 0,
      }}
    >
      <div
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.22em",
          color: "var(--pq-bronze, #B8956A)",
          marginBottom: 14,
        }}
      >
        {resolvedEyebrow}
      </div>

      <h1
        className="font-display"
        style={{
          fontWeight: 500,
          fontSize: "clamp(34px, 5vw, 48px)",
          lineHeight: 1.2,
          letterSpacing: "-0.02em",
          color: "var(--pq-ivory, #F5F0E8)",
          margin: 0,
          maxWidth: 880,
          wordBreak: "keep-all",
          overflowWrap: "anywhere",
        }}
      >
        {Headline}
      </h1>

      <p
        className="font-serif"
        style={{
          fontSize: "var(--pq-text-lead)",
          lineHeight: 1.7,
          color: "rgba(245,240,232,0.82)",
          maxWidth: 720,
          marginTop: 22,
          wordBreak: "keep-all",
          overflowWrap: "anywhere",
        }}
      >
        {loading ? loadingBody : countsBody}
      </p>
    </header>
  );
}
