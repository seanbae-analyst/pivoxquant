import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";

// Mock the realtime hook before importing the component
vi.mock("@/lib/realtime", () => ({
  useRealtimeStatus: vi.fn(),
}));

import { useRealtimeStatus } from "@/lib/realtime";
import { RealtimeStatusBanner } from "@/components/ui/realtime-status-banner";

const mockedHook = vi.mocked(useRealtimeStatus);

describe("RealtimeStatusBanner", () => {
  beforeEach(() => {
    mockedHook.mockReset();
    // Every string in this banner is about prices, so the component is gated
    // on the vendor-display flag (lib/market-display.ts). These cases assert
    // the ENABLED behaviour; the gate itself is asserted at the bottom.
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "1");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("renders nothing when connected and not failed (happy path)", () => {
    mockedHook.mockReturnValue({
      connected: true,
      failed: false,
      streamActive: true,
      lastUpdate: null,
    });
    const { container } = render(<RealtimeStatusBanner />);
    expect(container.firstChild).toBeNull();
  });

  it("renders red failed banner when failed=true (highest urgency)", () => {
    mockedHook.mockReturnValue({
      connected: false,
      failed: true,
      streamActive: true,
      lastUpdate: null,
    });
    render(<RealtimeStatusBanner />);
    expect(screen.getByText(/실시간 데이터 연결 실패/)).toBeInTheDocument();
    // Refresh button must be present in failed state
    expect(screen.getByRole("button", { name: /새로고침/ })).toBeInTheDocument();
  });

  it("renders yellow reconnecting banner when disconnected but not failed", () => {
    mockedHook.mockReturnValue({
      connected: false,
      failed: false,
      streamActive: true,
      lastUpdate: null,
    });
    render(<RealtimeStatusBanner />);
    expect(screen.getByText(/재연결 중/)).toBeInTheDocument();
    // Reconnecting state should NOT have the refresh button
    expect(screen.queryByRole("button", { name: /새로고침/ })).not.toBeInTheDocument();
  });

  // Bug #1 regression — banner must NOT render for users with no positions
  // (streamActive=false). Without this gate, the default disconnected state
  // showed the yellow "재연결 중" banner forever in the wild.
  it("renders nothing when stream is intentionally idle (no positions, no user, hidden tab)", () => {
    mockedHook.mockReturnValue({
      connected: false,
      failed: false,
      streamActive: false,
      lastUpdate: null,
    });
    const { container } = render(<RealtimeStatusBanner />);
    expect(container.firstChild).toBeNull();
  });

  // Defensive: even if some legacy code path sets failed=true while
  // streamActive=false (shouldn't happen, but guard against), suppress.
  it("renders nothing when streamActive=false even if failed=true", () => {
    mockedHook.mockReturnValue({
      connected: false,
      failed: true,
      streamActive: false,
      lastUpdate: null,
    });
    const { container } = render(<RealtimeStatusBanner />);
    expect(container.firstChild).toBeNull();
  });

  // ── vendor market-data display gate (2026-09-19) ──────────────────
  it("renders nothing when the market-data display flag is off, even on a hard failure", () => {
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "0");
    mockedHook.mockReturnValue({
      connected: false,
      failed: true,
      streamActive: true,
      lastUpdate: null,
    });
    const { container } = render(<RealtimeStatusBanner />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when the flag is unset (unset === off)", () => {
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "");
    mockedHook.mockReturnValue({
      connected: false,
      failed: false,
      streamActive: true,
      lastUpdate: null,
    });
    const { container } = render(<RealtimeStatusBanner />);
    expect(container.firstChild).toBeNull();
  });
});
