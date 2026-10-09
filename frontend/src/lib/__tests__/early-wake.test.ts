/**
 * Early backend wake (2026-10-09): one cookie-less GET /api/health per page
 * load, as early as the bundle evaluates. Pinned: it fires once, never with
 * credentials, never in demo mode, never twice when the inline <head> script
 * already sent it — and the inline script's literal path is HEALTH_PATH.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { wakeBackendEarly, __resetEarlyWakeForTests } from "@/lib/early-wake";
import {
  EARLY_WAKE_INLINE_PATH,
  EARLY_WAKE_INLINE_SCRIPT,
  EARLY_WAKE_WINDOW_FLAG,
} from "@/lib/early-wake-inline";
import { HEALTH_PATH } from "@/lib/backend-wake";

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  __resetEarlyWakeForTests();
  fetchMock = vi.fn(() => Promise.resolve(new Response("", { status: 502 })));
  vi.stubGlobal("fetch", fetchMock);
  delete (window as unknown as Record<string, unknown>)[EARLY_WAKE_WINDOW_FLAG];
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("wakeBackendEarly", () => {
  it("sends exactly one cookie-less GET to the health route", () => {
    expect(wakeBackendEarly()).toBe(true);
    expect(wakeBackendEarly()).toBe(false);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(HEALTH_PATH);
    expect(init.method).toBe("GET");
    expect(init.credentials).toBe("omit");
    expect(init.cache).toBe("no-store");
  });

  it("swallows a failing request (a sleeping backend is expected)", async () => {
    fetchMock.mockImplementation(() => Promise.reject(new TypeError("Failed to fetch")));
    expect(() => wakeBackendEarly()).not.toThrow();
    await Promise.resolve();
  });

  it("does nothing in demo mode", () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "1");
    expect(wakeBackendEarly()).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("does not send a second request when the inline <head> script already did", () => {
    (window as unknown as Record<string, unknown>)[EARLY_WAKE_WINDOW_FLAG] = 1;
    expect(wakeBackendEarly()).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("EARLY_WAKE_INLINE_SCRIPT", () => {
  it("targets the same health route and sets the dedupe flag", () => {
    expect(EARLY_WAKE_INLINE_PATH).toBe(HEALTH_PATH);
    // Execute it as the browser would.
    new Function(EARLY_WAKE_INLINE_SCRIPT)();
    expect((window as unknown as Record<string, unknown>)[EARLY_WAKE_WINDOW_FLAG]).toBe(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(HEALTH_PATH);
    expect(init.credentials).toBe("omit");
  });
});
