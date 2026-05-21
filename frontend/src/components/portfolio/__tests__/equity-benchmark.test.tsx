import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as React from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { SWRConfig } from "swr";
import { useEquityCurve } from "@/components/portfolio/v2/hooks-v2";

/**
 * FIX 1 regression — the equity-curve mapper must preserve the per-point
 * `benchmark` the backend adds (routes/portfolio.py `point["benchmark"]`).
 * Before the fix the mapper dropped it (`{ t: p.date, nav: p.value }`), so the
 * benchmark polyline + "vs benchmark" KPI in equity-curve-block always showed
 * "—" even though the data was present in the response.
 */

// Fresh SWR cache per test so the deduped fetcher actually runs.
function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      {children}
    </SWRConfig>
  );
}

describe("useEquityCurve — benchmark preservation", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("keeps benchmark on each mapped point when the backend supplies it", async () => {
    const payload = {
      data: [
        { date: "2026-05-01", value: 10000, benchmark: 9800 },
        { date: "2026-05-02", value: 10120, benchmark: 9850 },
        { date: "2026-05-03", value: 10250, benchmark: 9900 },
      ],
      benchmark: { name: "KOSPI200" },
    };
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => payload,
    });

    const { result } = renderHook(() => useEquityCurve("6mo"), { wrapper });

    await waitFor(() => expect(result.current.data?.series.length).toBe(3));

    const series = result.current.data!.series;
    expect(series[0]).toEqual({ t: "2026-05-01", nav: 10000, benchmark: 9800 });
    expect(series[2].benchmark).toBe(9900);
    // Every point retained its benchmark — no drop.
    expect(series.every((p) => typeof p.benchmark === "number")).toBe(true);
  });

  it("omits benchmark cleanly when the backend does not supply it", async () => {
    const payload = {
      data: [
        { date: "2026-05-01", value: 10000 },
        { date: "2026-05-02", value: 10120 },
      ],
    };
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => payload,
    });

    const { result } = renderHook(() => useEquityCurve("6mo"), { wrapper });

    await waitFor(() => expect(result.current.data?.series.length).toBe(2));

    const series = result.current.data!.series;
    expect(series[0]).toEqual({ t: "2026-05-01", nav: 10000 });
    expect("benchmark" in series[0]).toBe(false);
  });
});
