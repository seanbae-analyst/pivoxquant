/**
 * <DataStaleBanner /> tests — Wave G C-CS3.
 *
 * Covers the four behaviours that matter for end users:
 *   1. is_stale=false → invisible (happy path).
 *   2. is_stale=true + not dismissed → visible with KR/US label.
 *   3. dismissed within 1 h → invisible.
 *   4. dismiss button click → writes LocalStorage + hides banner.
 *
 * SWR is mocked so the test never touches `fetch` and runs deterministically
 * regardless of network availability in the jsdom env.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock SWR before importing the component so the hook returns whatever the
// test sets. We avoid mocking `fetch` directly — the SWR fetcher path is
// covered by the backend integration test; here we focus on the rendering
// contract.
vi.mock("swr", () => ({
  __esModule: true,
  default: vi.fn(),
}));

// The banner is now route-scoped (QA finding P3, 2026-09-19): it only renders
// on a screen that actually shows vendor prices. Default the mocked router to
// /portfolio — the one such screen — so the pre-existing cases below keep
// asserting the same rendering contract they always did.
const mockPathname = vi.fn(() => "/portfolio");
vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname(),
}));

import useSWR from "swr";
import { DataStaleBanner } from "@/components/ui/data-stale-banner";

const mockedSWR = vi.mocked(useSWR);

function mockStatus(payload: {
  is_stale: boolean;
  stale_ratio?: number;
  affected_markets?: Array<"KR" | "US">;
  market_data_display?: boolean;
}) {
  mockedSWR.mockReturnValue({
    data: {
      is_stale: payload.is_stale,
      stale_ratio: payload.stale_ratio ?? 0,
      affected_markets: payload.affected_markets ?? [],
      updated_at: null,
      threshold_pct: 0.05,
      ...(payload.market_data_display === undefined
        ? {}
        : { market_data_display: payload.market_data_display }),
    },
    error: undefined,
    isLoading: false,
    isValidating: false,
    mutate: vi.fn(),
    // SWR's return type has more fields but we cast to `any` because the
    // component only reads { data, error }.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } as any);
}

describe("DataStaleBanner", () => {
  beforeEach(() => {
    mockedSWR.mockReset();
    mockPathname.mockReturnValue("/portfolio");
    window.localStorage.clear();
    // A staleness warning about vendor prices presupposes vendor prices are
    // displayed. The cases below assert the ENABLED behaviour; the gate
    // itself is asserted in the block at the bottom.
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "1");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("renders nothing on the happy path (is_stale=false)", async () => {
    mockStatus({ is_stale: false });
    const { container } = render(<DataStaleBanner />);
    // useEffect runs after mount; wait a tick.
    await act(async () => {});
    expect(container.firstChild).toBeNull();
  });

  it("renders the banner when is_stale=true and not dismissed", async () => {
    mockStatus({
      is_stale: true,
      stale_ratio: 0.4,
      affected_markets: ["KR"],
    });
    render(<DataStaleBanner />);
    await act(async () => {});

    const banner = await screen.findByTestId("data-stale-banner");
    expect(banner).toBeInTheDocument();
    // KR market should be labelled as "한국"
    expect(screen.getByText(/한국.*지연/)).toBeInTheDocument();
    // Helper copy
    expect(
      screen.getByText(/표시된 가격이 최신이 아닐 수 있습니다/),
    ).toBeInTheDocument();
  });

  it("renders a generic headline when no markets are flagged", async () => {
    mockStatus({
      is_stale: true,
      stale_ratio: 0.06,
      affected_markets: [],
    });
    render(<DataStaleBanner />);
    await act(async () => {});

    expect(
      await screen.findByText(/일부 시세 데이터가 지연되고 있어요/),
    ).toBeInTheDocument();
  });

  it("renders combined label when both KR and US are stale", async () => {
    mockStatus({
      is_stale: true,
      stale_ratio: 0.5,
      affected_markets: ["KR", "US"],
    });
    render(<DataStaleBanner />);
    await act(async () => {});

    expect(
      await screen.findByText(/한국.*미국.*지연/),
    ).toBeInTheDocument();
  });

  it("renders nothing when dismissed within the 1 h window", async () => {
    mockStatus({
      is_stale: true,
      affected_markets: ["KR"],
    });
    // Pre-populate the dismiss-until timestamp 30 min in the future.
    window.localStorage.setItem(
      "pivox_stale_banner_dismissed_until",
      String(Date.now() + 30 * 60 * 1000),
    );

    const { container } = render(<DataStaleBanner />);
    await act(async () => {});
    expect(container.firstChild).toBeNull();
  });

  it("re-renders the banner once the dismiss window has expired", async () => {
    mockStatus({
      is_stale: true,
      affected_markets: ["KR"],
    });
    // Expired 1 h ago.
    window.localStorage.setItem(
      "pivox_stale_banner_dismissed_until",
      String(Date.now() - 60 * 60 * 1000),
    );

    render(<DataStaleBanner />);
    await act(async () => {});
    expect(await screen.findByTestId("data-stale-banner")).toBeInTheDocument();
  });

  it("hides the banner and writes LocalStorage when dismiss is clicked", async () => {
    mockStatus({
      is_stale: true,
      affected_markets: ["US"],
    });
    const user = userEvent.setup();
    render(<DataStaleBanner />);
    await act(async () => {});

    const dismissBtn = await screen.findByTestId("data-stale-banner-dismiss");
    expect(dismissBtn).toBeInTheDocument();

    await user.click(dismissBtn);

    // After click — banner gone.
    expect(screen.queryByTestId("data-stale-banner")).toBeNull();

    // LocalStorage should hold a future timestamp.
    const raw = window.localStorage.getItem(
      "pivox_stale_banner_dismissed_until",
    );
    expect(raw).not.toBeNull();
    const ts = Number(raw);
    expect(Number.isFinite(ts)).toBe(true);
    expect(ts).toBeGreaterThan(Date.now());
    // Within the 1 h cap (+ generous slack for slow CI).
    expect(ts).toBeLessThanOrEqual(Date.now() + 60 * 60 * 1000 + 5_000);
  });

  it("renders nothing on SWR error (no false alarm)", async () => {
    mockedSWR.mockReturnValue({
      data: undefined,
      error: new Error("HTTP 500"),
      isLoading: false,
      isValidating: false,
      mutate: vi.fn(),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);
    const { container } = render(<DataStaleBanner />);
    await act(async () => {});
    expect(container.firstChild).toBeNull();
  });

  // ── vendor market-data display gate + route scope (2026-09-19) ─────
  it("renders nothing on a screen that shows no prices (/pre-trade)", async () => {
    mockStatus({ is_stale: true, affected_markets: ["KR"] });
    mockPathname.mockReturnValue("/pre-trade");
    const { container } = render(<DataStaleBanner />);
    await act(async () => {});
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing on /settings", async () => {
    mockStatus({ is_stale: true, affected_markets: ["KR"] });
    mockPathname.mockReturnValue("/settings");
    const { container } = render(<DataStaleBanner />);
    await act(async () => {});
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when the market-data display flag is off", async () => {
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "0");
    mockStatus({ is_stale: true, affected_markets: ["KR"] });
    const { container } = render(<DataStaleBanner />);
    await act(async () => {});
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when the backend reports market_data_display=false", async () => {
    mockStatus({
      is_stale: true,
      affected_markets: ["KR"],
      market_data_display: false,
    });
    const { container } = render(<DataStaleBanner />);
    await act(async () => {});
    expect(container.firstChild).toBeNull();
  });

  it("still renders when the backend omits market_data_display (pre-contract deploy)", async () => {
    mockStatus({ is_stale: true, affected_markets: ["KR"] });
    render(<DataStaleBanner />);
    await act(async () => {});
    expect(await screen.findByTestId("data-stale-banner")).toBeInTheDocument();
  });
});
