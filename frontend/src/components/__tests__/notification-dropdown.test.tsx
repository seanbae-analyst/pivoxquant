import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock SWR — return canned alert state per test
vi.mock("swr", () => ({
  default: vi.fn(),
}));

// Mock next/navigation router
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

// Mock api fetch (network-free)
vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn().mockResolvedValue({}),
}));

import useSWR from "swr";
import { NotificationDropdown } from "@/components/ui/notification-dropdown";

const mockedSWR = vi.mocked(useSWR);

function makeSwrResult(data: unknown) {
  return {
    data,
    error: undefined,
    isLoading: false,
    isValidating: false,
    mutate: vi.fn(),
  } as unknown as ReturnType<typeof useSWR>;
}

describe("NotificationDropdown", () => {
  beforeEach(() => {
    mockedSWR.mockReset();
  });

  it("renders the bell button in closed state without exposing menu items", () => {
    mockedSWR.mockReturnValue(makeSwrResult({ alerts: [], unread: 0 }));
    render(<NotificationDropdown />);

    const bell = screen.getByRole("button", { name: /Notifications/i });
    expect(bell).toBeInTheDocument();
    expect(bell).toHaveAttribute("aria-expanded", "false");

    // Menu (role=menu) should not be in DOM yet
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("displays unread count badge when unread > 0", () => {
    mockedSWR.mockReturnValue(makeSwrResult({ alerts: [], unread: 5 }));
    render(<NotificationDropdown />);

    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("caps unread display at 99+", () => {
    mockedSWR.mockReturnValue(makeSwrResult({ alerts: [], unread: 250 }));
    render(<NotificationDropdown />);

    expect(screen.getByText("99+")).toBeInTheDocument();
  });

  it("opens dropdown and renders alert items when bell clicked", async () => {
    mockedSWR.mockReturnValue(
      makeSwrResult({
        alerts: [
          {
            id: 1,
            title: "Threshold reached",
            body: "AAPL crossed observed level",
            ticker: "AAPL",
            created_at: new Date().toISOString(),
            is_read: false,
          },
        ],
        unread: 1,
      }),
    );

    const user = userEvent.setup();
    render(<NotificationDropdown />);

    const bell = screen.getByRole("button", { name: /Notifications/i });
    await user.click(bell);

    expect(bell).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(screen.getByText(/Threshold reached/)).toBeInTheDocument();
    expect(screen.getByText(/View all/i)).toBeInTheDocument();
  });
});
