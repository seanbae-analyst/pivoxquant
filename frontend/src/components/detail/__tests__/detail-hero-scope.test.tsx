import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { DetailHero, type DetailHeroProps } from "@/components/detail/DetailHero";

/**
 * FIX 2 regression — a 403 `ticker_not_in_user_scope` must surface an honest
 * "add to watchlist" CTA, NOT the misleading "timeout" load-failure note.
 * Timeouts / server errors keep the existing failure surface + retry.
 */

function baseProps(over: Partial<DetailHeroProps> = {}): DetailHeroProps {
  return {
    displayTicker: "AAPL",
    rawTicker: "AAPL",
    displayName: "Apple Inc.",
    summary: null,
    sectorLine: "Technology",
    industry: null,
    krw: false,
    mcap: null,
    signal: undefined,
    loadingSignal: false,
    signalError: false,
    signalScopeDenied: false,
    onRetrySignal: vi.fn(),
    signalRetrying: false,
    inWatchlist: false,
    onWatchlistToggle: vi.fn(),
    ...over,
  };
}

describe("DetailHero — scope-denied vs timeout", () => {
  it("renders the watchlist CTA (KO + EN) when scope-denied, not a timeout note", () => {
    render(<DetailHero {...baseProps({ signalScopeDenied: true })} />);

    expect(
      screen.getByText(/관심 목록에 추가하면 분석을 볼 수 있습니다/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Add this ticker to your watchlist to see analysis/i),
    ).toBeInTheDocument();
    // The misleading timeout copy must NOT appear in the scope case.
    expect(screen.queryByText(/timeout/i)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/시그널·가격 데이터를 불러오지 못했습니다/),
    ).not.toBeInTheDocument();
  });

  it("fires onWatchlistToggle when the CTA is clicked", () => {
    const onWatchlistToggle = vi.fn();
    render(
      <DetailHero
        {...baseProps({ signalScopeDenied: true, onWatchlistToggle })}
      />,
    );
    // CTA carries the unique KO+EN label; the header toggle is hidden in the
    // scope-denied state, so this resolves to exactly the CTA button.
    screen
      .getByRole("button", { name: /관심 목록에 추가 · Add to watchlist/i })
      .click();
    expect(onWatchlistToggle).toHaveBeenCalledTimes(1);
  });

  it("renders the load-failure note + retry on a generic signal error (timeout/500)", () => {
    render(
      <DetailHero {...baseProps({ signalError: true, signalScopeDenied: false })} />,
    );

    expect(
      screen.getByText(/시그널·가격 데이터를 불러오지 못했습니다/),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /다시 시도/ })).toBeInTheDocument();
    // No watchlist CTA on a generic error.
    expect(
      screen.queryByText(/Add this ticker to your watchlist/i),
    ).not.toBeInTheDocument();
  });
});

describe("DetailHero — KOSPI vs KOSDAQ exchange line", () => {
  it("shows KOSDAQ for a .KQ ticker (rawTicker, not the suffix-stripped displayTicker)", () => {
    render(
      <DetailHero
        {...baseProps({
          krw: true,
          displayTicker: "247540",
          rawTicker: "247540.KQ",
        })}
      />,
    );
    expect(screen.getByText("KRW · KOSDAQ")).toBeInTheDocument();
    expect(screen.queryByText("KRW · KOSPI")).not.toBeInTheDocument();
  });

  it("shows KOSPI for a .KS ticker", () => {
    render(
      <DetailHero
        {...baseProps({
          krw: true,
          displayTicker: "005930",
          rawTicker: "005930.KS",
        })}
      />,
    );
    expect(screen.getByText("KRW · KOSPI")).toBeInTheDocument();
  });
});
