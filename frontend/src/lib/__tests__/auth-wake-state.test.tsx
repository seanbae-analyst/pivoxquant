/**
 * Auth wake state (2026-10-09) — a cold backend is "unknown", not "signed out".
 *
 * The bug these pin: `loading` was `isLoading && !data`, and SWR sets
 * `isLoading` back to true at the start of every retry while there is no
 * data. On a sleeping Render backend the /api/auth/me probe fails and
 * retries, so `loading` flipped true/false/true and the login page swapped
 * its OAuth card for a skeleton on every retry — unmounting
 * <OAuthButtonsV2 /> together with its "서버를 깨우는 중" note, its
 * "다시 시도" button and its wake loop.
 *
 * Also pinned: the unknown state is exposed as `waking` (the dashboard holds
 * instead of redirecting), /api/health is polled while unknown and the probe
 * re-runs the moment it answers, and the retry cadence outlasts a cold boot.
 */
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import { SWRConfig } from "swr";

const replaceMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: replaceMock,
    push: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/login",
}));

import {
  AUTH_WAKE_MAX_RETRIES,
  AUTH_WAKE_RETRY_MS,
  AuthProvider,
  AuthUnknownError,
  authErrorRetry,
  isColdStartAuthError,
  useAuth,
} from "@/lib/auth";
import { LocaleProvider } from "@/lib/locale";
import AuthEntryPage from "@/app/(auth)/login/page";
import ko from "@/messages/ko.json";
import { API } from "@/lib/endpoints";
import { persistStorageKey, __resetPersistedCacheForTests } from "@/lib/persisted-swr-cache";

const WAKING = ko.auth.login.waking;

type Route = (url: string) => Promise<Response>;
let meRoute: Route;
let healthRoute: Route;
let meCalls = 0;
let healthCalls = 0;

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
const offline: Route = () => Promise.reject(new TypeError("Failed to fetch"));
const bad502: Route = async () => new Response("Bad Gateway", { status: 502 });
const healthOk: Route = async () => json(200, { status: "ok" });

function installFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.startsWith(API.auth.me)) {
        meCalls += 1;
        return meRoute(url);
      }
      if (url.startsWith("/api/health")) {
        healthCalls += 1;
        return healthRoute(url);
      }
      return Promise.resolve(json(404, {}));
    }),
  );
}

function tree(ui: React.ReactElement) {
  return (
    <SWRConfig value={{ provider: () => new Map() }}>
      <LocaleProvider>
        <AuthProvider>{ui}</AuthProvider>
      </LocaleProvider>
    </SWRConfig>
  );
}

const loadingTrace: boolean[] = [];
function AuthProbe() {
  const { user, loading, waking, wakeFailed, retryAuth } = useAuth();
  loadingTrace.push(loading);
  return (
    <div>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="waking">{String(waking)}</span>
      <span data-testid="failed">{String(wakeFailed)}</span>
      <span data-testid="user">{user ? String(user.id) : "none"}</span>
      <button onClick={retryAuth}>retry</button>
    </div>
  );
}

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  meCalls = 0;
  healthCalls = 0;
  loadingTrace.length = 0;
  replaceMock.mockReset();
  window.localStorage.clear();
  __resetPersistedCacheForTests();
  document.cookie = "sp_locale=ko";
  meRoute = offline;
  healthRoute = bad502;
  installFetch();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("authErrorRetry — retry cadence", () => {
  const run = (err: Error, retryCount: number) => {
    const revalidate = vi.fn();
    authErrorRetry(err, API.auth.me, {} as never, revalidate, { retryCount, dedupe: true });
    return revalidate;
  };

  it("classifies boot failures (no answer / 408 / 5xx) and nothing else", () => {
    expect(isColdStartAuthError(new AuthUnknownError("x"))).toBe(true);
    expect(isColdStartAuthError(new AuthUnknownError("x", 502))).toBe(true);
    expect(isColdStartAuthError(new AuthUnknownError("x", 408))).toBe(true);
    expect(isColdStartAuthError(new AuthUnknownError("x", 429))).toBe(false);
    expect(isColdStartAuthError(new Error("x"))).toBe(false);
  });

  it("retries a boot failure on a short fixed gap, for longer than a cold start", () => {
    const revalidate = run(new AuthUnknownError("offline"), 1);
    vi.advanceTimersByTime(AUTH_WAKE_RETRY_MS - 1);
    expect(revalidate).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(revalidate).toHaveBeenCalledWith({ retryCount: 1 });
    // 8 × (≤ 8 s probe + 3 s) ≥ the 44 s measured cold start, and ≥ 75 s wake deadline
    expect(AUTH_WAKE_MAX_RETRIES * (8_000 + AUTH_WAKE_RETRY_MS)).toBeGreaterThanOrEqual(75_000);
  });

  it("stops after the wake budget", () => {
    const revalidate = run(new AuthUnknownError("offline"), AUTH_WAKE_MAX_RETRIES + 1);
    vi.advanceTimersByTime(60_000);
    expect(revalidate).not.toHaveBeenCalled();
  });

  it("does not hammer on a 429 — old budget of 2 with backoff", () => {
    const first = run(new AuthUnknownError("rate", 429), 1);
    vi.advanceTimersByTime(AUTH_WAKE_RETRY_MS);
    expect(first).not.toHaveBeenCalled();
    vi.advanceTimersByTime(5_000);
    expect(first).toHaveBeenCalledTimes(1);
    const third = run(new AuthUnknownError("rate", 429), 3);
    vi.advanceTimersByTime(60_000);
    expect(third).not.toHaveBeenCalled();
  });
});

describe("AuthProvider — loading latches; unknown is `waking`", () => {
  it("loading never returns to true across retries, and the unknown state is exposed", async () => {
    render(tree(<AuthProbe />));
    expect(screen.getByTestId("loading").textContent).toBe("true");

    await advance(10);
    expect(screen.getByTestId("loading").textContent).toBe("false");
    expect(screen.getByTestId("waking").textContent).toBe("true");
    expect(screen.getByTestId("user").textContent).toBe("none");

    // Several retry cycles on a backend that stays down.
    await advance(AUTH_WAKE_RETRY_MS * 4 + 100);
    expect(meCalls).toBeGreaterThanOrEqual(3);

    const firstFalse = loadingTrace.indexOf(false);
    expect(firstFalse).toBeGreaterThan(-1);
    expect(loadingTrace.slice(firstFalse)).not.toContain(true);
  });

  it("re-runs the probe the moment /api/health answers 200", async () => {
    render(tree(<AuthProbe />));
    await advance(10);
    expect(screen.getByTestId("waking").textContent).toBe("true");

    // Backend comes up between probe retries.
    meRoute = async () => json(200, { authenticated: true, user: { id: 42 } });
    healthRoute = healthOk;
    const before = meCalls;
    // The health poll runs every 2 s; the probe's own retry is every 3 s, so
    // a call inside the first 2.1 s can only have come from the health poll.
    await advance(2_100);
    expect(healthCalls).toBeGreaterThan(0);
    expect(meCalls).toBeGreaterThan(before);
    expect(screen.getByTestId("waking").textContent).toBe("false");
    expect(screen.getByTestId("user").textContent).toBe("42");
  });

  it("reports wakeFailed past the deadline, and never claims signed-out", async () => {
    render(tree(<AuthProbe />));
    await advance(80_000);
    expect(screen.getByTestId("waking").textContent).toBe("true");
    expect(screen.getByTestId("failed").textContent).toBe("true");
    expect(screen.getByTestId("loading").textContent).toBe("false");
  });

  it("retry after giving up re-runs the probe and recovers", async () => {
    render(tree(<AuthProbe />));
    await advance(80_000);
    expect(screen.getByTestId("failed").textContent).toBe("true");
    meRoute = async () => json(200, { authenticated: true, user: { id: 9 } });
    healthRoute = healthOk;
    fireEvent.click(screen.getByText("retry"));
    await advance(10);
    expect(screen.getByTestId("user").textContent).toBe("9");
    expect(screen.getByTestId("waking").textContent).toBe("false");
    expect(screen.getByTestId("failed").textContent).toBe("false");
  });

  it("a real 401 is signed out (not waking) and wipes the on-device screen cache", async () => {
    window.localStorage.setItem(persistStorageKey(7), JSON.stringify({ v: 1, uid: 7, entries: {} }));
    meRoute = async () => json(401, { code: "UNAUTHORIZED" });
    render(tree(<AuthProbe />));
    await advance(10);
    expect(screen.getByTestId("loading").textContent).toBe("false");
    expect(screen.getByTestId("waking").textContent).toBe("false");
    expect(window.localStorage.getItem(persistStorageKey(7))).toBeNull();
  });
});

describe("/login on a cold backend — the wake note survives auth retries", () => {
  it("keeps the OAuth card (and its waking note) mounted while /api/auth/me retries", async () => {
    render(tree(<AuthEntryPage />));
    await advance(10); // first /me failure settles auth

    const google = screen.getByText(/Google/).closest("a")!;
    fireEvent.click(google);
    await advance(10);
    expect(screen.getByText(WAKING)).toBeInTheDocument();

    const callsAtClick = meCalls;
    for (let i = 0; i < 4; i += 1) {
      await advance(AUTH_WAKE_RETRY_MS);
      // Before the fix each retry put the page back on its skeleton here.
      expect(screen.queryByLabelText("Loading login")).toBeNull();
      expect(screen.getByText(WAKING)).toBeInTheDocument();
    }
    expect(meCalls).toBeGreaterThan(callsAtClick);
  });
});
