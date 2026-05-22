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

function mkData(series: EquityPoint[]) {
  return {
    data: { series } as { series: EquityPoint[] },
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
