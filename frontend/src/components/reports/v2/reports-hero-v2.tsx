"use client";

/**
 * <ReportsHeroV2 /> — editorial hero for /reports v2 ("CFO Archive").
 *
 * Source: design-mockups/reports-v2/SPEC.md §1.
 * 80/64 padding, hairline-bottom seal, no card border.
 * H1 Playfair 500 / 48px / 1.05 line. Bronze italic accents on
 * "published" and "artifacts". Inline counts use mono tabular.
 *
 * Legal: pure editorial copy. No banned vocabulary.
 */

import * as React from "react";

interface Counts {
  memos: number;
  briefs: number;
  bragCards: number;
}

interface Props {
  eyebrow?: string;
  counts: Counts;
  loading?: boolean;
}

export function ReportsHeroV2({
  eyebrow = "Archive · CFO",
  counts,
  loading = false,
}: Props) {
  return (
    <header
      style={{
        // CEO 2026-05-28 직격 #5: 모바일 375px 에서 80/64 패딩 = 1/3 화면을
        // 빈 헤더가 먹음. clamp 으로 24px(모바일) → 80px(데스크) 스케일.
        padding: "clamp(40px, 8vw, 80px) 0 clamp(28px, 6vw, 64px)",
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
          lineHeight: 1.05,
          letterSpacing: "-0.02em",
          color: "var(--pq-ivory, #F5F0E8)",
          margin: 0,
          maxWidth: 880,
        }}
      >
        Everything we&apos;ve{" "}
        <span
          style={{
            color: "var(--pq-bronze, #B8956A)",
          }}
        >
          published
        </span>
        ,
        <br />
        kept as quiet{" "}
        <span
          style={{
            color: "var(--pq-bronze, #B8956A)",
          }}
        >
          artifacts
        </span>
        .
      </h1>

      <p
        className="font-serif"
        style={{
          fontSize: "var(--pq-text-lead)",
          lineHeight: 1.6,
          color: "rgba(245,240,232,0.82)",
          maxWidth: 720,
          marginTop: 22,
        }}
      >
        {loading ? (
          <>Indexing the library — counting every memo and brief on the shelf.</>
        ) : counts.memos + counts.briefs + counts.bragCards === 0 ? (
          // CEO 2026-05-28 직격 #3 "report 부분 엉망" — 신규 유저는 0/0/0 카운트가
          // "0 memos, 0 pre-briefs, and 0 brag cards" 로 나와 빈 책장이 더 빈약해
          // 보였음. 0일 때는 카운트 대신 stately 안내로 대체.
          <>
            The shelf is empty for now. Your first weekly memo lands automatically
            on Monday — drafted by AI, reviewed by you. None of it is instruction
            to trade.
          </>
        ) : (
          <>
            On the shelf this year:{" "}
            <span
              className="font-mono"
              style={{
                fontVariantNumeric: "tabular-nums",
                color: "var(--pq-ivory, #F5F0E8)",
              }}
            >
              {counts.memos}
            </span>{" "}
            memo{counts.memos === 1 ? "" : "s"},{" "}
            <span
              className="font-mono"
              style={{
                fontVariantNumeric: "tabular-nums",
                color: "var(--pq-ivory, #F5F0E8)",
              }}
            >
              {counts.briefs}
            </span>{" "}
            pre-brief{counts.briefs === 1 ? "" : "s"}, and{" "}
            <span
              className="font-mono"
              style={{
                fontVariantNumeric: "tabular-nums",
                color: "var(--pq-ivory, #F5F0E8)",
              }}
            >
              {counts.bragCards}
            </span>{" "}
            brag card{counts.bragCards === 1 ? "" : "s"}. Drafted by AI, reviewed by you. None of it is
            instruction to trade.
          </>
        )}
      </p>

      <div
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.22em",
          color: "rgba(245,240,232,0.45)",
          marginTop: 18,
        }}
      >
        Drafted by AI · Reviewed by you
      </div>
    </header>
  );
}

export default ReportsHeroV2;
