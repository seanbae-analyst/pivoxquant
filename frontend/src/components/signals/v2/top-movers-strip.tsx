"use client";

/**
 * <TopMoversStrip /> — top-5 horizontal mover cards.
 *
 * Source: design-mockups/signals-v2/SPEC.md §3.
 * 5-card grid (lg+), horizontal snap-x carousel below 1024px.
 * Each card: name-main (Playfair) → ticker-sub (mono dim) →
 * label pill → strength bar → rationale → footer (mono pct + price).
 *
 * Legal: POSITIVE / NEGATIVE / NEUTRAL only. "observed" framing.
 */

import * as React from "react";
import Link from "next/link";
import type { SignalEntry, SignalLabel } from "@/lib/types";

interface Props {
  entries: SignalEntry[];
  resolveName: (ticker: string) => string;
}

function strengthOf(s: SignalEntry): number {
  if (typeof s.strength === "number") return Math.max(0, Math.min(1, s.strength));
  if (typeof s.score === "number") return Math.max(0, Math.min(1, s.score / 100));
  return 0;
}

function labelOf(s: SignalEntry): SignalLabel {
  const v = (s.label ?? s.signal ?? "").toString().toUpperCase();
  if (v === "POSITIVE") return "POSITIVE";
  if (v === "NEGATIVE") return "NEGATIVE";
  return "NEUTRAL";
}

function labelTone(label: SignalLabel) {
  // CEO directive 2026-05-13: 전체 한국어화. 동일 패턴 → signal-card.tsx.
  if (label === "POSITIVE")
    return { fg: "var(--pq-positive, #dc2626)", bg: "rgba(220,38,38,0.08)", display: "긍정" };
  if (label === "NEGATIVE")
    return { fg: "var(--pq-negative, #2563eb)", bg: "rgba(37,99,235,0.08)", display: "부정" };
  return { fg: "rgba(245,240,232,0.55)", bg: "var(--pq-ivory-line-faint)", display: "중립" };
}

// CEO directive 2026-05-13: 한국 종목 우선 표시.
function isKr(s: SignalEntry): boolean {
  if (s.is_korean === true) return true;
  if (s.currency === "KRW") return true;
  const t = (s.ticker ?? "").toUpperCase();
  return t.endsWith(".KS") || t.endsWith(".KQ") || t.endsWith(".KRX");
}

function fmtPrice(s: SignalEntry): string {
  if (s.price == null) return "—";
  if (s.currency === "KRW" || s.is_korean) {
    return `₩${Math.round(s.price).toLocaleString("ko-KR")}`;
  }
  return `$${s.price.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function fmtPct(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const sign = n >= 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

export function TopMoversStrip({ entries, resolveName }: Props) {
  const top5 = React.useMemo(() => {
    // CEO 2026-05-13: 1차 정렬 한국 종목 우선, 2차 정렬 강도 내림차순.
    const sorted = [...entries].sort((a, b) => {
      const aKr = isKr(a);
      const bKr = isKr(b);
      if (aKr !== bKr) return aKr ? -1 : 1;
      return strengthOf(b) - strengthOf(a);
    });
    return sorted.slice(0, 5);
  }, [entries]);

  if (top5.length === 0) return null;

  return (
    <section style={{ marginBottom: 56 }} aria-label="강도 상위 5개 관측">
      <div
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.22em",
          color: "var(--pq-bronze, #B8956A)",
          marginBottom: 8,
        }}
      >
        강도 상위 · 한국 종목 우선
      </div>
      <h2
        className="font-display"
        style={{
          fontWeight: 500,
          fontSize: "clamp(26px, 3vw, 40px)",
          letterSpacing: "-0.02em",
          color: "var(--pq-ivory, #F5F0E8)",
          // CEO bug "폰트가 겹친다": Playfair 26-40px 헤딩이 1.0
          // 라인-height (브라우저 기본)였음. KR 글리프 descender
          // 확보를 위해 1.2로 명시.
          lineHeight: 1.2,
          margin: "0 0 22px 0",
        }}
      >
        오늘의 큰 관측 다섯.
      </h2>

      <div
        className="movers-rail"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(5, minmax(0, 1fr))",
          gap: 14,
        }}
      >
        {top5.map((s) => {
          const label = labelOf(s);
          const tone = labelTone(label);
          const strength = strengthOf(s);
          const name = s.name || resolveName(s.ticker);
          const pct = s.change_pct ?? null;
          const pctTone =
            pct == null
              ? "rgba(245,240,232,0.55)"
              : pct >= 0
                ? "var(--pq-positive, #dc2626)"
                : "var(--pq-negative, #2563eb)";

          // B-10 fix (2026-05-10): only the title is a <Link>. Carousel
          // scroll gestures on the card body no longer trigger navigation.
          return (
            <article
              key={`${s.ticker}-${s.id ?? ""}`}
              className="mover-card"
              style={{
                border: "1px solid var(--pq-hairline, var(--pq-ivory-line))",
                borderRadius: "var(--pq-radius-card, 4px)",
                padding: 16,
                background: "transparent",
                transition: "border-color 200ms cubic-bezier(0.16, 1, 0.3, 1)",
                height: "100%",
                display: "flex",
                flexDirection: "column",
                gap: 10,
              }}
            >
                {/* name-main (Playfair) — 종목명 main pattern */}
                <Link
                  href={`/detail/${s.ticker}`}
                  prefetch={false}
                  aria-label={`${name} · ${tone.display} · 강도 ${strength.toFixed(2)}`}
                  className="font-display mover-title-link"
                  style={{
                    fontSize: "var(--pq-text-h5)",
                    fontWeight: 500,
                    color: "var(--pq-ivory, #F5F0E8)",
                    // CEO bug "symbol 아래에 폰트가 걸린다" — 1.2가 KR
                    // 글리프 descender를 cover 못 함. 1.35로 늘려서
                    // 아래 ticker-sub 라인과 시각적 충돌 제거.
                    lineHeight: 1.35,
                    letterSpacing: "-0.005em",
                    textDecoration: "none",
                    // block + ellipsis: 긴 한국어/영어 종목명이 카드
                    // bounds를 깨고 흘러나오지 않도록.
                    display: "block",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    maxWidth: "100%",
                  }}
                >
                  {name}
                </Link>

                {/* ticker-sub (mono, dim) */}
                <div
                  className="font-mono"
                  style={{
                    fontSize: "var(--pq-text-eyebrow)",
                    letterSpacing: "0.14em",
                    color: "rgba(245,240,232,0.45)",
                    // 카드의 gap: 10 + ticker 본인 margin = 충분한 여백.
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {s.ticker}
                  {s.exchange ? ` · ${s.exchange}` : ""}
                </div>

                {/* label pill */}
                <div>
                  <span
                    className="font-mono uppercase"
                    style={{
                      fontSize: "var(--pq-text-eyebrow)",
                      letterSpacing: "0.2em",
                      padding: "3px 8px",
                      border: `1px solid ${tone.fg}`,
                      borderRadius: "var(--pq-radius-cta, 2px)",
                      background: tone.bg,
                      color: tone.fg,
                    }}
                  >
                    {tone.display}
                  </span>
                </div>

                {/* strength bar */}
                <div
                  aria-hidden
                  style={{
                    height: 3,
                    width: "100%",
                    background: "var(--pq-ivory-line-soft)",
                    borderRadius: 2,
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      height: "100%",
                      width: `${(strength * 100).toFixed(1)}%`,
                      background:
                        "linear-gradient(90deg, var(--pq-bronze-deep, #6F5636), var(--pq-bronze, #B8956A))",
                    }}
                  />
                </div>

                {/* rationale */}
                {s.rationale && (
                  <p
                    className="font-serif"
                    style={{
                      fontSize: "var(--pq-text-body)",
                      lineHeight: 1.5,
                      color: "rgba(245,240,232,0.70)",
                      margin: 0,
                      display: "-webkit-box",
                      WebkitLineClamp: 3,
                      WebkitBoxOrient: "vertical",
                      overflow: "hidden",
                    }}
                  >
                    {s.rationale}
                  </p>
                )}

                {/* footer: pct + price */}
                <div
                  style={{
                    marginTop: "auto",
                    display: "flex",
                    alignItems: "baseline",
                    gap: 8,
                    paddingTop: 6,
                  }}
                >
                  <span
                    className="font-mono"
                    style={{
                      fontSize: "var(--pq-text-eyebrow)",
                      fontVariantNumeric: "tabular-nums",
                      color: pctTone,
                    }}
                  >
                    {fmtPct(pct)}
                  </span>
                  <span
                    className="font-mono"
                    style={{
                      fontSize: "var(--pq-text-eyebrow)",
                      fontVariantNumeric: "tabular-nums",
                      color: "rgba(245,240,232,0.55)",
                    }}
                  >
                    {fmtPrice(s)}
                  </span>
                </div>
            </article>
          );
        })}
      </div>

      <style jsx>{`
        :global(.mover-card:hover) {
          border-color: var(--pq-bronze, #b8956a) !important;
        }
        :global(.mover-title-link:hover) {
          color: var(--pq-bronze, #b8956a) !important;
        }
        @media (max-width: 1279px) {
          :global(.movers-rail) {
            grid-auto-flow: column !important;
            grid-auto-columns: minmax(220px, 1fr) !important;
            grid-template-columns: none !important;
            overflow-x: auto;
            scroll-snap-type: x mandatory;
            padding-bottom: 6px;
          }
          :global(.movers-rail > article) {
            scroll-snap-align: start;
          }
        }
      `}</style>
    </section>
  );
}
