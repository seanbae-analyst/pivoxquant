import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

import { track, getAnonId } from "@/lib/track";
import { API } from "@/lib/endpoints";

describe("track() funnel telemetry", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    localStorage.clear();
    fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("POSTs to /api/track with the event in the body", async () => {
    const ok = await track("landing_view");
    expect(ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(API.viral.track);
    expect(init.method).toBe("POST");
    expect(init.keepalive).toBe(true);
    const body = JSON.parse(init.body);
    expect(body.event).toBe("landing_view");
  });

  it("clips channel ≤40 and ref_code ≤16", async () => {
    await track("share_clicked", {
      channel: "x".repeat(60),
      refCode: "y".repeat(40),
    });
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.channel).toHaveLength(40);
    expect(body.ref_code).toHaveLength(16);
  });

  it("clamps meta to ≤12 keys and ≤200-char string values", async () => {
    const meta: Record<string, string> = {};
    for (let i = 0; i < 20; i += 1) meta[`k${i}`] = "v";
    meta.k0 = "z".repeat(300);
    await track("artifact_opened", { meta });
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(Object.keys(body.meta).length).toBeLessThanOrEqual(12);
    expect((body.meta.k0 as string).length).toBeLessThanOrEqual(200);
  });

  it("attaches a persisted anon_id by default and reuses it", async () => {
    await track("landing_view");
    const first = JSON.parse(fetchMock.mock.calls[0][1].body).anon_id;
    expect(first).toBeTruthy();
    await track("landing_view");
    const second = JSON.parse(fetchMock.mock.calls[1][1].body).anon_id;
    expect(second).toBe(first);
    expect(getAnonId()).toBe(first);
  });

  it("omits anon_id when includeAnonId is false", async () => {
    await track("signup", { includeAnonId: false });
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.anon_id).toBeUndefined();
  });

  it("never throws on network failure — resolves false", async () => {
    fetchMock.mockRejectedValueOnce(new Error("offline"));
    await expect(track("landing_view")).resolves.toBe(false);
  });
});
