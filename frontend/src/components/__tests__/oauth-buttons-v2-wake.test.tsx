/**
 * A sleeping backend must not throw the visitor at Render's 502.
 *
 * The backend sleeps after 15 idle minutes (render.yaml `plan: free`). The
 * OAuth buttons are plain anchors, so a click during that window was a full
 * page navigation onto Render's unbranded error page — no branding, no
 * explanation, no retry. That is the "로그인이 안 된다" report.
 *
 * These pin the gate AND its limits. The limits matter as much as the gate:
 * a warm backend must navigate with exactly the latency it had before, and
 * cmd-click / a parent consent gate must keep working untouched.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act, waitFor } from "@testing-library/react";

import { OAuthButtonsV2 } from "@/components/auth/v2/oauth-buttons-v2";
import { API } from "@/lib/endpoints";
import { LocaleProvider } from "@/lib/locale";
import ko from "@/messages/ko.json";

const WAKING = ko.auth.login.waking;
const WAKE_FAILED = ko.auth.login.wakeFailed;

const healthOk = () =>
  new Response(JSON.stringify({ status: "ok" }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });

/** What a spun-down Render answers on the first hit. */
const bad502 = () => new Response("Bad Gateway", { status: 502 });

let fetchMock: ReturnType<typeof vi.fn>;
let assignMock: ReturnType<typeof vi.fn>;
let realLocation: Location;

function renderButtons(ui: React.ReactElement = <OAuthButtonsV2 />) {
  document.cookie = "sp_locale=ko";
  return render(<LocaleProvider>{ui}</LocaleProvider>);
}

/** Drain the probe's promise chain (mocked fetch settles immediately). */
async function flush() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

const googleLink = () => screen.getByText(/Google/).closest("a")!;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  assignMock = vi.fn();
  // jsdom's Location.assign is non-configurable; swap the whole object.
  realLocation = window.location;
  Object.defineProperty(window, "location", {
    configurable: true,
    writable: true,
    value: { ...realLocation, assign: assignMock, href: realLocation.href },
  });
});

afterEach(() => {
  Object.defineProperty(window, "location", {
    configurable: true,
    writable: true,
    value: realLocation,
  });
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("OAuthButtonsV2 — backend wake gate", () => {
  it("probes /api/health once on mount so the container boots while the page is read", async () => {
    fetchMock.mockResolvedValue(healthOk());
    renderButtons();
    await flush();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/health");
  });

  it("navigates natively with zero added latency when the backend is already awake", async () => {
    fetchMock.mockResolvedValue(healthOk());
    renderButtons();
    await flush();

    // fireEvent.click returns false when the handler called preventDefault.
    const notPrevented = fireEvent.click(googleLink());

    expect(notPrevented).toBe(true);
    expect(assignMock).not.toHaveBeenCalled();
    expect(screen.queryByText(WAKING)).not.toBeInTheDocument();
    // No extra probe: the mount one already answered.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("holds the click, announces the wait, then navigates once health returns 200", async () => {
    fetchMock.mockResolvedValueOnce(bad502()); // mount probe: still asleep
    let release!: (r: Response) => void;
    fetchMock.mockImplementationOnce(
      () => new Promise<Response>((resolve) => { release = resolve; }),
    );
    renderButtons();
    await flush();

    const prevented = fireEvent.click(googleLink()) === false;
    expect(prevented).toBe(true);
    await flush();

    // Waiting state: announced politely, both anchors marked unavailable,
    // the clicked one marked busy — and we have NOT navigated yet.
    const waiting = screen.getByText(WAKING);
    expect(waiting).toBeInTheDocument();
    expect(waiting).toHaveAttribute("aria-live", "polite");
    expect(googleLink()).toHaveAttribute("aria-busy", "true");
    expect(googleLink()).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText(/Kakao/).closest("a")).toHaveAttribute("aria-disabled", "true");
    expect(assignMock).not.toHaveBeenCalled();

    await act(async () => {
      release(healthOk());
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(assignMock).toHaveBeenCalledWith(API.auth.google);
  });

  it("keeps the href on the anchor while waiting (JS-dead progressive enhancement)", async () => {
    fetchMock.mockResolvedValue(bad502());
    renderButtons();
    await flush();

    expect(googleLink()).toHaveAttribute("href", API.auth.google);
    expect(screen.getByText(/Kakao/).closest("a")).toHaveAttribute("href", API.auth.kakao);
  });

  it("shows our own Korean error and a working retry instead of Render's 502", async () => {
    vi.useFakeTimers();
    fetchMock.mockResolvedValue(bad502());
    renderButtons();
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });

    fireEvent.click(googleLink());
    // Past the 75s deadline the gate gives up rather than spinning forever.
    await act(async () => { await vi.advanceTimersByTimeAsync(80_000); });

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(WAKE_FAILED);
    expect(screen.queryByText(WAKING)).not.toBeInTheDocument();
    expect(assignMock).not.toHaveBeenCalled();

    // Retry — a real button, so it is keyboard reachable — now succeeds.
    fetchMock.mockResolvedValue(healthOk());
    const retry = screen.getByRole("button", { name: new RegExp(ko.auth.login.wakeRetry) });
    fireEvent.click(retry);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });

    expect(assignMock).toHaveBeenCalledWith(API.auth.google);
  });

  it("leaves cmd/ctrl-click to the browser (open in a new tab)", async () => {
    fetchMock.mockResolvedValue(bad502());
    renderButtons();
    await flush();

    const notPrevented = fireEvent.click(googleLink(), { metaKey: true });

    expect(notPrevented).toBe(true);
    expect(screen.queryByText(WAKING)).not.toBeInTheDocument();
    expect(assignMock).not.toHaveBeenCalled();
  });

  it("does not wake when a parent handler cancelled the click (legal gate)", async () => {
    fetchMock.mockResolvedValue(bad502());
    const onGoogleClick = vi.fn((e: React.MouseEvent) => e.preventDefault());
    renderButtons(<OAuthButtonsV2 onGoogleClick={onGoogleClick} />);
    await flush();

    fireEvent.click(googleLink());
    await flush();

    expect(onGoogleClick).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(WAKING)).not.toBeInTheDocument();
    expect(assignMock).not.toHaveBeenCalled();
  });

  it("stays out of the way in demo mode — no backend to wake", async () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "1");
    renderButtons();
    await flush();

    expect(fetchMock).not.toHaveBeenCalled();
    expect(fireEvent.click(googleLink())).toBe(true);
    expect(assignMock).not.toHaveBeenCalled();
  });

  it("leaves the closed legal gate exactly as it was — buttons, not anchors", async () => {
    fetchMock.mockResolvedValue(bad502());
    renderButtons(<OAuthButtonsV2 disabled hint="동의해 주세요" />);
    await flush();

    // Disabled state is still <button>, and nothing navigates.
    expect(screen.getByText(/Google/).closest("button")).toHaveAttribute("aria-disabled", "true");
    await waitFor(() => expect(assignMock).not.toHaveBeenCalled());
  });
});
