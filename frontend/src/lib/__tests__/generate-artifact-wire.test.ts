/**
 * generateArtifact() wire contract (2026-06-11 fix):
 * the unified backend endpoint (routes/artifacts.py:api_artifacts_generate)
 * reads optional kwargs from `params` — `params.ticker`, never a top-level
 * `ticker`. The pre-fix client sent `{type, ticker}` top-level, which the
 * backend silently ignored → 400 EARNINGS_TICKER_REQUIRED on every
 * Earnings Pre-Brief request. The dead `topic` field is gone entirely.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockApiFetch = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    apiFetch: (...args: unknown[]) => mockApiFetch(...args),
  };
});

import { generateArtifact } from "@/lib/hooks";
import { API } from "@/lib/endpoints";

beforeEach(() => {
  mockApiFetch.mockReset();
  mockApiFetch.mockResolvedValue({
    status: "ready",
    type: "risk_board",
    artifact_id: 1,
    data: {},
    reason: null,
    message: null,
    redirect: null,
  });
});

function sentBody(): Record<string, unknown> {
  const [, init] = mockApiFetch.mock.calls[0] as [string, { body: string }];
  return JSON.parse(init.body);
}

describe("generateArtifact wire shape", () => {
  it("nests ticker under params.ticker (not top-level)", async () => {
    await generateArtifact({ type: "earnings_prebrief", ticker: "AAPL" });
    expect(mockApiFetch).toHaveBeenCalledWith(
      API.artifacts.generate,
      expect.objectContaining({ method: "POST" }),
    );
    expect(sentBody()).toEqual({
      type: "earnings_prebrief",
      params: { ticker: "AAPL" },
    });
  });

  it("sends a bare {type} when there are no kwargs", async () => {
    await generateArtifact({ type: "risk_board" });
    expect(sentBody()).toEqual({ type: "risk_board" });
  });
});
