"use client";

/**
 * <PortfolioPhoneSummary /> — the large title that stays on screen above the
 * phone /portfolio pages.
 *
 * 2026-10-10 (CEO "너무 웹사이트 같음 앱처럼"): was a bronze mono eyebrow over
 * one 16px line, beside a boxed button — page chrome, not a balance. Now it
 * reads like a finance app's account header:
 *
 *   보유 3종목 · 취득가 기준                     [ + 종목 추가 ]
 *   USD 1,000
 *   KRW 1,200,000
 *
 * and, once the current page is scrolled (`collapsed`, driven by
 * <PhonePager />), it shrinks to one line — "USD 1,000 · KRW 1,200,000" — the
 * way a native large-title bar folds into the navigation bar.
 *
 * Same amounts the hero sentence prints, drawn the same way:
 *   - vendor-display gate OFF (shipped default) → the user's cost basis,
 *     labelled "취득가 기준". No vendor price is read.
 *   - gate ON → the native-currency NAV subtotals.
 * USD and KRW are never added together: each currency keeps its own figure,
 * each on its own line. A slot with nothing true to print is dropped, never
 * shown as "USD 0".
 *
 * 2026-10-11 (CEO "너무 숫자만 … 있어보이게"): the figures are set the way a
 * Korean finance app sets a balance — won first, 만/억 units ("2,665만원",
 * "$34,830"), proportional sans digits instead of the terminal mono. Under
 * them, when the book holds both currencies and an FX rate is known, one
 * meter shows the 국내(KRW) / 해외(USD) split — bronze fill on the
 * bronze-deep track (dataviz meter form; ΔE 22 normal / 21.7 protan, track
 * below 3:1 so both shares are printed beside it). The split converts only to
 * compare shares; the two amounts above are still never summed.
 */

import * as React from "react";
import { Plus } from "lucide-react";
import { useReducedMotion } from "motion/react";
import { fmtMoneyKo } from "@/lib/format";
import { PQ_DUR_FAST, PQ_EASE } from "@/lib/motion";

interface PortfolioPhoneSummaryProps {
  marketDataDisplay: boolean;
  positionCount: number;
  loading?: boolean;
  costUsd?: number;
  costKrw?: number;
  navUsd?: number;
  navKrw?: number;
  /** Single display-currency NAV (FX-converted server-side). Gate ON only. */
  nav?: number;
  navCurrency?: "USD" | "KRW";
  /** USD→KRW, for the 국내/해외 split only. Absent → no split is drawn. */
  fxRate?: number | null;
  onAddPosition: () => void;
  /** The current page is scrolled — fold the title into one line. */
  collapsed?: boolean;
}

const positive = (v: number | undefined): v is number =>
  typeof v === "number" && Number.isFinite(v) && v > 0;

const EASE_CSS = `cubic-bezier(${PQ_EASE.join(", ")})`;

/** ["2,665만원", "$34,830"] — one figure per currency (won first), or null when none is real. */
export function summaryAmounts({
  marketDataDisplay,
  costUsd,
  costKrw,
  navUsd,
  navKrw,
  nav,
  navCurrency = "USD",
}: Pick<
  PortfolioPhoneSummaryProps,
  "marketDataDisplay" | "costUsd" | "costKrw" | "navUsd" | "navKrw" | "nav" | "navCurrency"
>): string[] | null {
  const usd = marketDataDisplay ? navUsd : costUsd;
  const krw = marketDataDisplay ? navKrw : costKrw;
  const parts: string[] = [];
  if (positive(krw)) parts.push(fmtMoneyKo(krw, "KRW", { compact: true }));
  if (positive(usd)) parts.push(fmtMoneyKo(usd, "USD", { compact: true }));
  if (parts.length > 0) return parts;
  if (marketDataDisplay && positive(nav)) return [fmtMoneyKo(nav, navCurrency, { compact: true })];
  return null;
}

/**
 * 국내(KRW) share of the book in percent — or null unless both currencies
 * hold something and the FX rate is real (a one-currency book is 100/0 and
 * needs no meter; a missing rate is never guessed).
 */
export function domesticShare({
  marketDataDisplay,
  costUsd,
  costKrw,
  navUsd,
  navKrw,
  fxRate,
}: Pick<
  PortfolioPhoneSummaryProps,
  "marketDataDisplay" | "costUsd" | "costKrw" | "navUsd" | "navKrw" | "fxRate"
>): number | null {
  const usd = marketDataDisplay ? navUsd : costUsd;
  const krw = marketDataDisplay ? navKrw : costKrw;
  if (!positive(usd) || !positive(krw) || !positive(fxRate ?? undefined)) return null;
  const krwInUsd = krw / (fxRate as number);
  return (krwInUsd / (krwInUsd + usd)) * 100;
}

export function PortfolioPhoneSummary(props: PortfolioPhoneSummaryProps) {
  const { marketDataDisplay, positionCount, loading, onAddPosition, collapsed = false } = props;
  const reduce = useReducedMotion();
  const amounts = loading ? null : summaryAmounts(props);
  const share = loading ? null : domesticShare(props);
  const domestic = share == null ? 0 : Math.round(share);
  const empty = !loading && positionCount === 0;
  const basis = marketDataDisplay ? "평가액" : "취득가 기준";
  const fold = reduce
    ? "none"
    : `font-size ${PQ_DUR_FAST}s ${EASE_CSS}, margin ${PQ_DUR_FAST}s ${EASE_CSS}`;

  return (
    <div
      className="pq-pf-summary pb-3"
      data-collapsed={collapsed ? "true" : undefined}
      data-testid="portfolio-phone-summary"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0 truncate text-pq-body-sm tracking-[0.01em] text-[var(--pq-ivory-dim)]">
          {loading ? "보유 —" : `보유 ${positionCount}종목`}
          {!empty && !loading ? ` · ${basis}` : null}
        </div>
        <button
          type="button"
          onClick={onAddPosition}
          className="pq-cta-bronze flex min-h-[36px] shrink-0 items-center gap-1 rounded-sm bg-[var(--pq-bronze)] pl-2.5 pr-3 text-pq-button font-medium text-[var(--pq-ink)] transition-opacity active:opacity-80"
          data-testid="portfolio-phone-add"
        >
          <Plus aria-hidden className="h-4 w-4" strokeWidth={2} />
          종목 추가
        </button>
      </div>

      {/* No amount at all when there is no true one (holdings recorded
          without an average cost) — never a zero money slot. */}
      {loading ? (
        <div className="mt-2 flex flex-col gap-2" role="status" aria-label="불러오는 중">
          <span className="pq-skeleton-dark block h-7 w-40" />
          {!collapsed && <span className="pq-skeleton-dark block h-7 w-52" />}
        </div>
      ) : empty ? (
        <div
          className="mt-1.5 text-pq-lead text-[var(--pq-ivory-mid)]"
          data-testid="portfolio-phone-summary-amount"
        >
          아직 기록된 종목이 없습니다
        </div>
      ) : amounts ? (
        <div
          className="pq-pf-summary-amount font-semibold text-[var(--pq-ivory)]"
          style={{ transition: fold }}
          data-testid="portfolio-phone-summary-amount"
        >
          {/* Expanded: one currency per line. Collapsed: one line, joined by
              " · ". The separator is always in the text so the line reads
              the same to a screen reader either way. */}
          {amounts.map((a, i) => (
            <span key={a} className="pq-pf-summary-figure">
              {i > 0 ? <span className="pq-pf-summary-sep text-[var(--pq-ivory-dim)]">{" · "}</span> : null}
              {a}
            </span>
          ))}
        </div>
      ) : null}

      {/* 국내 / 해외 — one ratio, so a meter, not a pie. Labels carry both
          shares in text tokens; the swatches carry identity. */}
      {share != null && !collapsed ? (
        <div
          className="mt-4"
          role="img"
          aria-label={`국내 ${domestic}% · 해외 ${100 - domestic}%`}
          data-testid="portfolio-phone-split"
        >
          <div aria-hidden className="flex h-1.5 w-full gap-[2px]">
            <span
              className="block h-full rounded-l-[4px]"
              style={{ width: `${share}%`, background: "var(--pq-bronze)" }}
            />
            <span
              className="block h-full flex-1 rounded-r-[4px]"
              style={{ background: "var(--pq-bronze-deep)" }}
            />
          </div>
          <div aria-hidden className="mt-2 flex justify-between text-pq-caption text-[var(--pq-ivory-dim)]">
            <span className="inline-flex items-center gap-1.5">
              <span className="block h-2 w-2 rounded-[2px]" style={{ background: "var(--pq-bronze)" }} />
              국내 {domestic}%
            </span>
            <span className="inline-flex items-center gap-1.5">
              해외 {100 - domestic}%
              <span className="block h-2 w-2 rounded-[2px]" style={{ background: "var(--pq-bronze-deep)" }} />
            </span>
          </div>
        </div>
      ) : null}

      <style jsx>{`
        .pq-pf-summary-amount {
          margin-top: 6px;
          font-size: 34px;
          line-height: 1.18;
          letter-spacing: -0.02em;
        }
        .pq-pf-summary-amount :global(.pq-pf-summary-figure) {
          display: block;
          white-space: nowrap;
        }
        .pq-pf-summary-amount :global(.pq-pf-summary-sep) {
          display: none;
        }
        .pq-pf-summary[data-collapsed="true"] .pq-pf-summary-amount {
          margin-top: 2px;
          font-size: 17px;
          line-height: 1.35;
          letter-spacing: -0.01em;
        }
        .pq-pf-summary[data-collapsed="true"] .pq-pf-summary-amount :global(.pq-pf-summary-figure) {
          display: inline;
        }
        .pq-pf-summary[data-collapsed="true"] .pq-pf-summary-amount :global(.pq-pf-summary-sep) {
          display: inline;
        }
      `}</style>
    </div>
  );
}

export default PortfolioPhoneSummary;
