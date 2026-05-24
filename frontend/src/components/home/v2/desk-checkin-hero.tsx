"use client";

/**
 * <DeskCheckinHero /> — /home top (CEO 2026-05-24).
 *
 * Replaces the editorial "weekly memo / morning paper" hero, which read as a
 * newspaper that recited the market and never had real content (headline was
 * permanently null → "memo coming soon" placeholder). CEO disliked the paper
 * framing outright.
 *
 * New concept, aligned with "User as CFO" + the companion voice of the mood
 * nudge: a warm desk check-in. Not an article — a greeting + one honest,
 * data-grounded line about YOUR book (holdings count + today's biggest mover),
 * then a quiet link deeper. §101-safe: observation only, never buy/sell/target.
 */

import * as React from "react";
import Link from "next/link";
import { displayTicker, pctColor, fmtPct } from "@/lib/format";

interface HeroPosition {
  name?: string | null;
  ticker?: string | null;
  symbol?: string | null;
  change_pct?: number | null;
}

interface Props {
  displayName?: string;
  positions?: HeroPosition[];
  loading?: boolean;
  hasPositions?: boolean;
}

function greeting(hour: number): string {
  if (hour >= 5 && hour < 12) return "좋은 아침이에요";
  if (hour >= 12 && hour < 18) return "좋은 오후예요";
  return "편안한 저녁이에요";
}

function topMover(positions: HeroPosition[]): HeroPosition | null {
  let best: HeroPosition | null = null;
  let bestAbs = 0;
  for (const p of positions) {
    const c = p.change_pct;
    if (typeof c === "number" && Number.isFinite(c) && Math.abs(c) > bestAbs) {
      bestAbs = Math.abs(c);
      best = p;
    }
  }
  return best;
}

export function DeskCheckinHero({
  displayName,
  positions = [],
  loading = false,
  hasPositions = true,
}: Props) {
  const now = new Date();
  const who = displayName && displayName !== "Observer" ? `${displayName}님` : "";
  const headline = `${greeting(now.getHours())}${who ? `, ${who}` : ""}.`;

  const count = positions.length;
  const mover = topMover(positions);
  const moverName = mover ? displayTicker(mover.ticker ?? mover.symbol ?? "", mover.name) : null;

  return (
    <section
      style={{
        padding: "56px 0 40px",
        borderBottom: "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))",
        marginBottom: 40,
      }}
    >
      <div
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow, 10.5px)",
          letterSpacing: "0.22em",
          color: "var(--pq-bronze)",
          marginBottom: 20,
        }}
      >
        Your desk
      </div>

      <h1
        className="font-display"
        style={{
          fontWeight: 500,
          fontSize: "clamp(28px, 3.4vw, 40px)",
          lineHeight: 1.1,
          letterSpacing: "-0.02em",
          color: "var(--pq-ivory)",
          margin: "0 0 18px 0",
        }}
      >
        {headline}
      </h1>

      {/* Companion desk line — honest, data-grounded, §101-safe. */}
      {loading ? (
        <div style={{ height: 26, marginBottom: 36 }} aria-hidden />
      ) : !hasPositions ? (
        <p
          className="font-serif"
          style={{
            fontSize: "var(--pq-text-h5)",
            lineHeight: 1.55,
            color: "rgba(245,240,232,0.82)",
            maxWidth: 640,
            margin: "0 0 32px 0",
            wordBreak: "keep-all",
          }}
        >
          첫 종목을 장부에 올리면, 데스크가 당신의 포트폴리오를 지켜보기 시작해요.
        </p>
      ) : (
        <p
          className="font-serif"
          style={{
            fontSize: "var(--pq-text-h5)",
            lineHeight: 1.55,
            color: "rgba(245,240,232,0.82)",
            maxWidth: 640,
            margin: "0 0 32px 0",
            wordBreak: "keep-all",
          }}
        >
          {count}개 종목을 지켜보고 있어요.
          {mover && moverName ? (
            <>
              {" "}오늘 가장 큰 움직임은{" "}
              <span style={{ color: "var(--pq-ivory)" }}>{moverName}</span>
              {", "}
              <span
                className="font-mono"
                style={{ color: pctColor(mover.change_pct ?? null), fontVariantNumeric: "tabular-nums" }}
              >
                {fmtPct(mover.change_pct ?? null)}
              </span>
              {" 였어요."}
            </>
          ) : null}
        </p>
      )}

      <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        {!loading && !hasPositions ? (
          <Link
            href="/portfolio"
            className="font-mono"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              padding: "12px 22px",
              background: "var(--pq-bronze)",
              color: "var(--pq-ink, #050505)",
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.2em",
              textTransform: "uppercase",
              borderRadius: 2,
              textDecoration: "none",
            }}
          >
            첫 종목 추가 →
          </Link>
        ) : (
          <Link
            href="/risk"
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "rgba(245, 240, 232, 0.6)",
              borderBottom: "1px solid rgba(184,149,106,0.35)",
              paddingBottom: 2,
              textDecoration: "none",
            }}
          >
            리스크 · 집중도 보기 →
          </Link>
        )}
      </div>
    </section>
  );
}

export default DeskCheckinHero;
