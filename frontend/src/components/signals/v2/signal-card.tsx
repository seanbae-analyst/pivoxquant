"use client";

/**
 * <SignalCard /> — single observation row in the v2 timeline.
 *
 * Source: design-mockups/signals-v2/SPEC.md §4 (SignalRow).
 * Grid: 1fr 280px 120px (desktop), stacks on mobile.
 *
 *   Left:  name-main Playfair 22px ivory
 *          ticker-sub mono 11px dim ("AAPL · NASDAQ")
 *          rationale Source Serif 4 14px ivory-soft (2-3 sentences)
 *   Mid:   label pill + "strength 0.91" + 3px bronze bar + price line
 *   Right: timestamp "09:42 KST" mono 11px + "3h ago" subline
 *
 * Whole row is <a href="/detail/${ticker}">. aria-label per SPEC.
 *
 * Legal: POSITIVE / NEGATIVE / NEUTRAL only. "observed" framing.
 */

import * as React from "react";
import Link from "next/link";
import type { SignalEntry, SignalLabel } from "@/lib/types";
import { fmtPct, normalizeTicker } from "@/lib/format";

interface Props {
  entry: SignalEntry;
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
  // CEO directive 2026-05-13: signal 페이지 전체 한국어화. Display
  // labels in Korean ("긍정/부정/중립") instead of English. Legal
  // vocabulary (POSITIVE/NEGATIVE/NEUTRAL) is preserved internally;
  // only the user-facing text is localised. Bilingual aria-label
  // below carries both forms for screen readers + audit.
  if (label === "POSITIVE")
    return { fg: "var(--pq-positive, #b8956a)", bg: "rgba(184,149,106,0.08)", display: "긍정" };
  if (label === "NEGATIVE")
    return { fg: "var(--pq-negative, #d18888)", bg: "rgba(209,136,136,0.08)", display: "부정" };
  return { fg: "rgba(245,240,232,0.55)", bg: "var(--pq-ivory-line-faint)", display: "중립" };
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

// fmtPct migrated to @/lib/format (2026-05-19 Wave 2 sweep).
// lib/format.ts `fmtPct` is byte-identical (same `n >= 0 ? "+"` sign rule
// + 2-decimal toFixed + "—" sentinel).

function fmtKstClock(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "—";
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    return `${hh}:${mm} KST`;
  } catch {
    return "—";
  }
}

// CEO directive 2026-05-13: 시간 표시도 한국어 ("3시간 전" / "방금").
function fmtAgo(iso: string | null | undefined): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    const diff = Date.now() - d.getTime();
    if (diff < 0) return "방금";
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "방금";
    if (mins < 60) return `${mins}분 전`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}시간 전`;
    const days = Math.floor(hrs / 24);
    return `${days}일 전`;
  } catch {
    return "";
  }
}

export function SignalCard({ entry, resolveName }: Props) {
  const name = entry.name || resolveName(entry.ticker);
  const label = labelOf(entry);
  const tone = labelTone(label);
  const strength = strengthOf(entry);
  const pct = entry.change_pct ?? null;
  const pctTone =
    pct == null
      ? "rgba(245,240,232,0.55)"
      : pct >= 0
        ? "var(--pq-positive, #b8956a)"
        : "var(--pq-negative, #d18888)";

  const observed = entry.observed_at ?? null;

  // B-10 fix (2026-05-10): wrap only the title in <Link> so vertical
  // scroll gestures on the card body are not mis-interpreted as clicks.
  // Previously the entire <article> was the link target, which made it
  // hard to scroll on touch devices without accidentally navigating to
  // /detail/{ticker}. The title link still carries the full aria-label
  // and announces the row context to assistive tech.
  const detailHref = `/detail/${entry.ticker}${entry.id != null ? `?signal=${entry.id}` : ""}`;

  return (
    <article
      className="signal-row"
      style={{
        display: "grid",
        gridTemplateColumns: "minmax(0, 1fr) 280px 120px",
        gap: 28,
        padding: "22px 0",
        borderBottom: "1px solid var(--pq-hairline, var(--pq-ivory-line))",
        transition: "background 200ms cubic-bezier(0.16, 1, 0.3, 1), border-color 200ms",
        // CEO 2026-05-13: align all 3 columns to the top so the right
        // timestamp doesn't visually overlap the rationale below the
        // strength bar on narrow desktop widths.
        alignItems: "start",
      }}
    >
        {/* LEFT — name + ticker + rationale */}
        <div style={{ minWidth: 0 }}>
          <Link
            href={detailHref}
            prefetch={false}
            aria-label={`${name} · ${entry.ticker} · ${tone.display} · 강도 ${strength.toFixed(2)} · ${fmtKstClock(observed)}`}
            // Bug #11 sweep: same hover-tooltip exposure as the mover
            // card. Single-line ellipsis is preserved (the rationale
            // sits below and any wrap would push it into the next
            // row), but `title` keeps the full name reachable without
            // resizing the viewport.
            title={name}
            className="font-display signal-title-link"
            style={{
              fontSize: "var(--pq-text-quote)",
              fontWeight: 500,
              letterSpacing: "-0.01em",
              color: "var(--pq-ivory, #F5F0E8)",
              // CEO bug "symbol 아래에 폰트가 걸린다" (2026-05-13):
              // Playfair Display has no KR glyph coverage; KR titles
              // (e.g. "삼성전자") fall through to a system serif whose
              // descenders extend past Playfair's metrics. 1.15 was too
              // tight — descenders clipped onto the ticker sub-line.
              // 1.3 gives KR ink + Latin ink consistent breathing room.
              lineHeight: 1.3,
              textDecoration: "none",
              display: "block",
              // truncate long Latin names (e.g. "Berkshire Hathaway Inc.
              // Class B") instead of letting them wrap and shove the
              // ticker sub-line further down into rationale territory.
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              maxWidth: "100%",
            }}
          >
            {name}
          </Link>
          <div
            className="font-mono"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.14em",
              color: "rgba(245,240,232,0.45)",
              // CEO bug "폰트가 겹친다" — was 4px which let descenders
              // overlap. 8px clears any KR descender at 24px Playfair.
              marginTop: 8,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {normalizeTicker(entry.ticker)}
            {entry.exchange ? ` · ${entry.exchange}` : ""}
          </div>
          {entry.rationale && (
            <p
              className="font-serif"
              style={{
                fontSize: "var(--pq-text-body)",
                lineHeight: 1.55,
                color: "rgba(245,240,232,0.78)",
                margin: "10px 0 0 0",
                // CEO 2026-05-20 "한 문장이 부분 줄바꿈": KR prose must
                // break at word (어절) boundaries, not mid-word. keep-all
                // honours KR spacing; anywhere is the escape hatch for a
                // single token longer than the column.
                wordBreak: "keep-all",
                overflowWrap: "anywhere",
              }}
            >
              {entry.rationale}
            </p>
          )}
        </div>

        {/* MIDDLE — label + strength bar + price */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
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
            <span
              className="font-mono"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.04em",
                color: "rgba(245,240,232,0.55)",
                fontVariantNumeric: "tabular-nums",
              }}
            >
              강도 {strength.toFixed(2)}
            </span>
            {entry.is_stale && (
              <span
                className="font-mono uppercase"
                title="신선도 TTL 경과된 캐시 관측"
                style={{
                  fontSize: "var(--pq-text-eyebrow-sm)",
                  letterSpacing: "0.18em",
                  padding: "2px 6px",
                  border: "1px solid rgba(245,240,232,0.20)",
                  borderRadius: "var(--pq-radius-cta, 2px)",
                  color: "rgba(245,240,232,0.45)",
                  background: "var(--pq-ivory-line-faint)",
                }}
              >
                오래됨
              </span>
            )}
          </div>
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
          <div
            className="font-mono"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              fontVariantNumeric: "tabular-nums",
              display: "flex",
              gap: 10,
              alignItems: "baseline",
            }}
          >
            <span style={{ color: "rgba(245,240,232,0.78)" }}>{fmtPrice(entry)}</span>
            <span style={{ color: pctTone }}>{fmtPct(pct)}</span>
          </div>
        </div>

        {/* RIGHT — timestamp */}
        <div style={{ textAlign: "right" }}>
          <div
            className="font-mono"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              fontVariantNumeric: "tabular-nums",
              color: "rgba(245,240,232,0.55)",
            }}
          >
            {fmtKstClock(observed)}
          </div>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.06em",
              color: "rgba(245,240,232,0.55)",
              marginTop: 4,
            }}
          >
            {fmtAgo(observed)}
          </div>
        </div>
      <style jsx>{`
        :global(.signal-row:hover) {
          background: rgba(184, 149, 106, 0.025);
          border-bottom-color: var(--pq-bronze, #b8956a) !important;
        }
        :global(.signal-title-link:hover) {
          color: var(--pq-bronze, #b8956a) !important;
        }
        @media (max-width: 767px) {
          :global(.signal-row) {
            grid-template-columns: 1fr !important;
            gap: 12px !important;
          }
        }
      `}</style>
    </article>
  );
}
