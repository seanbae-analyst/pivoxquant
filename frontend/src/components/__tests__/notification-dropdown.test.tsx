import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LocaleProvider } from "@/lib/locale";
import { API } from "@/lib/endpoints";

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

// Mock auth — the dropdown only fetches for a signed-in user.
const auth = vi.hoisted(() => ({
  user: { id: 1, email: "u@example.com" } as { id: number; email: string } | null,
}));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: auth.user, loading: false }),
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
    auth.user = { id: 1, email: "u@example.com" };
  });

  it("does not request /api/alerts while signed out (SWR key is null)", () => {
    // 2026-09-12 sweep: every protected route fired 401 GET /api/alerts?limit=50
    // before the redirect to /login.
    auth.user = null;
    mockedSWR.mockReturnValue(makeSwrResult(undefined));
    render(
      <LocaleProvider>
        <NotificationDropdown />
      </LocaleProvider>,
    );

    expect(mockedSWR).toHaveBeenCalled();
    for (const call of mockedSWR.mock.calls) {
      expect(call[0]).toBeNull();
    }
  });

  it("requests the shared ?limit=50 alerts key once signed in", () => {
    mockedSWR.mockReturnValue(makeSwrResult({ alerts: [], unread: 0 }));
    render(
      <LocaleProvider>
        <NotificationDropdown />
      </LocaleProvider>,
    );

    expect(mockedSWR.mock.calls[0][0]).toBe(`${API.alerts.list}?limit=50`);
  });

  it("renders the bell button in closed state without exposing menu items", () => {
    mockedSWR.mockReturnValue(makeSwrResult({ alerts: [], unread: 0 }));
    render(
      <LocaleProvider>
        <NotificationDropdown />
      </LocaleProvider>,
    );

    // KR-first locale (LocaleProvider default = "ko"): bell aria-label is "알림".
    const bell = screen.getByRole("button", { name: /알림/ });
    expect(bell).toBeInTheDocument();
    expect(bell).toHaveAttribute("aria-expanded", "false");

    // Menu (role=menu) should not be in DOM yet
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("displays unread count badge when unread > 0", () => {
    mockedSWR.mockReturnValue(makeSwrResult({ alerts: [], unread: 5 }));
    render(
      <LocaleProvider>
        <NotificationDropdown />
      </LocaleProvider>,
    );

    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("caps unread display at 99+", () => {
    mockedSWR.mockReturnValue(makeSwrResult({ alerts: [], unread: 250 }));
    render(
      <LocaleProvider>
        <NotificationDropdown />
      </LocaleProvider>,
    );

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
    render(
      <LocaleProvider>
        <NotificationDropdown />
      </LocaleProvider>,
    );

    const bell = screen.getByRole("button", { name: /알림/ });
    await user.click(bell);

    expect(bell).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(screen.getByText(/Threshold reached/)).toBeInTheDocument();
    // The "전체 보기" footer link went with /alerts in the 2026-08-31 prune —
    // the dropdown is now the only place notifications are read.
    expect(screen.queryByText(/전체 보기/)).not.toBeInTheDocument();
  });
});
