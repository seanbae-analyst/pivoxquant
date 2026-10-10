/**
 * /portfolio on a phone (CEO 2026-10-09 — "화면 넘어가는식으로"; 2026-10-10 —
 * "너무 웹사이트 같음 앱처럼"): a large-title summary that stays on screen above
 * three swipeable pages (보유 · 현황 · 최근 활동).
 *
 * What must hold on the phone layout, both positions of the vendor gate:
 *   - every section is still there (holdings, hero, seed capital, sectors,
 *     recent activity) — rearranged, not dropped;
 *   - the actions still work (종목 추가, 정리 기록 per holding);
 *   - gate OFF: cost basis only, labelled, no market column, no curve, no
 *     currency-prefixed zero; USD and KRW are never summed into one figure;
 *   - desktop (and SSR) keep the original column — no pager.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, within, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { BackendPositionRow } from "@/components/portfolio/types";

vi.mock("swr", () => ({ __esModule: true, default: vi.fn(), mutate: vi.fn() }));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

vi.mock("@/lib/hooks", () => ({
  usePortfolioPositions: vi.fn(),
  usePortfolioSummary: vi.fn(),
  useFxRate: vi.fn(),
  fetcher: vi.fn(),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { available_capital: 1000, available_capital_krw: 0 },
    refresh: vi.fn(),
  }),
}));

vi.mock("@/components/dashboard/living-cfo-status", () => ({
  LivingCFOStatusBar: () => <div data-testid="cfo-bar-stub" />,
}));
vi.mock("@/components/dashboard/weekly-pulse-prompt", () => ({
  WeeklyPulsePrompt: () => null,
}));
vi.mock("@/components/settings/v2/capital-card-v2", () => ({
  CapitalCardV2: () => <div data-testid="capital-card-stub" />,
}));
vi.mock("@/components/portfolio/v2/recent-transactions-block", () => ({
  RecentTransactionsBlock: () => <div data-testid="recent-tx-stub" />,
}));
vi.mock("@/components/portfolio/v2/add-position-modal-v2", () => ({
  AddPositionModalV2: ({ open }: { open: boolean }) =>
    open ? <div data-testid="add-modal-open" /> : null,
}));
vi.mock("@/components/portfolio/v2/trade-modal-v2", () => ({
  TradeModalV2: ({ open, action }: { open: boolean; action: string }) =>
    open ? <div data-testid={`trade-modal-${action}`} /> : null,
}));
vi.mock("@/components/portfolio/v2/equity-curve-block", () => ({
  EquityCurveBlock: () => <div data-testid="equity-curve-stub" />,
}));

import { usePortfolioPositions, usePortfolioSummary, useFxRate } from "@/lib/hooks";
import { LocaleProvider } from "@/lib/locale";
import PortfolioPageV2 from "@/app/(dashboard)/portfolio/page";

const mockedPositions = vi.mocked(usePortfolioPositions);
const mockedSummary = vi.mocked(usePortfolioSummary);
const mockedFx = vi.mocked(useFxRate);

const PRICED_ROWS: BackendPositionRow[] = [
  { id: 1, ticker: "AAPL", name: "Apple", shares: 10, avgCost: 100, current: 150, sector: "Technology", currency: "USD" },
  { id: 2, ticker: "005930", name: "삼성전자", shares: 20, avgCost: 60_000, current: 70_000, sector: "Technology", currency: "KRW" },
];
const UNPRICED_ROWS: BackendPositionRow[] = PRICED_ROWS.map((r) => ({
  ...r,
  current: undefined,
  current_price: undefined,
}));

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const swrLike = (data: any) => ({ data, isLoading: false, error: undefined }) as any;

function setPhone(on: boolean) {
  window.matchMedia = ((q: string) => ({
    matches: on && q === "(max-width: 767px)",
    media: q,
    addEventListener: () => {},
    removeEventListener: () => {},
  })) as unknown as typeof window.matchMedia;
}

const originalMatchMedia = window.matchMedia;

async function renderPage() {
  const out = render(
    <LocaleProvider>
      <PortfolioPageV2 />
    </LocaleProvider>,
  );
  await act(async () => {});
  return out;
}

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.clearAllMocks();
  window.matchMedia = originalMatchMedia;
});

describe("/portfolio phone pager — vendor gate OFF (shipped default)", () => {
  beforeEach(() => {
    setPhone(true);
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "0");
    mockedPositions.mockReturnValue(swrLike({ positions: UNPRICED_ROWS, market_data_display: false }));
    mockedSummary.mockReturnValue(swrLike({ market_data_display: false, realizedYtd: 42, realizedUsd: 42 }));
    mockedFx.mockReturnValue({ rate: 1400, isStale: false });
  });

  it("lays the sections out as three tabbed pages (2026-10-10)", async () => {
    await renderPage();
    const tabs = within(screen.getByRole("tablist", { name: "포트폴리오 화면" })).getAllByRole("tab");
    expect(tabs.map((t) => t.textContent)).toEqual(["보유", "현황", "최근 활동"]);
    expect(tabs[0]).toHaveAttribute("aria-selected", "true");
    // The tab strip already says where you are — no carousel dots under it.
    expect(screen.queryByTestId("phone-pager-dots")).toBeNull();

    expect(within(screen.getByTestId("phone-page-holdings")).getAllByTestId("position-card")).toHaveLength(2);
    const overview = screen.getByTestId("phone-page-overview");
    expect(within(overview).getByText("올해 실현 손익")).toBeInTheDocument();
    // Sectors moved onto 현황 as a composition strip, under its own label.
    expect(within(overview).getByText("섹터 구성")).toBeInTheDocument();
    expect(within(overview).getByTestId("sector-plain")).toBeInTheDocument();
    expect(within(screen.getByTestId("phone-page-activity")).getByTestId("recent-tx-stub")).toBeInTheDocument();
    // FX attribution + foot signature end the 현황 page instead of trailing
    // under the pager like a web footer.
    expect(within(overview).getByText(/투자자문이 아닙니다/)).toBeInTheDocument();
    // Desktop-only chrome stays off the phone tree; the editorial hero
    // paragraph is not on the phone either.
    expect(screen.queryByTestId("cfo-bar-stub")).toBeNull();
    expect(document.querySelector(".pq-portfolio-hero-v2")).toBeNull();
  });

  it("seed capital is a row on 현황 that opens the same form in a sheet", async () => {
    await renderPage();
    const overview = screen.getByTestId("phone-page-overview");
    const row = within(overview).getByTestId("portfolio-capital-open");
    // useAuth mock: available_capital 1000 USD, no KRW → one line, no "KRW 0".
    expect(row).toHaveTextContent("USD 1,000");
    expect(row.textContent).not.toMatch(/KRW/);
    expect(screen.queryByTestId("capital-card-stub")).toBeNull();
    await userEvent.click(row);
    expect(screen.getByTestId("capital-card-stub")).toBeInTheDocument();
  });

  it("summary rows show no market-price row with the gate off", async () => {
    await renderPage();
    const overview = screen.getByTestId("phone-page-overview");
    expect(within(overview).queryByText("오늘")).toBeNull();
    expect(within(overview).queryByText("평가 손익")).toBeNull();
    expect(within(overview).queryByText("마지막 관측")).toBeNull();
    expect(within(overview).getByText("+USD 42")).toBeInTheDocument();
  });

  it("keeps a cost-basis summary on screen, one figure per currency", async () => {
    const { container } = await renderPage();
    const summary = screen.getByTestId("portfolio-phone-summary");
    expect(summary).toHaveTextContent("보유 2종목 · 취득가 기준");
    // 10 × 100 USD and 20 × 60,000 KRW, side by side — never added up.
    expect(screen.getByTestId("portfolio-phone-summary-amount").textContent).toBe("USD 1,000 · KRW 1,200,000");

    expect(screen.getByTestId("portfolio-cost-basis-note")).toBeInTheDocument();
    expect(screen.getByTestId("positions-cost-basis-note")).toBeInTheDocument();
    expect(screen.getByTestId("sector-cost-basis-note")).toBeInTheDocument();
    expect(screen.queryByTestId("equity-curve-stub")).toBeNull();

    const text = container.textContent ?? "";
    expect(text).not.toMatch(/USD\s*0(\D|$)/);
    expect(text).not.toMatch(/KRW\s*0(\D|$)/);
    expect(text).not.toMatch(/USD 150\b/); // the vendor quote in the fixture
  });

  it("keeps the actions: 종목 추가 from the summary, 정리 기록 per holding", async () => {
    await renderPage();
    await userEvent.click(screen.getByTestId("portfolio-phone-add"));
    expect(screen.getByTestId("add-modal-open")).toBeInTheDocument();

    // 2026-10-09: tapping a holding opens its action sheet (same actions).
    await userEvent.click(screen.getAllByTestId("position-card-open")[0]);
    await userEvent.click(screen.getByRole("button", { name: "AAPL 정리 기록" }));
    expect(screen.getByTestId("trade-modal-sell")).toBeInTheDocument();
  });

  it("taps a tab to move to its page", async () => {
    await renderPage();
    const tab = screen.getByRole("tab", { name: "최근 활동" });
    await userEvent.click(tab);
    expect(tab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("phone-page-activity")).not.toHaveAttribute("inert");
    expect(screen.getByTestId("phone-page-holdings")).toHaveAttribute("inert");
  });
});

describe("/portfolio phone pager — vendor gate ON", () => {
  beforeEach(() => {
    setPhone(true);
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "1");
    mockedPositions.mockReturnValue(swrLike({ positions: PRICED_ROWS }));
    mockedSummary.mockReturnValue(
      swrLike({ totalNav: 2500, navUsd: 1500, navKrw: 1_400_000, fxRate: 1400, cashPct: 28.5, realizedYtd: 42 }),
    );
    mockedFx.mockReturnValue({ rate: 1400, isStale: false });
  });

  it("shows the native NAV split and puts the curve on the 현황 page", async () => {
    await renderPage();
    expect(screen.getByTestId("portfolio-phone-summary")).toHaveTextContent("보유 2종목 · 평가액");
    expect(screen.getByTestId("portfolio-phone-summary-amount").textContent).toBe("USD 1,500 · KRW 1,400,000");
    const overview = screen.getByTestId("phone-page-overview");
    expect(within(overview).getByTestId("equity-curve-stub")).toBeInTheDocument();
    expect(within(overview).getByText("자산 흐름")).toBeInTheDocument();
    expect(within(overview).getByText("마지막 관측")).toBeInTheDocument();
    expect(within(overview).getByText("현금 비중")).toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-cost-basis-note")).toBeNull();
  });
});

describe("/portfolio on desktop", () => {
  it("keeps the single column — no pager, CFO bar present", async () => {
    setPhone(false);
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "0");
    mockedPositions.mockReturnValue(swrLike({ positions: UNPRICED_ROWS, market_data_display: false }));
    mockedSummary.mockReturnValue(swrLike({ market_data_display: false }));
    mockedFx.mockReturnValue({ rate: 1400, isStale: false });
    await renderPage();
    expect(screen.queryByTestId("phone-pager")).toBeNull();
    expect(screen.queryByRole("tablist", { name: "포트폴리오 화면" })).toBeNull();
    expect(screen.getByTestId("cfo-bar-stub")).toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
  });
});
