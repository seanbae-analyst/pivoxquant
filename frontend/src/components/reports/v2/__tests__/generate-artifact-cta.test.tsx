/**
 * <GenerateArtifactCta /> — contracts (2026-06-11 Risk Note tile fix):
 *   - The third tile is the RISK BOARD (type "risk_board", an artifact the
 *     backend can actually dispatch), not the dead "Risk Note" free-text tile
 *     (type "risk_report" — never existed in _ARTIFACT_DISPATCH → 400 on
 *     every click, before any tier gate).
 *   - The unified endpoint is synchronous: status "ready" resolves the tile
 *     immediately; status "empty" is terminal copy, not a stuck "Drafting…".
 *   - Earnings Pre-Brief sends its ticker (the GenerateArtifactBody shape —
 *     hooks.ts nests it under params.ticker on the wire).
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const mockGenerate = vi.fn();
vi.mock("@/lib/hooks", () => ({
  generateArtifact: (...args: unknown[]) => mockGenerate(...args),
  useArtifacts: () => ({ artifacts: [] }),
}));

const mockMutate = vi.fn();
vi.mock("swr", () => ({
  useSWRConfig: () => ({ mutate: mockMutate }),
}));

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}));

// Plain anchor stand-in — the locked-tile test only asserts the href.
vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...rest
  }: React.PropsWithChildren<{ href: string } & Record<string, unknown>>) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));
import * as React from "react";

import { toast } from "sonner";
import { GenerateArtifactCta } from "@/components/reports/v2/generate-artifact-cta";

const READY = {
  status: "ready",
  type: "risk_board",
  artifact_id: 7,
  data: {},
  reason: null,
  message: null,
  redirect: null,
  pdf_available: true,
  pdf_status: "ok",
};

beforeEach(() => {
  mockGenerate.mockReset();
  mockMutate.mockReset();
  (toast as unknown as ReturnType<typeof vi.fn>).mockClear();
  (toast.success as unknown as ReturnType<typeof vi.fn>).mockClear();
});

// The five tile tests below are SKIPPED, not deleted. GENERATE_AVAILABLE is
// false while `POST /api/artifacts/generate` is gone with the artefact tree, so
// the tiles do not render and these would fail on an offer nobody is making.
// They are the acceptance suite for flipping that flag back on — deleting them
// would mean rebuilding the generator with no coverage. The dormant-state test
// below asserts what the component actually does today.
describe("GenerateArtifactCta — Risk Board tile", () => {
  it.skip("renders the Risk Board tile (not Risk Note) with no free-text input", () => {
    render(<GenerateArtifactCta tier="pro" />);
    expect(screen.getByText("Risk Board")).toBeTruthy();
    expect(screen.queryByText("Risk Note")).toBeNull();
    // Exactly one input on the grid: the earnings ticker. The old free-text
    // topic prompt is gone with the never-built risk_report type.
    expect(screen.getAllByRole("textbox")).toHaveLength(1);
  });

  it.skip("posts type risk_board and resolves immediately on a ready response", async () => {
    mockGenerate.mockResolvedValue(READY);
    render(<GenerateArtifactCta tier="pro" />);

    fireEvent.click(screen.getByText("Run the board ›"));

    await screen.findByText("Ready · in your archive ↑");
    expect(mockGenerate).toHaveBeenCalledTimes(1);
    expect(mockGenerate).toHaveBeenCalledWith({ type: "risk_board" });
    // The dead type must never go over the wire again.
    expect(JSON.stringify(mockGenerate.mock.calls)).not.toContain(
      "risk_report",
    );
    expect(toast.success).toHaveBeenCalledWith(
      "Risk Board is ready",
      expect.anything(),
    );
    // Archive caches revalidate so the new row surfaces everywhere.
    expect(mockMutate).toHaveBeenCalled();
  });

  it.skip("an empty response (new book) shows terminal copy, not a stuck Drafting state", async () => {
    mockGenerate.mockResolvedValue({
      status: "empty",
      type: "risk_board",
      artifact_id: null,
      data: null,
      reason: "no_positions",
      message: "first_position_needed",
      redirect: null,
    });
    render(<GenerateArtifactCta tier="pro" />);

    fireEvent.click(screen.getByText("Run the board ›"));

    await screen.findByText("Your book is empty — add a position first.");
    expect(screen.queryByText("Drafting…")).toBeNull();
  });

  it.skip("earnings pre-brief sends its ticker uppercased", async () => {
    mockGenerate.mockResolvedValue({ ...READY, type: "earnings_prebrief" });
    render(<GenerateArtifactCta tier="pro" />);

    fireEvent.change(screen.getByLabelText(/Ticker symbol/), {
      target: { value: "aapl" },
    });
    fireEvent.click(screen.getByText("Queue pre-brief ›"));

    await screen.findByText("Ready · in your archive ↑");
    expect(mockGenerate).toHaveBeenCalledWith({
      type: "earnings_prebrief",
      ticker: "AAPL",
    });
  });

  it.skip("free tier locks the two Pro tiles behind /pricing", () => {
    render(<GenerateArtifactCta tier="free" />);
    const upgrades = screen.getAllByText("Upgrade to pro");
    expect(upgrades).toHaveLength(2);
    for (const link of upgrades) {
      expect(link.closest("a")?.getAttribute("href")).toBe("/pricing");
    }
    // Brag Card stays free.
    expect(screen.getByText("Generate now ›")).toBeTruthy();
  });

  it("source lock: the component requests risk_board and the topic field is gone", () => {
    // vitest cwd = frontend/ (jsdom import.meta.url is not a file: URL).
    const src = readFileSync(
      join(
        process.cwd(),
        "src/components/reports/v2/generate-artifact-cta.tsx",
      ),
      "utf-8",
    );
    expect(src).toContain('type: "risk_board"');
    expect(src).not.toContain('type: "risk_report"');
    expect(src).not.toContain("needsTopic");
    expect(src).not.toContain("eta_seconds");
  });
});

describe("GenerateArtifactCta — dormant", () => {
  it("states the desk cannot take requests, and offers no tile to click", () => {
    render(<GenerateArtifactCta tier="pro" />);
    expect(screen.getByText(/지금은 요청을 받을 수 없습니다/)).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
    expect(mockGenerate).not.toHaveBeenCalled();
  });
});
