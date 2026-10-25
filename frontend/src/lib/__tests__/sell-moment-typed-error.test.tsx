/**
 * useSellMomentForTyped — an error for the new input never keeps the last
 * input's answer on screen (2026-10-21 버그헌팅). keepPreviousData holds the
 * old answer while the new one loads; on an error it used to hold it for
 * good, so shares=7 showed the hold and cost computed for shares=5.
 */
import { it, expect, vi, afterEach } from "vitest";
import * as React from "react";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import { SWRConfig } from "swr";

import { useSellMomentForTyped } from "@/lib/hooks";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function Probe({ shares }: { shares: number }) {
  const { data } = useSellMomentForTyped({ ticker: "AAPL", shares, price: 10 });
  return <div data-testid="o">{data ? `held=${data.held_days}` : "none"}</div>;
}

it("shows nothing after an error for the new input", async () => {
  const fetchMock = vi.fn(async (url: string) => {
    if (url.includes("shares=5&")) {
      return {
        ok: true,
        json: async () => ({ ok: true, ticker: "AAPL", words: [], held_days: 34, vs_cost_pct: 1, matched_shares: 5 }),
      };
    }
    return { ok: false, status: 429, statusText: "Too Many Requests", json: async () => ({}) };
  });
  vi.stubGlobal("fetch", fetchMock);
  const cache = new Map();
  const wrap = (shares: number) => (
    <SWRConfig value={{ provider: () => cache }}>
      <Probe shares={shares} />
    </SWRConfig>
  );
  const { rerender } = render(wrap(5));
  await waitFor(() => expect(screen.getByTestId("o").textContent).toBe("held=34"));
  rerender(wrap(7));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  await waitFor(() => expect(screen.getByTestId("o").textContent).toBe("none"));
});
