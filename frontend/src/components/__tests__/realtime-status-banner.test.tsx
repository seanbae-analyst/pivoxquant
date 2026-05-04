import { describe, it, expect, vi, beforeEach } from "vitest";
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
  });

  it("renders nothing when connected and not failed (happy path)", () => {
    mockedHook.mockReturnValue({ connected: true, failed: false, lastUpdate: null });
    const { container } = render(<RealtimeStatusBanner />);
    expect(container.firstChild).toBeNull();
  });

  it("renders red failed banner when failed=true (highest urgency)", () => {
    mockedHook.mockReturnValue({ connected: false, failed: true, lastUpdate: null });
    render(<RealtimeStatusBanner />);
    expect(screen.getByText(/실시간 데이터 연결 실패/)).toBeInTheDocument();
    // Refresh button must be present in failed state
    expect(screen.getByRole("button", { name: /새로고침/ })).toBeInTheDocument();
  });

  it("renders yellow reconnecting banner when disconnected but not failed", () => {
    mockedHook.mockReturnValue({ connected: false, failed: false, lastUpdate: null });
    render(<RealtimeStatusBanner />);
    expect(screen.getByText(/재연결 중/)).toBeInTheDocument();
    // Reconnecting state should NOT have the refresh button
    expect(screen.queryByRole("button", { name: /새로고침/ })).not.toBeInTheDocument();
  });
});
