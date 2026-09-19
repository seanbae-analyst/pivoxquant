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
import { LocaleProvider } from "@/lib/locale";

// The matrix reads its event names/help from settingsV2.notifications via
// useT (2026-09-19), so every render needs the provider. ko is the default
// locale — hence the Korean row names in the accessible-name queries below.
function renderMatrix() {
  return render(
    <LocaleProvider>
      <NotificationsMatrix />
    </LocaleProvider>,
  );
}

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

// 2026-09-01: was the seven legacy event ids. Six had lost their producer and
// the seventh died with the quant engine; the matrix now exposes the two
// notifications this product actually sends (models.user.NOTIFICATION_EVENT_IDS).
const FULL_SERVER_PREFS = {
  price_52w: { email: false, push: true, inapp: true },
  concentration: { email: true, push: true, inapp: true },
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

  it("reflects the server prefs map once loaded (price_52w email = off)", async () => {
    mockedUseHook.mockReturnValue(hookReturn(FULL_SERVER_PREFS));
    renderMatrix();

    // price_52w email toggle should hydrate to OFF from the server map.
    const signalEmail = await screen.findByRole("switch", {
      name: /52주 범위 · email/i,
    });
    await waitFor(() => {
      expect(signalEmail).toHaveAttribute("aria-checked", "false");
    });

    // concentration email is ON from the server map.
    const concentrationEmail = screen.getByRole("switch", {
      name: /섹터 집중도 · email/i,
    });
    expect(concentrationEmail).toHaveAttribute("aria-checked", "true");
  });

  it("PUTs the updated map after the debounce on toggle, then toasts success", async () => {
    mockedUseHook.mockReturnValue(hookReturn(FULL_SERVER_PREFS));
    mockedSave.mockResolvedValue({ prefs: FULL_SERVER_PREFS });

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderMatrix();

    const signalEmail = await screen.findByRole("switch", {
      name: /52주 범위 · email/i,
    });
    await waitFor(() =>
      expect(signalEmail).toHaveAttribute("aria-checked", "false"),
    );

    // Toggle price_52w email ON — optimistic update is immediate.
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
    expect(sentMap.price_52w.email).toBe(true);

    await waitFor(() =>
      expect(toast.success).toHaveBeenCalledWith("알림 설정 저장됨"),
    );
  });

  it("rolls back the toggle and toasts an error when the PUT fails", async () => {
    mockedUseHook.mockReturnValue(hookReturn(FULL_SERVER_PREFS));
    mockedSave.mockRejectedValue(new Error("boom"));

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderMatrix();

    const signalEmail = await screen.findByRole("switch", {
      name: /52주 범위 · email/i,
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

  it("does NOT PUT when toggled while the server map is still loading (data undefined)", async () => {
    // FIX 3: pre-hydration the matrix shows hardcoded defaults. A toggle now
    // would PUT those defaults and the backend's full-replace would wipe the
    // user's saved custom prefs. Toggles must be disabled until hydration.
    mockedUseHook.mockReturnValue(hookReturn(undefined)); // isLoading, data undefined
    mockedSave.mockResolvedValue({ prefs: FULL_SERVER_PREFS });

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderMatrix();

    const signalEmail = screen.getByRole("switch", {
      name: /52주 범위 · email/i,
    });
    // Toggle is disabled while loading.
    expect(signalEmail).toBeDisabled();
    expect(signalEmail).toHaveAttribute("aria-disabled", "true");

    // Clicking a disabled toggle is a no-op (userEvent respects pointer-events;
    // assert no PUT regardless).
    await user.click(signalEmail).catch(() => {});

    await act(async () => {
      vi.advanceTimersByTime(700);
    });

    expect(mockedSave).not.toHaveBeenCalled();
  });

  it("enables toggles and PUTs normally once the server map has loaded", async () => {
    // After hydration the same toggle is enabled and persists as before.
    mockedUseHook.mockReturnValue(hookReturn(FULL_SERVER_PREFS));
    mockedSave.mockResolvedValue({ prefs: FULL_SERVER_PREFS });

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderMatrix();

    const signalEmail = await screen.findByRole("switch", {
      name: /52주 범위 · email/i,
    });
    await waitFor(() => expect(signalEmail).not.toBeDisabled());

    await user.click(signalEmail);
    await act(async () => {
      vi.advanceTimersByTime(700);
    });

    await waitFor(() => expect(mockedSave).toHaveBeenCalledTimes(1));
  });

  it("batches rapid toggles into a single PUT", async () => {
    mockedUseHook.mockReturnValue(hookReturn(FULL_SERVER_PREFS));
    mockedSave.mockResolvedValue({ prefs: FULL_SERVER_PREFS });

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderMatrix();

    const signalEmail = await screen.findByRole("switch", {
      name: /52주 범위 · email/i,
    });
    await waitFor(() =>
      expect(signalEmail).toHaveAttribute("aria-checked", "false"),
    );
    const concentrationPush = screen.getByRole("switch", {
      name: /섹터 집중도 · push/i,
    });

    await user.click(signalEmail);
    await user.click(concentrationPush);

    await act(async () => {
      vi.advanceTimersByTime(700);
    });

    await waitFor(() => expect(mockedSave).toHaveBeenCalledTimes(1));
    const sentMap = mockedSave.mock.calls[0][0];
    expect(sentMap.price_52w.email).toBe(true);
    expect(sentMap.concentration.push).toBe(false);
  });
});
