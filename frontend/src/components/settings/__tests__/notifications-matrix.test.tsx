import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock the data layer (SWR hook + PUT mutation) and sonner (toast).
vi.mock("@/lib/hooks", () => ({
  useNotificationPreferences: vi.fn(),
  saveNotificationPreferences: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import {
  useNotificationPreferences,
  saveNotificationPreferences,
} from "@/lib/hooks";
import { toast } from "sonner";
import { NotificationsMatrix } from "@/components/settings/v2/notifications-matrix";

const mockedUseHook = vi.mocked(useNotificationPreferences);
const mockedSave = vi.mocked(saveNotificationPreferences);
const mockedMutate = vi.fn();

// Minimal SWR-hook return shape the component reads (data + mutate).
function hookReturn(prefs: Record<string, Record<string, boolean>> | undefined) {
  return {
    data: prefs ? { prefs } : undefined,
    mutate: mockedMutate,
    // unused-by-component fields, present for type-shape parity
    error: undefined,
    isLoading: !prefs,
    isValidating: false,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } as any;
}

const FULL_SERVER_PREFS = {
  weekly_memo: { email: true, push: true, inapp: true },
  earnings_pre_brief: { email: true, push: true, inapp: true },
  signal_state: { email: false, push: true, inapp: true },
  risk_breach: { email: true, push: true, inapp: true },
  pulse_prompt: { email: true, push: false, inapp: true },
  brag_card: { email: true, push: false, inapp: true },
  broker_sync_error: { email: true, push: true, inapp: true },
};

describe("NotificationsMatrix — server wiring", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mockedUseHook.mockReset();
    mockedSave.mockReset();
    mockedMutate.mockReset();
    vi.mocked(toast.success).mockReset();
    vi.mocked(toast.error).mockReset();
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it("reflects the server prefs map once loaded (signal_state email = off)", async () => {
    mockedUseHook.mockReturnValue(hookReturn(FULL_SERVER_PREFS));
    render(<NotificationsMatrix />);

    // signal_state email toggle should hydrate to OFF from the server map.
    const signalEmail = await screen.findByRole("switch", {
      name: /Signal state change · email/i,
    });
    await waitFor(() => {
      expect(signalEmail).toHaveAttribute("aria-checked", "false");
    });

    // weekly_memo email is ON from the server map.
    const memoEmail = screen.getByRole("switch", {
      name: /Weekly memo.*· email/i,
    });
    expect(memoEmail).toHaveAttribute("aria-checked", "true");
  });

  it("PUTs the updated map after the debounce on toggle, then toasts success", async () => {
    mockedUseHook.mockReturnValue(hookReturn(FULL_SERVER_PREFS));
    mockedSave.mockResolvedValue({ prefs: FULL_SERVER_PREFS });

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<NotificationsMatrix />);

    const signalEmail = await screen.findByRole("switch", {
      name: /Signal state change · email/i,
    });
    await waitFor(() =>
      expect(signalEmail).toHaveAttribute("aria-checked", "false"),
    );

    // Toggle signal_state email ON — optimistic update is immediate.
    await user.click(signalEmail);
    expect(signalEmail).toHaveAttribute("aria-checked", "true");

    // No PUT before the debounce window elapses.
    expect(mockedSave).not.toHaveBeenCalled();

    // Advance past the 600ms debounce.
    await act(async () => {
      vi.advanceTimersByTime(700);
    });

    await waitFor(() => expect(mockedSave).toHaveBeenCalledTimes(1));
    const sentMap = mockedSave.mock.calls[0][0];
    expect(sentMap.signal_state.email).toBe(true);

    await waitFor(() =>
      expect(toast.success).toHaveBeenCalledWith("알림 설정 저장됨"),
    );
  });

  it("rolls back the toggle and toasts an error when the PUT fails", async () => {
    mockedUseHook.mockReturnValue(hookReturn(FULL_SERVER_PREFS));
    mockedSave.mockRejectedValue(new Error("boom"));

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<NotificationsMatrix />);

    const signalEmail = await screen.findByRole("switch", {
      name: /Signal state change · email/i,
    });
    await waitFor(() =>
      expect(signalEmail).toHaveAttribute("aria-checked", "false"),
    );

    await user.click(signalEmail);
    expect(signalEmail).toHaveAttribute("aria-checked", "true");

    await act(async () => {
      vi.advanceTimersByTime(700);
    });

    await waitFor(() => expect(mockedSave).toHaveBeenCalledTimes(1));

    // Failure → rollback to the pre-edit OFF state + error toast.
    await waitFor(() =>
      expect(signalEmail).toHaveAttribute("aria-checked", "false"),
    );
    expect(toast.error).toHaveBeenCalled();
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("batches rapid toggles into a single PUT", async () => {
    mockedUseHook.mockReturnValue(hookReturn(FULL_SERVER_PREFS));
    mockedSave.mockResolvedValue({ prefs: FULL_SERVER_PREFS });

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<NotificationsMatrix />);

    const signalEmail = await screen.findByRole("switch", {
      name: /Signal state change · email/i,
    });
    await waitFor(() =>
      expect(signalEmail).toHaveAttribute("aria-checked", "false"),
    );
    const pulsePush = screen.getByRole("switch", {
      name: /Pulse prompt.*· push/i,
    });

    await user.click(signalEmail);
    await user.click(pulsePush);

    await act(async () => {
      vi.advanceTimersByTime(700);
    });

    await waitFor(() => expect(mockedSave).toHaveBeenCalledTimes(1));
    const sentMap = mockedSave.mock.calls[0][0];
    expect(sentMap.signal_state.email).toBe(true);
    expect(sentMap.pulse_prompt.push).toBe(true);
  });
});
