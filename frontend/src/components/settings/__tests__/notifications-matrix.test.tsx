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
function hookReturn(
  prefs: Record<string, Record<string, boolean>> | undefined,
  channels: Record<string, string[]> | undefined = FULL_SERVER_CHANNELS,
) {
  return {
    data: prefs ? { prefs, channels } : undefined,
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
//
// 2026-09-29: every event used to render all three channels. The 52-week and
// concentration sweeps only ever write a bell row + push (services/alert.py);
// the monthly report only ever emails. Those are the only live cells — the
// server says so in `channels`, the rest render as "—" with no switch.
const FULL_SERVER_PREFS = {
  price_52w: { email: false, push: false, inapp: true },
  concentration: { email: false, push: true, inapp: true },
};
const FULL_SERVER_CHANNELS = {
  price_52w: ["push", "inapp"],
  concentration: ["push", "inapp"],
  monthly_mirror: ["email"],
};

describe("NotificationsMatrix — server wiring", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    // The 52-week row needs a vendor quote, so the matrix hides it whenever
    // the vendor-display flag is off (lib/market-display.ts). These cases
    // assert the ENABLED behaviour; the gate is asserted in its own block.
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "1");
    mockedUseHook.mockReset();
    mockedSave.mockReset();
    mockedMutate.mockReset();
    vi.mocked(toast.success).mockReset();
    vi.mocked(toast.error).mockReset();
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
    vi.unstubAllEnvs();
  });

  it("reflects the server prefs map once loaded (price_52w email = off)", async () => {
    mockedUseHook.mockReturnValue(hookReturn(FULL_SERVER_PREFS));
    renderMatrix();

    // price_52w push toggle should hydrate to OFF from the server map.
    const signalPush = await screen.findByRole("switch", {
      name: /52주 범위 · push/i,
    });
    await waitFor(() => {
      expect(signalPush).toHaveAttribute("aria-checked", "false");
    });

    // concentration in-app is ON from the server map.
    const concentrationInapp = screen.getByRole("switch", {
      name: /섹터 집중도 · inapp/i,
    });
    expect(concentrationInapp).toHaveAttribute("aria-checked", "true");
  });

  it("PUTs the updated map after the debounce on toggle, then toasts success", async () => {
    mockedUseHook.mockReturnValue(hookReturn(FULL_SERVER_PREFS));
    mockedSave.mockResolvedValue({ prefs: FULL_SERVER_PREFS });

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderMatrix();

    const signalPush = await screen.findByRole("switch", {
      name: /52주 범위 · push/i,
    });
    await waitFor(() =>
      expect(signalPush).toHaveAttribute("aria-checked", "false"),
    );

    // Toggle price_52w push ON — optimistic update is immediate.
    await user.click(signalPush);
    expect(signalPush).toHaveAttribute("aria-checked", "true");

    // No PUT before the debounce window elapses.
    expect(mockedSave).not.toHaveBeenCalled();

    // Advance past the 600ms debounce.
    await act(async () => {
      vi.advanceTimersByTime(700);
    });

    await waitFor(() => expect(mockedSave).toHaveBeenCalledTimes(1));
    const sentMap = mockedSave.mock.calls[0][0];
    expect(sentMap.price_52w.push).toBe(true);

    await waitFor(() =>
      expect(toast.success).toHaveBeenCalledWith("알림 설정 저장됨"),
    );
  });

  it("rolls back the toggle and toasts an error when the PUT fails", async () => {
    mockedUseHook.mockReturnValue(hookReturn(FULL_SERVER_PREFS));
    mockedSave.mockRejectedValue(new Error("boom"));

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderMatrix();

    const signalPush = await screen.findByRole("switch", {
      name: /52주 범위 · push/i,
    });
    await waitFor(() =>
      expect(signalPush).toHaveAttribute("aria-checked", "false"),
    );

    await user.click(signalPush);
    expect(signalPush).toHaveAttribute("aria-checked", "true");

    await act(async () => {
      vi.advanceTimersByTime(700);
    });

    await waitFor(() => expect(mockedSave).toHaveBeenCalledTimes(1));

    // Failure → rollback to the pre-edit OFF state + error toast.
    await waitFor(() =>
      expect(signalPush).toHaveAttribute("aria-checked", "false"),
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

    const signalPush = screen.getByRole("switch", {
      name: /52주 범위 · push/i,
    });
    // Toggle is disabled while loading.
    expect(signalPush).toBeDisabled();
    expect(signalPush).toHaveAttribute("aria-disabled", "true");

    // Clicking a disabled toggle is a no-op (userEvent respects pointer-events;
    // assert no PUT regardless).
    await user.click(signalPush).catch(() => {});

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

    const signalPush = await screen.findByRole("switch", {
      name: /52주 범위 · push/i,
    });
    await waitFor(() => expect(signalPush).not.toBeDisabled());

    await user.click(signalPush);
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

    const signalPush = await screen.findByRole("switch", {
      name: /52주 범위 · push/i,
    });
    await waitFor(() =>
      expect(signalPush).toHaveAttribute("aria-checked", "false"),
    );
    const concentrationPush = screen.getByRole("switch", {
      name: /섹터 집중도 · push/i,
    });

    await user.click(signalPush);
    await user.click(concentrationPush);

    await act(async () => {
      vi.advanceTimersByTime(700);
    });

    await waitFor(() => expect(mockedSave).toHaveBeenCalledTimes(1));
    const sentMap = mockedSave.mock.calls[0][0];
    expect(sentMap.price_52w.push).toBe(true);
    expect(sentMap.concentration.push).toBe(false);
  });
});

describe("NotificationsMatrix — the server owns the row list", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mockedUseHook.mockReset();
    mockedSave.mockReset();
    mockedMutate.mockReset();
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
    vi.unstubAllEnvs();
  });

  it("drops the 52-week row when the market-data display flag is off", async () => {
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "0");
    mockedUseHook.mockReturnValue(hookReturn(FULL_SERVER_PREFS));
    renderMatrix();
    await act(async () => {});

    expect(
      screen.queryByRole("switch", { name: /52주 범위 · push/i }),
    ).toBeNull();
    // The event that does not need a quote is untouched.
    expect(
      screen.getByRole("switch", { name: /섹터 집중도 · inapp/i }),
    ).toBeInTheDocument();
  });

  it("drops a row the backend stops returning, even with the flag on", async () => {
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "1");
    // Backend with MARKET_DATA_DISPLAY_ENABLED off omits price_52w entirely.
    mockedUseHook.mockReturnValue(
      hookReturn({ concentration: { email: true, push: true, inapp: true } }),
    );
    renderMatrix();
    await act(async () => {});

    expect(
      screen.queryByRole("switch", { name: /52주 범위 · push/i }),
    ).toBeNull();
    expect(
      screen.getByRole("switch", { name: /섹터 집중도 · inapp/i }),
    ).toBeInTheDocument();
  });

  it("never PUTs an id the server did not return", async () => {
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "1");
    const serverPrefs = {
      concentration: { email: true, push: true, inapp: true },
    };
    mockedUseHook.mockReturnValue(hookReturn(serverPrefs));
    mockedSave.mockResolvedValue({ prefs: serverPrefs });

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderMatrix();

    const concentrationInapp = await screen.findByRole("switch", {
      name: /섹터 집중도 · inapp/i,
    });
    await waitFor(() => expect(concentrationInapp).not.toBeDisabled());
    await user.click(concentrationInapp);

    await act(async () => {
      vi.advanceTimersByTime(700);
    });

    await waitFor(() => expect(mockedSave).toHaveBeenCalledTimes(1));
    const sentMap = mockedSave.mock.calls[0][0];
    expect(Object.keys(sentMap)).toEqual(["concentration"]);
    expect(sentMap.price_52w).toBeUndefined();
  });
});

describe("NotificationsMatrix — only channels with a sender are toggles", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.stubEnv("NEXT_PUBLIC_MARKET_DATA_DISPLAY", "1");
    mockedUseHook.mockReset();
    mockedSave.mockReset();
    mockedMutate.mockReset();
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
    vi.unstubAllEnvs();
  });

  const PREFS_WITH_MIRROR = {
    ...FULL_SERVER_PREFS,
    monthly_mirror: { email: true, push: false, inapp: false },
  };

  it("renders no switch for a channel the server lists as dead", async () => {
    mockedUseHook.mockReturnValue(hookReturn(PREFS_WITH_MIRROR));
    renderMatrix();
    await act(async () => {});

    // concentration is never emailed; monthly mirror is only emailed.
    expect(screen.queryByRole("switch", { name: /섹터 집중도 · email/i })).toBeNull();
    expect(screen.queryByRole("switch", { name: /52주 범위 · email/i })).toBeNull();
    expect(screen.queryByRole("switch", { name: /월간 거울 리포트 · push/i })).toBeNull();
    expect(screen.queryByRole("switch", { name: /월간 거울 리포트 · inapp/i })).toBeNull();
    // Live cells are still switches.
    expect(screen.getByRole("switch", { name: /섹터 집중도 · push/i })).toBeInTheDocument();
    expect(
      screen.getByRole("switch", { name: /월간 거울 리포트 · email/i }),
    ).toHaveAttribute("aria-checked", "true");
  });

  it("falls back to the local allowlist before / without a server channel map", async () => {
    mockedUseHook.mockReturnValue(hookReturn(PREFS_WITH_MIRROR, undefined));
    renderMatrix();
    await act(async () => {});

    expect(screen.queryByRole("switch", { name: /섹터 집중도 · email/i })).toBeNull();
    expect(screen.queryByRole("switch", { name: /월간 거울 리포트 · push/i })).toBeNull();
    expect(screen.getByRole("switch", { name: /월간 거울 리포트 · email/i })).toBeInTheDocument();
  });
});
