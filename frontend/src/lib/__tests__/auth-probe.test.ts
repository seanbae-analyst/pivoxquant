// frontend/src/lib/__tests__/auth-probe.test.ts
// -----------------------------------------------------------------
// Regression guard for the 2026-09-01 redirect ping-pong.
//
// `meFetcher` used to answer EVERY failure with `{ authenticated: false }`,
// conflating "the server says you are not signed in" with "we could not
// reach the server". The second is not something the client knows, and
// asserting it logs a signed-in user out: the (dashboard) guard reads
// `user == null` and replaces to /login, the login page's own guard sees the
// next (successful) probe and replaces back, and the two alternate forever.
//
// Reproduced by exhausting the backend's 100/min limit locally — /login and
// /portfolio alternated indefinitely and the app never painted past its
// loading splash.
//
// The contract these tests pin: ONLY a 401/403 may resolve to
// "unauthenticated". Every other failure must throw, so SWR's
// keepPreviousData holds the last known session instead of dropping it.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const apiFetch = vi.fn();

vi.mock("../api", () => ({
  apiFetch: (...args: unknown[]) => apiFetch(...args),
  ApiError: class ApiError extends Error {
    constructor(public status: number, message: string) {
      super(message);
    }
  },
}));

// The module pulls in next/navigation + SWR at import time; the fetcher
// itself needs neither, so a bare import is enough once ../api is mocked.
const loadModule = async () => await import("../auth");

beforeEach(() => {
  apiFetch.mockReset();
  vi.useRealTimers();
});

afterEach(() => {
  vi.resetModules();
});

describe("meFetcher — what counts as 'signed out'", () => {
  it("resolves to unauthenticated on a 401 (the server actually said so)", async () => {
    const { meFetcher, AuthUnknownError } = await loadModule();
    const { ApiError } = await import("../api");
    apiFetch.mockRejectedValueOnce(new ApiError(401, "unauthorized"));

    const res = await meFetcher("/api/auth/me");

    expect(res).toEqual({ authenticated: false });
    expect(AuthUnknownError).toBeDefined();
  });

  it("resolves to unauthenticated on a 403", async () => {
    const { meFetcher } = await loadModule();
    const { ApiError } = await import("../api");
    apiFetch.mockRejectedValueOnce(new ApiError(403, "forbidden"));

    await expect(meFetcher("/api/auth/me")).resolves.toEqual({
      authenticated: false,
    });
  });

  it("throws on a 429 rather than claiming the user is signed out", async () => {
    const { meFetcher, AuthUnknownError } = await loadModule();
    const { ApiError } = await import("../api");
    apiFetch.mockRejectedValueOnce(new ApiError(429, "rate limited"));

    await expect(meFetcher("/api/auth/me")).rejects.toBeInstanceOf(
      AuthUnknownError,
    );
  });

  it("throws on a 502 — an unreachable backend is not a logout", async () => {
    const { meFetcher, AuthUnknownError } = await loadModule();
    const { ApiError } = await import("../api");
    apiFetch.mockRejectedValueOnce(new ApiError(502, "bad gateway"));

    await expect(meFetcher("/api/auth/me")).rejects.toBeInstanceOf(
      AuthUnknownError,
    );
  });

  it("throws on a network error / abort", async () => {
    const { meFetcher, AuthUnknownError } = await loadModule();
    apiFetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    await expect(meFetcher("/api/auth/me")).rejects.toBeInstanceOf(
      AuthUnknownError,
    );
  });

  it("passes a successful response straight through", async () => {
    const { meFetcher } = await loadModule();
    const payload = { authenticated: true, user: { id: 1 } };
    apiFetch.mockResolvedValueOnce(payload);

    await expect(meFetcher("/api/auth/me")).resolves.toEqual(payload);
  });
});
