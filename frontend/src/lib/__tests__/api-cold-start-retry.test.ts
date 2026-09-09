/**
 * A Render cold start must not read as an outage.
 *
 * Measured against production 2026-09-07: the backend answers /api/health in
 * 0.52s warm and 43.9s cold, because the free plan spins the service down
 * after 15 idle minutes. DEFAULT_TIMEOUT_MS is 30s — between those two
 * numbers. Every visitor arriving after an idle gap therefore had their first
 * request aborted at 30s and saw ApiError(408) while the server was merely
 * still booting. On a closed beta with almost no traffic, that is most
 * visitors, and nothing tested it.
 *
 * These pin the retry AND its limits. The limits matter more than the retry:
 * replaying a POST that timed out could double-create a record the server
 * already accepted.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { apiFetch, ApiError } from "@/lib/api";

const ok = (body: unknown = { ok: true }) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });

/** What a cold start looks like to fetch(): our AbortController fires. */
function timeoutOnce() {
  return Promise.reject(
    new DOMException("Request timeout", "TimeoutError"),
  );
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("apiFetch — cold-start retry", () => {
  it("retries a GET once when the first attempt times out", async () => {
    fetchMock.mockImplementationOnce(timeoutOnce).mockResolvedValueOnce(ok({ db: "ok" }));
    await expect(apiFetch("/api/health")).resolves.toEqual({ db: "ok" });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("gives up after the second timeout — a cold start is one wake-up, not a loop", async () => {
    fetchMock.mockImplementation(timeoutOnce);
    await expect(apiFetch("/api/health")).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not retry a POST — a timed-out write may already have applied", async () => {
    fetchMock.mockImplementation(timeoutOnce);
    await expect(
      apiFetch("/api/pre-trade/reflections", { method: "POST", body: "{}" }),
    ).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it.each(["PUT", "PATCH", "DELETE"])("does not retry %s", async (method) => {
    fetchMock.mockImplementation(timeoutOnce);
    await expect(apiFetch("/api/x", { method })).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("does not retry when the caller set its own timeout budget", async () => {
    fetchMock.mockImplementation(timeoutOnce);
    await expect(
      apiFetch("/api/health", { timeoutMs: 1_000 }),
    ).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("does not retry a caller-cancelled request", async () => {
    // Route change / unmount. The caller does not want this request at all;
    // firing a second one would be the opposite of what they asked for.
    const ac = new AbortController();
    ac.abort();
    fetchMock.mockImplementation(() =>
      Promise.reject(new DOMException("Aborted", "AbortError")),
    );
    await expect(apiFetch("/api/health", { signal: ac.signal })).rejects.toBeTruthy();
    expect(fetchMock.mock.calls.length).toBeLessThanOrEqual(1);
  });

  it("leaves a non-timeout failure alone — a 500 is not a cold start", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ error: "boom" }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(apiFetch("/api/health")).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("does not retry when the first attempt already succeeded", async () => {
    fetchMock.mockResolvedValueOnce(ok());
    await apiFetch("/api/health");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
