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

export function SignalsHeroV2({ eyebrow = "시그널 · 실시간", counts, loading = false }: Props) {
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
        {eyebrow}
      </div>

      <h1
        className="font-display"
        style={{
          fontWeight: 500,
          fontSize: "clamp(34px, 5vw, 48px)",
          // CEO bug "폰트 겹친다": 한국어 글리프(특히 받침)는 Playfair
          // metrics보다 descender가 깊다. 1.05는 EN-only 가정.
          // 1.2로 늘려 KR/EN 혼합 헤딩에서 줄 사이 충돌 제거.
          lineHeight: 1.2,
          letterSpacing: "-0.02em",
          color: "var(--pq-ivory, #F5F0E8)",
          margin: 0,
          maxWidth: 880,
          // CEO 2026-05-20 "한 문장이 부분 줄바꿈": KR headline must
          // break at 어절 boundaries, not mid-word.
          wordBreak: "keep-all",
          overflowWrap: "anywhere",
        }}
      >
        스트림은{" "}
        <span
          style={{
            fontStyle: "italic",
            color: "var(--pq-bronze, #B8956A)",
          }}
        >
          관측
        </span>
        될 뿐,
        <br />
        조언이 아닙니다 —{" "}
        <span
          style={{
            fontStyle: "italic",
            color: "var(--pq-bronze, #B8956A)",
          }}
        >
          보유
        </span>
        하신 종목으로 좁혔습니다.
      </h1>

      <p
        className="font-serif"
        style={{
          fontSize: "var(--pq-text-lead)",
          lineHeight: 1.7,
          color: "rgba(245,240,232,0.82)",
          maxWidth: 720,
          marginTop: 22,
          // CEO 2026-05-20: KR prose breaks at 어절 boundaries.
          wordBreak: "keep-all",
          overflowWrap: "anywhere",
        }}
      >
        {loading ? (
          <>오늘의 관측을 집계 중입니다 — 보유 종목 전반의 신호를 읽고 있어요.</>
        ) : (
          <>
            오늘 시스템이 표면화한 관측은{" "}
            <span
              className="font-mono"
              style={{
                fontVariantNumeric: "tabular-nums",
                color: "var(--pq-positive, #b8956a)",
              }}
            >
              {counts.positive}
            </span>
            건 긍정,{" "}
            <span
              className="font-mono"
              style={{
                fontVariantNumeric: "tabular-nums",
                color: "var(--pq-negative, #d18888)",
              }}
            >
              {counts.negative}
            </span>
            건 부정,{" "}
            <span
              className="font-mono"
              style={{
                fontVariantNumeric: "tabular-nums",
                color: "rgba(245,240,232,0.55)",
              }}
            >
              {counts.neutral}
            </span>
            건 중립이며, 총{" "}
            <span
              className="font-mono"
              style={{
                fontVariantNumeric: "tabular-nums",
                color: "var(--pq-ivory, #F5F0E8)",
              }}
            >
              {counts.symbols}
            </span>
            개 종목에 걸쳐 있습니다. 이는 매매 지시가 아닙니다.
          </>
        )}
      </p>
    </header>
  );
}
