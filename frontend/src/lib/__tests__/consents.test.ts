import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock the network layer. consents.ts calls apiFetch(API.consents.*, ...)
// and instanceof-checks ApiError in the GET helpers, so we provide a real
// subclass for the latter.
vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message = "") {
      super(message);
      this.status = status;
    }
  },
}));

import { apiFetch, ApiError } from "@/lib/api";
import { API } from "@/lib/endpoints";
import {
  CONSENT_STORAGE_KEY,
  flushPendingMarketingConsent,
  flushPendingCrossBorderConsent,
  recordMarketingConsent,
  revokeMarketingConsent,
  fetchMarketingConsent,
  serverHasRequiredConsents,
} from "@/lib/consents";

const mockedFetch = vi.mocked(apiFetch);

beforeEach(() => {
  mockedFetch.mockReset();
  window.localStorage.clear();
});

describe("flushPendingMarketingConsent — the signup→backend promotion leg", () => {
  it("POSTs to the marketing endpoint when the staged snapshot opted in", async () => {
    mockedFetch.mockResolvedValue({ ok: true } as never);

    const result = await flushPendingMarketingConsent({ marketing: true });

    expect(result).toBe(true);
    expect(mockedFetch).toHaveBeenCalledTimes(1);
    expect(mockedFetch).toHaveBeenCalledWith(API.consents.marketing, {
      method: "POST",
    });
  });

  it("does NOT POST when marketing was declined (§50 default-deny)", async () => {
    const result = await flushPendingMarketingConsent({ marketing: false });

    expect(result).toBe(true); // attempted-handling = true, but no network
    expect(mockedFetch).not.toHaveBeenCalled();
  });

  it("returns false and sends nothing when there is no staged snapshot", async () => {
    const result = await flushPendingMarketingConsent(null);

    expect(result).toBe(false);
    expect(mockedFetch).not.toHaveBeenCalled();
  });

  it("returns false on backend failure (never throws, so the caller retries)", async () => {
    // Contract (2026-05-23): a failed flush must NOT throw (post-signup UX
    // is never blocked) but must resolve to FALSE so the dashboard layout
    // keeps the staged snapshot and retries on the next mount instead of
    // silently dropping the opt-in the user gave at signup.
    mockedFetch.mockRejectedValue(new ApiError(401, "unauthorized"));

    await expect(
      flushPendingMarketingConsent({ marketing: true }),
    ).resolves.toBe(false);
    expect(mockedFetch).toHaveBeenCalledTimes(1);
  });

  it("falls back to reading the localStorage staging slot when no override given", async () => {
    mockedFetch.mockResolvedValue({ ok: true } as never);
    window.localStorage.setItem(
      CONSENT_STORAGE_KEY,
      JSON.stringify({ marketing: true, cross_border: true }),
    );

    const result = await flushPendingMarketingConsent();

    expect(result).toBe(true);
    expect(mockedFetch).toHaveBeenCalledWith(API.consents.marketing, {
      method: "POST",
    });
  });
});

describe("flushPendingCrossBorderConsent — PIPA §28-8 promotion leg", () => {
  it("POSTs to the cross-border endpoint when staged snapshot opted in", async () => {
    mockedFetch.mockResolvedValue({ ok: true } as never);

    const result = await flushPendingCrossBorderConsent({ cross_border: true });

    expect(result).toBe(true);
    expect(mockedFetch).toHaveBeenCalledWith(API.consents.crossBorder, {
      method: "POST",
    });
  });

  it("returns false on backend failure (caller keeps snapshot to retry)", async () => {
    mockedFetch.mockRejectedValue(new ApiError(401, "unauthorized"));
    await expect(
      flushPendingCrossBorderConsent({ cross_border: true }),
    ).resolves.toBe(false);
  });

  it("does NOT POST when cross-border consent absent", async () => {
    const result = await flushPendingCrossBorderConsent({ cross_border: false });

    expect(result).toBe(true);
    expect(mockedFetch).not.toHaveBeenCalled();
  });

  // 2026-09-29 — oauth-finalize already stamped cross_border_consent_at in
  // its own transaction. A later re-POST from a leftover snapshot would move
  // that timestamp off the real consent moment (or undo a revocation).
  it("does NOT re-POST when the server already recorded a cross-border consent", async () => {
    const result = await flushPendingCrossBorderConsent(
      { cross_border: true },
      { serverRecorded: true },
    );

    expect(result).toBe(true); // end-state reached → caller may clear snapshot
    expect(mockedFetch).not.toHaveBeenCalled();
  });

  it("still POSTs for a legacy user with no server-side record", async () => {
    mockedFetch.mockResolvedValue({ ok: true } as never);
    const result = await flushPendingCrossBorderConsent(
      { cross_border: true },
      { serverRecorded: false },
    );
    expect(result).toBe(true);
    expect(mockedFetch).toHaveBeenCalledWith(API.consents.crossBorder, {
      method: "POST",
    });
  });
});

describe("serverHasRequiredConsents — server is the SoT for 'already consented'", () => {
  it("true after oauth-finalize (age confirmed + cross-border recorded)", () => {
    expect(
      serverHasRequiredConsents({
        age_confirmation_required: false,
        cross_border_consent_recorded: true,
      }),
    ).toBe(true);
  });

  it("false for a legacy account with no cross-border record", () => {
    expect(
      serverHasRequiredConsents({
        age_confirmation_required: false,
        cross_border_consent_recorded: false,
      }),
    ).toBe(false);
  });

  it("false while the age self-declaration is still pending", () => {
    expect(
      serverHasRequiredConsents({
        age_confirmation_required: true,
        cross_border_consent_recorded: true,
      }),
    ).toBe(false);
  });

  it("false when the backend does not send the flag (older deploy) or no user", () => {
    expect(serverHasRequiredConsents({ age_confirmation_required: false })).toBe(false);
    expect(serverHasRequiredConsents(null)).toBe(false);
  });
});

describe("settings-toggle helpers hit the right method", () => {
  it("recordMarketingConsent POSTs", async () => {
    mockedFetch.mockResolvedValue({
      ok: true,
      opted_in: true,
      marketing_consent_at: "2026-05-20T00:00:00Z",
      marketing_consent_revoked_at: null,
    } as never);

    const res = await recordMarketingConsent();

    expect(res.opted_in).toBe(true);
    expect(mockedFetch).toHaveBeenCalledWith(API.consents.marketing, {
      method: "POST",
    });
  });

  it("revokeMarketingConsent DELETEs", async () => {
    mockedFetch.mockResolvedValue({
      ok: true,
      opted_in: false,
      marketing_consent_at: "2026-05-20T00:00:00Z",
      marketing_consent_revoked_at: "2026-05-20T01:00:00Z",
    } as never);

    const res = await revokeMarketingConsent();

    expect(res.opted_in).toBe(false);
    expect(mockedFetch).toHaveBeenCalledWith(API.consents.marketing, {
      method: "DELETE",
    });
  });

  it("fetchMarketingConsent returns null on 401 (unauthenticated)", async () => {
    mockedFetch.mockRejectedValue(new ApiError(401, "unauthorized"));

    const res = await fetchMarketingConsent();

    expect(res).toBeNull();
  });
});
