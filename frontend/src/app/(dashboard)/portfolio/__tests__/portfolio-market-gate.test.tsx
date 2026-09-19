/**
 * /portfolio — vendor market-data display gate, both positions of the switch.
 *
 * The bug this file exists to prevent: with prices withheld, a money slot
 * that still renders prints "USD 0" / "KRW 0" / "—" and the reader takes it
 * for a real valuation. Same class as the false-NAV flash fixed in bcd45e02.
 * So the OFF cases assert absence of the market columns AND absence of any
 * zero-money string anywhere in the document — not just that a label changed.
 *
 * The ON cases assert the screen is what it was before the flag existed.
 *
 * Heavyweight children that fetch on mount (CFO bar, capital card, recent
 * transactions, rolling window, weekly pulse, the modals) are stubbed; the
 * three components under test — hero, ledger, sector donut — are real.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";

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

// Fetching children — stubbed to keep the test about the gate.
vi.mock("@/components/dashboard/living-cfo-status", () => ({
  LivingCFOStatusBar: () => null,
}));
vi.mock("@/components/dashboard/weekly-pulse", () => ({
  WeeklyPulseCard: () => null,
}));
vi.mock("@/components/dashboard/rolling-window", () => ({
  RollingWindowWidget: () => null,
}));
vi.mock("@/components/settings/v2/capital-card-v2", () => ({
  CapitalCardV2: () => null,
}));
vi.mock("@/components/portfolio/v2/recent-transactions-block", () => ({
  RecentTransactionsBlock: () => null,
}));
vi.mock("@/components/portfolio/v2/add-position-modal-v2", () => ({
  AddPositionModalV2: () => null,
}));
vi.mock("@/components/portfolio/v2/trade-modal-v2", () => ({
  TradeModalV2: () => null,
}));
// Stubbed so its presence/absence is a single unambiguous assertion.
vi.mock("@/components/portfolio/v2/equity-curve-block", () => ({
  EquityCurveBlock: () => <div data-testid="equity-curve-stub" />,
}));

import {
  usePortfolioPositions,
  usePortfolioSummary,
  useFxRate,
} from "@/lib/hooks";
import { LocaleProvider } from "@/lib/locale";
import PortfolioPageV2 from "@/app/(dashboard)/portfolio/page";

const mockedPositions = vi.mocked(usePortfolioPositions);
const mockedSummary = vi.mocked(usePortfolioSummary);
const mockedFx = vi.mocked(useFxRate);

/** One US row and one KR row, so the cross-currency paths are exercised. */
const PRICED_ROWS: BackendPositionRow[] = [
  {
    id: 1,
    ticker: "AAPL",
    name: "Apple",
    shares: 10,
    avgCost: 100,
    current: 150,
    sector: "Technology",
    currency: "USD",
  },
  {
    id: 2,
    ticker: "005930",
    name: "삼성전자",
    shares: 20,
    avgCost: 60_000,
    current: 70_000,
    sector: "Technology",
    currency: "KRW",
  },
];

/** What the backend sends with MARKET_DATA_DISPLAY_ENABLED off: no price. */
const UNPRICED_ROWS: BackendPositionRow[] = PRICED_ROWS.map((r) => ({
  ...r,
  current: undefined,
  current_price: undefined,
}));

const PRICED_SUMMARY = {
  totalNav: 2500,
  navUsd: 1500,
  navKrw: 1_400_000,
  todayPnl: 12,
  todayPnlPct: 0.5,
  unrealized: 500,
  realizedYtd: 42,
  fxRate: 1400,
  cashPct: 28.5,
  observed_at: "2026-09-19T00:00:00Z",
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const swrLike = (data: any) =>
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ({ data, isLoading: false, error: undefined }) as any;

function renderPage() {
  return render(
    <LocaleProvider>
      <PortfolioPageV2 />
    </LocaleProvider>,
  );
}

/**
 * The core invariant. `—` is deliberately NOT banned outright: it is a valid
 * "not recorded yet" mark in non-money cells. What must never appear is a
 * currency-prefixed zero, which reads as a valuation of nothing.
 */
function expectNoFalseZeroMoney(container: HTMLElement) {
  const text = container.textContent ?? "";
  expect(text).not.toMatch(/USD\s*0(\D|$)/);
  expect(text).not.toMatch(/KRW\s*0(\D|$)/);
  expect(text).not.toMatch(/\$\s*0(\D|$)/);
}

describe("/portfolio — market-data display OFF (shipped default)", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "0");
    mockedPositions.mockReturnValue(
      swrLike({ positions: UNPRICED_ROWS, market_data_display: false }),
    );
    mockedSummary.mockReturnValue(swrLike({ market_data_display: false }));
    mockedFx.mockReturnValue({ rate: 1400, isStale: false });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.clearAllMocks();
  });

  it("drops the LAST / P/L % / MKT VALUE columns", async () => {
    renderPage();
    await act(async () => {});

    expect(screen.queryByRole("columnheader", { name: /Last/i })).toBeNull();
    expect(screen.queryByRole("columnheader", { name: /P\/L %/i })).toBeNull();
    expect(
      screen.queryByRole("columnheader", { name: /Mkt value/i }),
    ).toBeNull();

    // The two cost-basis columns stay.
    expect(
      screen.getByRole("columnheader", { name: /Avg cost/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: /Weight · at cost/i }),
    ).toBeInTheDocument();
  });

  it("drops the TODAY and UNREALIZED KPIs and keeps REALIZED YTD", async () => {
    mockedSummary.mockReturnValue(
      swrLike({ market_data_display: false, realizedYtd: 42, realizedUsd: 42 }),
    );
    renderPage();
    await act(async () => {});

    expect(screen.queryByText("Today")).toBeNull();
    expect(screen.queryByText("Unrealized")).toBeNull();
    expect(screen.getByText("Realized YTD")).toBeInTheDocument();
  });

  it("hides the equity curve block entirely", async () => {
    renderPage();
    await act(async () => {});
    expect(screen.queryByTestId("equity-curve-stub")).toBeNull();
  });

  it("states the cost basis on the hero, the ledger and the sector mix", async () => {
    renderPage();
    await act(async () => {});

    expect(
      screen.getByTestId("portfolio-cost-basis-note"),
    ).toHaveTextContent("평균매입가 기준 (시장가 아님)");
    expect(screen.getByTestId("positions-cost-basis-note")).toBeInTheDocument();
    expect(screen.getByTestId("sector-cost-basis-note")).toBeInTheDocument();
  });

  it("shows the acquisition amount, split by native currency", async () => {
    renderPage();
    await act(async () => {});
    // 10 × 100 USD and 20 × 60,000 KRW — the user's own numbers.
    expect(screen.getByText(/USD 1,000/)).toBeInTheDocument();
    expect(screen.getByText(/KRW 1,200,000/)).toBeInTheDocument();
  });

  it("prints no currency-prefixed zero anywhere", async () => {
    const { container } = renderPage();
    await act(async () => {});
    expectNoFalseZeroMoney(container);
  });

  it("carries the exchangerate-api attribution", async () => {
    renderPage();
    await act(async () => {});
    const link = screen.getByRole("link", {
      name: "Rates By Exchange Rate API",
    });
    expect(link).toHaveAttribute("href", "https://www.exchangerate-api.com");
  });

  it("stays off when the frontend flag is on but the backend says false", async () => {
    // This is the case that would print "USD 0": `toPosition` coerces the
    // backend's null `current` to 0 via `?? 0`.
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "1");
    const { container } = renderPage();
    await act(async () => {});

    expect(screen.queryByRole("columnheader", { name: /Mkt value/i })).toBeNull();
    expect(screen.queryByTestId("equity-curve-stub")).toBeNull();
    expectNoFalseZeroMoney(container);
  });
});

describe("/portfolio — market-data display ON (unchanged from before the flag)", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "1");
    mockedPositions.mockReturnValue(swrLike({ positions: PRICED_ROWS }));
    mockedSummary.mockReturnValue(swrLike(PRICED_SUMMARY));
    mockedFx.mockReturnValue({ rate: 1400, isStale: false });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.clearAllMocks();
  });

  it("renders all eight ledger columns", async () => {
    renderPage();
    await act(async () => {});

    for (const name of [
      /Name/i,
      /Shares/i,
      /Avg cost/i,
      /Last/i,
      /P\/L %/i,
      /Mkt value/i,
      /Sector/i,
    ]) {
      expect(screen.getByRole("columnheader", { name })).toBeInTheDocument();
    }
    // Plain "Weight", not the at-cost variant.
    expect(
      screen.getByRole("columnheader", { name: /^Weight/i }),
    ).toHaveTextContent(/Weight/);
    expect(
      screen.queryByRole("columnheader", { name: /Weight · at cost/i }),
    ).toBeNull();
  });

  it("renders the three KPIs and the equity curve", async () => {
    renderPage();
    await act(async () => {});

    expect(screen.getByText("Today")).toBeInTheDocument();
    expect(screen.getByText("Unrealized")).toBeInTheDocument();
    expect(screen.getByText("Realized YTD")).toBeInTheDocument();
    expect(screen.getByTestId("equity-curve-stub")).toBeInTheDocument();
  });

  it("shows the market NAV split and no cost-basis notes", async () => {
    renderPage();
    await act(async () => {});

    // The hero prints the split; the ledger's MKT VALUE cells repeat the
    // same figures, hence getAllByText.
    expect(screen.getAllByText(/USD 1,500/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/KRW 1,400,000/).length).toBeGreaterThan(0);
    expect(screen.queryByTestId("portfolio-cost-basis-note")).toBeNull();
    expect(screen.queryByTestId("positions-cost-basis-note")).toBeNull();
    expect(screen.queryByTestId("sector-cost-basis-note")).toBeNull();
  });
});
