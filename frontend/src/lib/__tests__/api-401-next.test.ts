/**
 * 세션 만료 401 → /login 리다이렉트가 원래 경로를 ?next= 로 싣는다 (2026-09-29).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { apiFetch, ApiError } from "@/lib/api";

const hrefSet = vi.fn();
const realLocation = window.location;

beforeEach(() => {
  hrefSet.mockClear();
  // jsdom 은 실제 내비게이션을 못 하므로 href 대입을 가로챈다.
  Object.defineProperty(window, "location", {
    configurable: true,
    value: {
      origin: "http://localhost",
      pathname: "/journal",
      search: "?id=5",
      hash: "",
      set href(v: string) {
        hrefSet(v);
      },
      get href() {
        return "http://localhost/journal?id=5";
      },
      assign: hrefSet,
      replace: hrefSet,
    },
  });
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ code: "SESSION_EXPIRED" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
});

afterEach(() => {
  Object.defineProperty(window, "location", { configurable: true, value: realLocation });
  window.localStorage.clear();
  vi.unstubAllGlobals();
});

describe("apiFetch — SESSION_EXPIRED redirect", () => {
  it("sends a fresh guest to /login?next=<original path>", async () => {
    await expect(apiFetch("/api/journal")).rejects.toBeInstanceOf(ApiError);
    expect(hrefSet).toHaveBeenCalledWith("/login?next=%2Fjournal%3Fid%3D5");
  });

  it("keeps expired=1 for a device that held a session", async () => {
    window.localStorage.setItem("pq_had_session", "1");
    await expect(apiFetch("/api/journal")).rejects.toBeInstanceOf(ApiError);
    expect(hrefSet).toHaveBeenCalledWith("/login?expired=1&next=%2Fjournal%3Fid%3D5");
  });
});
