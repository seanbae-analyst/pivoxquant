/**
 * The poll loop's contract, pinned with tiny intervals so the test runs in
 * milliseconds instead of the production 75 s deadline.
 *
 * What matters here is what the loop does NOT do: it does not keep polling
 * past the deadline, it does not treat a 503 (process up, DB down) as awake,
 * and it does not touch the network at all when disabled.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

import {
  useBackendWake,
  probeBackendOnce,
  WAKE_DEADLINE_MS,
  WAKE_POLL_INTERVAL_MS,
  WAKE_PROBE_TIMEOUT_MS,
} from "@/lib/backend-wake";

const ok = () => new Response("{}", { status: 200 });
const gateway502 = () => new Response("Bad Gateway", { status: 502 });
const degraded503 = () => new Response("{}", { status: 503 });

let fetchMock: ReturnType<typeof vi.fn>;

const fast = { pollIntervalMs: 1, deadlineMs: 40, probeTimeoutMs: 20 };

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("probeBackendOnce", () => {
  it("is true only on a 2xx — 502 and 503 both mean 'not yet'", async () => {
    fetchMock.mockResolvedValueOnce(ok());
    await expect(probeBackendOnce(20)).resolves.toBe(true);
    fetchMock.mockResolvedValueOnce(gateway502());
    await expect(probeBackendOnce(20)).resolves.toBe(false);
    fetchMock.mockResolvedValueOnce(degraded503());
    await expect(probeBackendOnce(20)).resolves.toBe(false);
  });

  it("swallows a network error rather than throwing at the caller", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await expect(probeBackendOnce(20)).resolves.toBe(false);
  });

  it("sends no credentials — a liveness probe needs no identity", async () => {
    fetchMock.mockResolvedValueOnce(ok());
    await probeBackendOnce(20);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      credentials: "omit",
      cache: "no-store",
    });
  });
});

describe("useBackendWake", () => {
  it("flips to ready from the single mount probe", async () => {
    fetchMock.mockResolvedValue(ok());
    const { result } = renderHook(() => useBackendWake(fast));

    await act(async () => { await new Promise((r) => setTimeout(r, 5)); });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(result.current.isReady).toBe(true);
    // Already ready → wake() resolves without another request.
    await act(async () => { await expect(result.current.wake()).resolves.toBe(true); });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("polls until a 200 and then reports ready", async () => {
    fetchMock
      .mockResolvedValueOnce(gateway502()) // mount
      .mockResolvedValueOnce(gateway502())
      .mockResolvedValueOnce(ok());
    const { result } = renderHook(() => useBackendWake(fast));
    await act(async () => { await new Promise((r) => setTimeout(r, 5)); });
    expect(result.current.isReady).toBe(false);

    await act(async () => { await expect(result.current.wake()).resolves.toBe(true); });

    expect(result.current.status).toBe("ready");
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("gives up at the deadline instead of polling forever", async () => {
    fetchMock.mockResolvedValue(gateway502());
    const { result } = renderHook(() => useBackendWake(fast));
    await act(async () => { await new Promise((r) => setTimeout(r, 5)); });

    await act(async () => { await expect(result.current.wake()).resolves.toBe(false); });

    expect(result.current.status).toBe("failed");
    // 40ms budget at a 1ms interval — bounded, and nowhere near unbounded.
    expect(fetchMock.mock.calls.length).toBeLessThan(60);
  });

  it("never touches the network when disabled, and wake() resolves at once", async () => {
    const { result } = renderHook(() => useBackendWake({ ...fast, enabled: false }));
    await act(async () => { await new Promise((r) => setTimeout(r, 5)); });

    await act(async () => { await expect(result.current.wake()).resolves.toBe(true); });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("ships timings sized to the measured cold start (43.9s), not to guesses", () => {
    expect(WAKE_PROBE_TIMEOUT_MS).toBeGreaterThan(5_000);
    expect(WAKE_POLL_INTERVAL_MS).toBeLessThanOrEqual(3_000);
    expect(WAKE_DEADLINE_MS).toBeGreaterThan(43_900);
    expect(WAKE_DEADLINE_MS).toBeLessThanOrEqual(90_000);
  });
});
