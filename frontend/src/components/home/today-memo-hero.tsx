"use client";

/**
 * <TodayMemoHero /> — full-bleed CFO Hero strip on /home.
 *
 * Concept: "User as CFO". The agent ships an Artifact (memo / brag card /
 * earnings pre-brief) — not a chat. This hero anchors the day's headline
 * in serif, lays out the brief body, and offers four Artifact CTA chips.
 *
 * Data source: legacy MorningBrief shape (deprecated 2026-04-29) the /home
 * page used to fetch. We reuse the value via props
 * to avoid duplicating the SWR hook + re-rendering twice.
 *
 * Empty / loading / error states intentionally refuse mock fallbacks.
 *
 * Legal: no recommendation/advice/protect/grow language. POSITIVE/
 * NEGATIVE/NEUTRAL labels only.
 */

import Link from "next/link";
import { WEEKLY_MEMO_WHEN_SHORT } from "@/lib/cfo/memo-schedule";

interface TodayMemoHeroProps {
  /** Headline / first sentence (brief.insight or brief.summary). null → empty state. */
  headline: string | null;
  /** Optional secondary body (brief.summary when insight was used as headline). */
  body?: string | null;
  /** YYYY-MM-DD; rendered in the eyebrow. Falls back to today (KST). */
  isoDate?: string;
  /** True while SWR is still resolving. */
  loading?: boolean;
  /** Display name (e.g. "Sean"). */
  displayName?: string;
}

function todayKstIso(): string {
  const now = new Date();
  // KST is UTC+9; use Intl to get YYYY-MM-DD reliably.
  const fmt = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  return fmt.format(now);
}

export function TodayMemoHero({
  headline,
  body,
  isoDate,
  loading = false,
  displayName,
}: TodayMemoHeroProps) {
  const date = isoDate || todayKstIso();
  const eyebrowName = displayName ? ` · ${displayName}` : "";

  return (
    <section
      aria-label="Today's CFO memo"
      style={{
        background: "rgba(184, 149, 106, 0.04)",
        border: "1px solid rgba(184, 149, 106, 0.18)",
        padding: "22px 24px",
        marginBottom: 14,
        display: "grid",
        gridTemplateColumns: "minmax(0, 7fr) minmax(0, 3fr)",
        gap: 28,
        minHeight: 220,
      }}
      className="pq-today-memo-hero"
    >
      {/* ── Left 70% — Eyebrow + Headline + Body + CTA chips ── */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 14,
          minWidth: 0,
        }}
      >
        {/* Eyebrow */}
        <div
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.28em",
            color: "var(--pq-bronze)",
          }}
        >
          Today · {date}
          {eyebrowName}
        </div>

        {/* Headline (serif) */}
        {loading ? (
          <div
            aria-hidden="true"
            style={{
              height: 56,
              background:
                "linear-gradient(90deg, rgba(245,240,232,0.05) 0%, rgba(245,240,232,0.10) 50%, rgba(245,240,232,0.05) 100%)",
              backgroundSize: "200% 100%",
              animation: "pq-skeleton-shimmer 1.4s ease-in-out infinite",
              borderRadius: 2,
            }}
          />
        ) : headline ? (
          <h1
            className="font-serif"
            style={{
              fontSize: "clamp(22px, 2.4vw, 30px)",
              lineHeight: 1.22,
              color: "var(--pq-ivory)",
              margin: 0,
              fontWeight: 500,
              letterSpacing: "-0.005em",
            }}
          >
            {headline}
          </h1>
        ) : (
          <h1
            className="font-serif"
            style={{
              fontSize: "clamp(20px, 2vw, 26px)",
              lineHeight: 1.3,
              color: "rgba(245, 240, 232, 0.55)",
              margin: 0,
              fontWeight: 400,
              fontStyle: "italic",
            }}
          >
            Today&rsquo;s brief is being prepared. Check back at 09:00 KST.
          </h1>
        )}

        {/* Body */}
        {loading ? (
          <div
            aria-hidden="true"
            style={{
              height: 32,
              background:
                "linear-gradient(90deg, var(--pq-ivory-line-faint) 0%, var(--pq-ivory-line) 50%, var(--pq-ivory-line-faint) 100%)",
              backgroundSize: "200% 100%",
              animation: "pq-skeleton-shimmer 1.4s ease-in-out infinite",
              borderRadius: 2,
            }}
          />
        ) : body && body !== headline ? (
          <p
            style={{
              fontSize: "var(--pq-text-body)",
              lineHeight: 1.65,
              color: "rgba(245, 240, 232, 0.72)",
              margin: 0,
              maxWidth: "62ch",
            }}
          >
            {body}
          </p>
        ) : null}

        {/* CTA chips */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 8,
            marginTop: "auto",
            paddingTop: 6,
          }}
        >
          <Link
            href="/reports"
            className="pq-ink-btn-bronze"
            style={{ height: 32, padding: "0 14px", fontSize: "var(--pq-text-eyebrow)" }}
          >
            Open the desk
          </Link>
          <Link
            href="/reports?type=weekly_memo"
            className="pq-ink-btn-ghost"
            style={{ height: 32, padding: "0 12px", fontSize: "var(--pq-text-eyebrow)" }}
          >
            Weekly Memo (Sun)
          </Link>
          <Link
            href="/reports?type=brag_card"
            className="pq-ink-btn-ghost"
            style={{ height: 32, padding: "0 12px", fontSize: "var(--pq-text-eyebrow)" }}
          >
            Last Brag Card
          </Link>
          <Link
            href="/reports?type=earnings_prebrief"
            className="pq-ink-btn-ghost"
            style={{ height: 32, padding: "0 12px", fontSize: "var(--pq-text-eyebrow)" }}
          >
            Earnings Pre-Brief
          </Link>
        </div>
      </div>

      {/* ── Right 30% — Meta strip ── */}
      <aside
        style={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          gap: 12,
          minWidth: 0,
          borderLeft: "0.5px solid rgba(245, 240, 232, 0.10)",
          paddingLeft: 24,
        }}
        className="pq-today-memo-hero__aside"
      >
        <div>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-kicker)",
              letterSpacing: "0.24em",
              color: "rgba(245, 240, 232, 0.45)",
              marginBottom: 6,
            }}
          >
            Cadence
          </div>
          <div
            className="font-serif"
            style={{
              fontSize: "var(--pq-text-body)",
              lineHeight: 1.5,
              color: "rgba(245, 240, 232, 0.78)",
            }}
          >
            Daily brief lands at <span style={{ color: "var(--pq-bronze)" }}>09:00 KST</span>.
            <br />
            Weekly memo every <span style={{ color: "var(--pq-bronze)" }}>{WEEKLY_MEMO_WHEN_SHORT}</span>.
          </div>
        </div>

        <div>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-kicker)",
              letterSpacing: "0.24em",
              color: "rgba(245, 240, 232, 0.45)",
              marginBottom: 6,
            }}
          >
            Agent
          </div>
          <div
            className="font-serif"
            style={{
              fontSize: "var(--pq-text-body)",
              lineHeight: 1.5,
              color: "rgba(245, 240, 232, 0.78)",
            }}
          >
            Your AI Assistant authors Artifacts on your behalf.
            Observations only &mdash; no investment guidance.
          </div>
        </div>
      </aside>

      {/* Mobile fallback — collapse to single column */}
      <style jsx>{`
        @media (max-width: 768px) {
          .pq-today-memo-hero {
            grid-template-columns: minmax(0, 1fr) !important;
            padding: 18px 16px !important;
            min-height: 0 !important;
          }
          .pq-today-memo-hero__aside {
            border-left: 0 !important;
            border-top: 0.5px solid rgba(245, 240, 232, 0.1) !important;
            padding-left: 0 !important;
            padding-top: 16px !important;
            flex-direction: row !important;
          }
          .pq-today-memo-hero__aside > div {
            flex: 1 1 0;
            min-width: 0;
          }
        }
        @keyframes pq-skeleton-shimmer {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
      `}</style>
    </section>
  );
}

export default TodayMemoHero;
