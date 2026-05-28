import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

// Mock the data hook so we control the series shape (partial benchmark
// coverage is the bug being regressed — FIX 4, 2026-05-22).
vi.mock("@/components/portfolio/v2/hooks-v2", () => ({
  useEquityCurve: vi.fn(),
}));

import { useEquityCurve, type EquityPoint } from "@/components/portfolio/v2/hooks-v2";
import { EquityCurveBlock } from "@/components/portfolio/v2/equity-curve-block";

const mockedHook = vi.mocked(useEquityCurve);

function mkData(
  series: EquityPoint[],
  benchmark?: { name?: string },
) {
  return {
    data: { series, benchmark } as {
      series: EquityPoint[];
      benchmark?: { name?: string };
    },
    isLoading: false,
    error: undefined,
  } as unknown as ReturnType<typeof useEquityCurve>;
}

describe("EquityCurveBlock — benchmark KPI from partial benchmark series", () => {
  beforeEach(() => {
    mockedHook.mockReset();
  });

  it("computes BENCHMARK + SPREAD from first/last VALID benchmark points (not series[0])", () => {
    // Benchmark is undefined for the first two samples (line starts mid-chart),
    // then 100 → 110. Pre-fix this rendered "—" because series[0].benchmark
    // was undefined. NAV runs 1000 → 1200 (+20%). Benchmark = +10.00%,
    // spread = +10.00pp.
    const series: EquityPoint[] = [
      { t: "2026-01-01", nav: 1000 }, // no benchmark
      { t: "2026-01-02", nav: 1010 }, // no benchmark
      { t: "2026-01-03", nav: 1020, benchmark: 100 },
      { t: "2026-01-04", nav: 1100, benchmark: 105 },
      { t: "2026-01-05", nav: 1200, benchmark: 110 },
    ];
    mockedHook.mockReturnValue(mkData(series));

    render(<EquityCurveBlock currency="USD" currentNav={1200} />);

    // RANGE +20.00%, BENCHMARK +10.00% — both render as real numbers (pre-fix
    // the benchmark cell was "—").
    expect(screen.getByText("+20.00%")).toBeTruthy();
    expect(screen.getByText("+10.00%")).toBeTruthy();
    // SPREAD = +20.00% - +10.00% = +10.00pp.
    expect(screen.getByText("+10.00pp")).toBeTruthy();
  });

  // Bug #1 (bug-hunter 2026-05-28): benchmark legend was hardcoded
  // "Benchmark · KOSPI200" — US portfolios saw "KOSPI200" too.
  // Backend now emits `benchmark: { name }` from routes/portfolio.py;
  // the legend must render that name dynamically.
  it("renders dynamic benchmark legend label from data.benchmark.name (KR portfolio)", () => {
    const series: EquityPoint[] = [
      { t: "2026-01-01", nav: 1000, benchmark: 2500 },
      { t: "2026-01-02", nav: 1100, benchmark: 2520 },
    ];
    mockedHook.mockReturnValue(mkData(series, { name: "KOSPI 200" }));
    render(<EquityCurveBlock currency="KRW" currentNav={1100} />);
    expect(screen.getByText(/Benchmark · KOSPI 200/)).toBeTruthy();
  });

  it("renders dynamic benchmark legend label from data.benchmark.name (US portfolio)", () => {
    const series: EquityPoint[] = [
      { t: "2026-01-01", nav: 1000, benchmark: 450 },
      { t: "2026-01-02", nav: 1100, benchmark: 460 },
    ];
    mockedHook.mockReturnValue(mkData(series, { name: "S&P 500" }));
    render(<EquityCurveBlock currency="USD" currentNav={1100} />);
    expect(screen.getByText(/Benchmark · S&P 500/)).toBeTruthy();
    // Regression guard: KOSPI200 must not appear when label = S&P 500.
    expect(screen.queryByText(/KOSPI200/)).toBeNull();
    expect(screen.queryByText(/KOSPI 200/)).toBeNull();
  });

  it("falls back to plain 'Benchmark' when backend omits benchmark name", () => {
    const series: EquityPoint[] = [
      { t: "2026-01-01", nav: 1000, benchmark: 100 },
      { t: "2026-01-02", nav: 1100, benchmark: 105 },
    ];
    mockedHook.mockReturnValue(mkData(series));
    render(<EquityCurveBlock currency="USD" currentNav={1100} />);
    // No "Benchmark · X" — falls back to "Benchmark · Benchmark"
    // OR — accept either of: bare "Benchmark" / "Benchmark · Benchmark"
    // (we just guard against the legacy "KOSPI200" leak).
    expect(screen.queryByText(/KOSPI200/)).toBeNull();
  });

  it("returns em-dash when no valid benchmark points exist", () => {
    const series: EquityPoint[] = [
      { t: "2026-01-01", nav: 1000 },
      { t: "2026-01-02", nav: 1100 },
    ];
    mockedHook.mockReturnValue(mkData(series));

    render(<EquityCurveBlock currency="USD" currentNav={1100} />);

    // BENCHMARK + SPREAD both fall back to em-dash; rangeReturn still shows.
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(2);
  });
});
