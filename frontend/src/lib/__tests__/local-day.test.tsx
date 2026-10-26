import { afterEach, describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";
import { localDayStr } from "@/lib/local-day";

describe("localDayStr", () => {
  it("is the local calendar day, not the UTC one", () => {
    // Built from local fields, so it is 00:30 local whatever the zone.
    expect(localDayStr(new Date(2026, 9, 14, 0, 30))).toBe("2026-10-14");
  });
});

// TradeModalV2 defaulted its date to toISOString()'s UTC day — in Korea,
// yesterday until 09:00 (2026-10-13 bug hunt).
vi.mock("@/lib/api", () => ({ apiFetch: vi.fn(), ApiError: class extends Error {} }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@/lib/hooks", () => ({
  useLinkableReflections: () => ({ reflections: [], isLoading: false, error: undefined }),
}));

describe("TradeModalV2 default date", () => {
  const prevTz = process.env.TZ;
  afterEach(() => {
    vi.useRealTimers();
    process.env.TZ = prevTz;
  });

  it("is today in Korea at 08:30 KST (still yesterday in UTC)", async () => {
    process.env.TZ = "Asia/Seoul";
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-10-13T23:30:00Z")); // 2026-10-14 08:30 KST
    const { TradeModalV2 } = await import("@/components/portfolio/v2/trade-modal-v2");
    const { container } = render(
      <TradeModalV2
        open
        action="buy"
        position={{
          id: "p1", symbol: "AAPL", name: "Apple", shares: 1, avgCost: 1, current: 1,
          notes: "", side: "Long", sector: "Tech", purchaseDate: "2024-01-01",
        }}
        onClose={() => {}}
      />,
    );
    const input = (container.querySelector('input[type="date"]') ??
      document.querySelector('input[type="date"]')) as HTMLInputElement;
    expect(input.value).toBe("2026-10-14");
  });
});
