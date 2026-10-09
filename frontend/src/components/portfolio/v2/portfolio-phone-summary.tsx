"use client";

/**
 * <PortfolioPhoneSummary /> — the two lines that stay on screen above the
 * phone /portfolio pages (CEO 2026-10-09, swipe layout).
 *
 *   보유 3종목 · 취득가 기준                 [ + 종목 추가 ]
 *   USD 1,000 · KRW 1,200,000
 *
 * Same amounts the hero sentence prints, drawn the same way:
 *   - vendor-display gate OFF (shipped default) → the user's cost basis,
 *     labelled "취득가 기준". No vendor price is read.
 *   - gate ON → the native-currency NAV subtotals.
 * USD and KRW are never added together: each currency keeps its own figure.
 * A slot with nothing true to print is dropped, never shown as "USD 0".
 */

import * as React from "react";
import { fmtMoneyPlain } from "@/lib/format";

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
  onAddPosition: () => void;
}

const positive = (v: number | undefined): v is number =>
  typeof v === "number" && Number.isFinite(v) && v > 0;

/** ["USD X", "KRW Y"] — one figure per currency, or null when none is real. */
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
  if (positive(usd)) parts.push(fmtMoneyPlain(usd, "USD", 0));
  if (positive(krw)) parts.push(fmtMoneyPlain(krw, "KRW", 0));
  if (parts.length > 0) return parts;
  if (marketDataDisplay && positive(nav)) return [fmtMoneyPlain(nav, navCurrency, 0)];
  return null;
}

export function PortfolioPhoneSummary(props: PortfolioPhoneSummaryProps) {
  const { marketDataDisplay, positionCount, loading, onAddPosition } = props;
  const amounts = loading ? null : summaryAmounts(props);
  const empty = !loading && positionCount === 0;
  const basis = marketDataDisplay ? "평가액" : "취득가 기준";

  return (
    <div
      className="flex items-center justify-between gap-3 pb-3"
      data-testid="portfolio-phone-summary"
    >
      <div className="min-w-0">
        <div className="font-mono text-[12px] tracking-[0.02em] text-[var(--pq-bronze)]">
          {loading ? "보유 —" : `보유 ${positionCount}종목`}
          {!empty && !loading ? ` · ${basis}` : null}
        </div>
        {/* No line at all when there is no true amount (e.g. holdings
            recorded without an average cost) — never a zero money slot. */}
        {loading || empty || amounts ? (
          <div
            className="mt-1 font-mono text-[16px] leading-[1.35] tabular-nums text-[var(--pq-ivory)]"
            data-testid="portfolio-phone-summary-amount"
          >
            {loading ? (
              "—"
            ) : empty ? (
              <span className="font-serif text-[15px] text-[var(--pq-ivory-dim)]">
                아직 기록된 종목이 없습니다
              </span>
            ) : (
              // Each currency is its own unbreakable run: a narrow phone wraps
              // between USD and KRW, never inside a number.
              amounts?.map((a, i) => (
                <span key={a} className="whitespace-nowrap">
                  {i > 0 ? <span className="text-[var(--pq-ivory-dim)]">{" · "}</span> : null}
                  {a}
                </span>
              ))
            )}
          </div>
        ) : null}
      </div>
      <button
        type="button"
        onClick={onAddPosition}
        className="pq-cta-bronze flex min-h-[40px] shrink-0 items-center rounded-[var(--pq-radius-cta,2px)] bg-[var(--pq-bronze)] px-3 text-[13px] text-[var(--pq-ink)]"
        data-testid="portfolio-phone-add"
      >
        + 종목 추가
      </button>
    </div>
  );
}

export default PortfolioPhoneSummary;
