"use client";

/**
 * <PortfolioHeroV2 />
 *
 * Editorial hero for /portfolio v2 (mockup §HERO).
 *
 * Visual rules:
 * - 80px top / 64px bottom padding, hairline-bottom only (no card border).
 * - H1 Playfair 500 / 48px / line-height 1.05 / track-tight.
 * - Bronze italic accent on the word "book."
 * - Two CTAs: bronze-filled "Add position" + bronze-outline "Reconcile".
 * - Eyebrow: "Book · Volume {weekIndex} · {weekday}".
 *
 * Legal: action vocabulary `Add` / `Reconcile` / `Save observation` only.
 * Never "Buy / Sell / Recommend / Advice".
 */

import * as React from "react";
import { PRICE_COLOR_HEX } from "@/lib/format";

interface PortfolioHeroV2Props {
  /** Total NAV in display currency (USD or KRW). May be undefined. */
  nav?: number;
  navCurrency?: "USD" | "KRW";
  /** Native-currency stock subtotals — US holdings in USD, KR holdings in KRW.
   *  When both are present the NAV is shown split ("USD X · KRW Y") instead of a
   *  single FX-unified USD figure (CEO 2026-05-24). */
  navUsd?: number;
  navKrw?: number;
  /** Number of recorded positions. Optional — em-dash when missing. */
  positionCount?: number;
  /** Cash bucket as percent of NAV (0..100). Optional — em-dash when missing. */
  cashPct?: number;
  /** ISO timestamp of last reconciliation / observation. Optional. */
  lastReconciledAt?: string | null;
  /** Whether at least one broker connection is wired. Drives CTA enabled state. */
  reconcileAvailable?: boolean;
  /** Click handler for the primary "Add position" CTA. */
  onAddPosition: () => void;
  /** Click handler for the secondary "Reconcile from broker" CTA. */
  onReconcile?: () => void;
  loading?: boolean;
  /** Today P&L in display currency. v1 KPI parity (additive). */
  todayPnl?: number;
  /** Today P&L percent. v1 KPI parity (additive). */
  todayPnlPct?: number;
  /** Unrealized P&L in display currency. v1 KPI parity (additive). */
  unrealized?: number;
  /** Realized YTD P&L in display currency. v1 KPI parity (additive). */
  realizedYtd?: number;
}

function weekIndexOf(d: Date): number {
  const yearStart = new Date(d.getFullYear(), 0, 1);
  const days = Math.floor((d.getTime() - yearStart.getTime()) / 86_400_000);
  return Math.min(52, Math.max(1, Math.ceil((days + yearStart.getDay() + 1) / 7)));
}

function weekdayOf(d: Date): string {
  return d.toLocaleDateString("en-US", { weekday: "long" });
}

// Wave 2 sweep (2026-05-19): NOT migrated to @/lib/format helpers.
// Divergences from lib/format.ts that would cause user-visible regression:
//   fmtMoney  — 0-decimal USD vs lib/fmtUsd 2-decimal under 1000
//   fmtPct    — toFixed(1) vs lib/fmtPct toFixed(2), AND no "+" prefix
//   fmtMoneySigned (below) — 0-decimal USD vs lib 2-decimal under 1000
// Hero card intentionally suppresses cents/decimals for editorial weight.
function fmtMoney(n: number | undefined, currency: "USD" | "KRW"): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  const dec = currency === "KRW" ? 0 : 0;
  const body = abs.toLocaleString(currency === "KRW" ? "ko-KR" : "en-US", {
    minimumFractionDigits: dec,
    maximumFractionDigits: dec,
  });
  return `${sign}${currency === "KRW" ? "KRW " : "USD "}${body}`;
}

function fmtPct(n: number | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  return `${n.toFixed(1)}%`;
}

/** Like fmtMoney but always emits an explicit +/− sign for non-zero values. */
function fmtMoneySigned(
  n: number | undefined,
  currency: "USD" | "KRW",
  loading?: boolean,
): string {
  if (loading) return "—";
  if (n == null || !Number.isFinite(n)) return "—";
  const abs = Math.abs(n);
  const sign = n > 0 ? "+" : n < 0 ? "−" : "";
  const dec = currency === "KRW" ? 0 : 0;
  const body = abs.toLocaleString(currency === "KRW" ? "ko-KR" : "en-US", {
    minimumFractionDigits: dec,
    maximumFractionDigits: dec,
  });
  return `${sign}${currency === "KRW" ? "KRW " : "USD "}${body}`;
}

function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "never";
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "never";
  const diff = Date.now() - t;
  const min = Math.floor(diff / 60_000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const days = Math.floor(hr / 24);
  return `${days}d ago`;
}

export function PortfolioHeroV2({
  nav,
  navCurrency = "USD",
  navUsd,
  navKrw,
  positionCount,
  cashPct,
  lastReconciledAt,
  reconcileAvailable = false,
  onAddPosition,
  onReconcile,
  loading,
  todayPnl,
  todayPnlPct,
  unrealized,
  realizedYtd,
}: PortfolioHeroV2Props) {
  const now = new Date();
  const eyebrow = `Book · Volume ${weekIndexOf(now)} · ${weekdayOf(now)}`;

  // Show native-currency subtotals separately rather than one FX-unified USD
  // figure (CEO 2026-05-24): KR holdings in KRW, US holdings in USD. Falls back to
  // the single display-currency nav when only one market is held (or the
  // backend hasn't supplied the split).
  const hasUs = typeof navUsd === "number" && navUsd > 0;
  const hasKr = typeof navKrw === "number" && navKrw > 0;
  const navText = loading
    ? "—"
    : hasUs && hasKr
      ? `${fmtMoney(navUsd, "USD")} · ${fmtMoney(navKrw, "KRW")}`
      : hasKr
        ? fmtMoney(navKrw, "KRW")
        : hasUs
          ? fmtMoney(navUsd, "USD")
          : fmtMoney(nav, navCurrency);
  const positionsText = loading
    ? "—"
    : positionCount != null
      ? `${positionCount}`
      : "—";
  const cashText = loading ? "—" : fmtPct(cashPct);
  const reconcileText = loading
    ? "—"
    : relativeTime(lastReconciledAt);

  return (
    <section
      className="pq-portfolio-hero-v2"
      style={{
        padding: "80px 0 64px",
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
          marginBottom: 28,
        }}
      >
        {eyebrow}
      </div>

      <h1
        className="font-display"
        style={{
          fontWeight: 500,
          fontSize: "var(--pq-text-h2-dash)",
          lineHeight: 1.05,
          letterSpacing: "var(--pq-track-tight, -0.02em)",
          color: "var(--pq-ivory)",
          maxWidth: 940,
          margin: "0 0 28px 0",
        }}
      >
        Your{" "}
        <span
          style={{
            fontStyle: "italic",
            color: "var(--pq-bronze)",
          }}
        >
          book.
        </span>
      </h1>

      <p
        className="font-serif"
        style={{
          fontSize: "var(--pq-text-h5)",
          lineHeight: 1.55,
          color: "rgba(245,240,232,0.82)",
          maxWidth: 720,
          margin: "0 0 32px 0",
        }}
      >
        {positionsText} positions{" "}
        <span style={{ fontStyle: "italic", color: "var(--pq-bronze)" }}>
          observed
        </span>
        {" · "}
        {navText} of capital
        {" · "}
        last{" "}
        <span style={{ fontStyle: "italic", color: "var(--pq-bronze)" }}>
          reconciled
        </span>{" "}
        {reconcileText}. Cash buffer at {cashText}.
      </p>

      {/* KPI deck — v1 parity (today P&L / unrealized / realized YTD).
          Renders only when at least one figure is present so v2 doesn't
          get a row of em-dashes during the initial load. */}
      {(todayPnl != null || unrealized != null || realizedYtd != null) && (
        <div
          aria-label="Portfolio KPI deck"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
            gap: 24,
            maxWidth: 720,
            marginBottom: 32,
            paddingTop: 4,
          }}
        >
          <HeroKpi
            label="Today"
            value={fmtMoneySigned(todayPnl, navCurrency, loading)}
            sub={
              todayPnlPct != null && Number.isFinite(todayPnlPct)
                ? `${todayPnlPct >= 0 ? "+" : ""}${todayPnlPct.toFixed(2)}%`
                : undefined
            }
            tone={
              todayPnl == null || todayPnl === 0
                ? "neutral"
                : todayPnl > 0
                  ? "positive"
                  : "negative"
            }
          />
          <HeroKpi
            label="Unrealized"
            value={fmtMoneySigned(unrealized, navCurrency, loading)}
            tone={
              unrealized == null || unrealized === 0
                ? "neutral"
                : unrealized > 0
                  ? "positive"
                  : "negative"
            }
          />
          <HeroKpi
            label="Realized YTD"
            value={fmtMoneySigned(realizedYtd, navCurrency, loading)}
            tone={
              realizedYtd == null || realizedYtd === 0
                ? "neutral"
                : realizedYtd > 0
                  ? "positive"
                  : "negative"
            }
          />
        </div>
      )}

      {/* CTAs */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          flexWrap: "wrap",
        }}
      >
        <button
          type="button"
          onClick={onAddPosition}
          className="pq-cta-bronze font-mono"
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
            border: "none",
            borderRadius: "var(--pq-radius-cta, 2px)",
            cursor: "pointer",
            transition: "background-color 200ms",
          }}
        >
          Add position →
        </button>

        <button
          type="button"
          onClick={onReconcile}
          disabled={!reconcileAvailable}
          className="pq-cta-outline font-mono"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 10,
            padding: "12px 22px",
            background: "transparent",
            color: reconcileAvailable
              ? "var(--pq-bronze)"
              : "rgba(245,240,232,0.55)",
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.2em",
            textTransform: "uppercase",
            border: `1px solid ${reconcileAvailable ? "var(--pq-bronze)" : "rgba(245,240,232,0.20)"}`,
            borderRadius: "var(--pq-radius-cta, 2px)",
            cursor: reconcileAvailable ? "pointer" : "not-allowed",
            transition: "border-color 200ms, color 200ms",
          }}
          aria-disabled={!reconcileAvailable}
          title={
            reconcileAvailable
              ? "Reconcile from connected broker"
              : "KIS broker 연결 필요 (Settings)"
          }
        >
          Reconcile from broker
        </button>
      </div>
    </section>
  );
}

/* ── HeroKpi — KPI deck cell (v1 parity) ─────────────────────────── */

function HeroKpi({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone: "positive" | "negative" | "neutral";
}) {
  // Color: bronze for neutral, semantic for positive/negative — paired
  // with text labels in the parent prose for accessibility. KR convention
  // (site-canonical PRICE_COLOR_HEX): gain → carmine #D18888, loss → indigo
  // #7AA0C8. The old local mapping inverted gain to bronze, diverging from
  // detail/watchlist; bronze stays the brand accent for the neutral case.
  const valueColor =
    tone === "positive"
      ? PRICE_COLOR_HEX.up
      : tone === "negative"
        ? PRICE_COLOR_HEX.down
        : "var(--pq-bronze)";

  return (
    <div
      style={{
        borderTop: "1px solid var(--pq-hairline-ink, rgba(245,240,232,0.10))",
        paddingTop: 12,
      }}
    >
      <div
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.22em",
          color: "var(--pq-bronze)",
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      <div
        className="font-mono tabular-nums"
        style={{
          fontSize: "var(--pq-text-h5)",
          letterSpacing: "-0.005em",
          color: valueColor,
          lineHeight: 1.2,
        }}
      >
        {value}
      </div>
      {sub ? (
        <div
          className="font-mono tabular-nums"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            color: "rgba(245,240,232,0.55)",
            marginTop: 2,
          }}
        >
          {sub}
        </div>
      ) : null}
    </div>
  );
}

export default PortfolioHeroV2;
