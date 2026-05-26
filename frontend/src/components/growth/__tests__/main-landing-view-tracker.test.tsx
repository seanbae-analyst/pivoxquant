/**
 * <MainLandingViewTracker /> tests — main-landing channel attribution.
 *
 * Covers the acquisition-tracking gap fix:
 *   1. utm_source is read into the `channel` arg of track("landing_view").
 *   2. utm_medium is the fallback when utm_source is absent.
 *   3. ?ref=<code> is forwarded as refCode; surface is always "landing".
 *   4. The fired useRef guard prevents a duplicate fire on re-render.
 *
 * track() is mocked so the test never touches `fetch` and asserts purely on
 * the call contract. window.location.search is stubbed per case.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render } from "@testing-library/react";

import { track } from "@/lib/track";
import { MainLandingViewTracker } from "../main-landing-view-tracker";

vi.mock("@/lib/track", () => ({
  track: vi.fn().mockResolvedValue(true),
}));

const trackMock = vi.mocked(track);

function setSearch(search: string) {
  Object.defineProperty(window, "location", {
    value: { ...window.location, search },
    writable: true,
    configurable: true,
  });
}

describe("MainLandingViewTracker", () => {
  beforeEach(() => {
    trackMock.mockClear();
  });

  afterEach(() => {
    setSearch("");
  });

  it("maps utm_source to the channel arg", () => {
    setSearch("?utm_source=naver_cafe");
    render(<MainLandingViewTracker />);
    expect(trackMock).toHaveBeenCalledTimes(1);
    const [event, opts] = trackMock.mock.calls[0];
    expect(event).toBe("landing_view");
    expect(opts?.channel).toBe("naver_cafe");
    expect(opts?.meta).toEqual({ surface: "landing" });
  });

  it("falls back to utm_medium when utm_source is absent", () => {
    setSearch("?utm_medium=email");
    render(<MainLandingViewTracker />);
    expect(trackMock.mock.calls[0][1]?.channel).toBe("email");
  });

  it("prefers utm_source over utm_medium when both present", () => {
    setSearch("?utm_source=naver_cafe&utm_medium=email");
    render(<MainLandingViewTracker />);
    expect(trackMock.mock.calls[0][1]?.channel).toBe("naver_cafe");
  });

  it("forwards ?ref as refCode and leaves channel undefined when no UTM", () => {
    setSearch("?ref=abc123");
    render(<MainLandingViewTracker />);
    const opts = trackMock.mock.calls[0][1];
    expect(opts?.refCode).toBe("abc123");
    expect(opts?.channel).toBeUndefined();
  });

  it("fires exactly once across re-renders (fired useRef guard)", () => {
    setSearch("?utm_source=naver_cafe");
    const { rerender } = render(<MainLandingViewTracker />);
    rerender(<MainLandingViewTracker />);
    rerender(<MainLandingViewTracker />);
    expect(trackMock).toHaveBeenCalledTimes(1);
  });
});
