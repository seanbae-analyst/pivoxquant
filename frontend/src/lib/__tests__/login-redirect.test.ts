/**
 * 로그인 후 딥링크 (2026-09-29).
 *
 * 백엔드는 `/api/auth/{google,kakao}?next=` 를 받아 서명된 state 에 싣고
 * 로그인 뒤 그리로 보낸다(routes/auth.py::_safe_next). 프론트는 그걸 한 번도
 * 보내지 않아, 딥링크로 들어온 비로그인 유저는 로그인 후 늘 /mirror 에 떨어졌다.
 * 이 헬퍼들이 (1) /login 으로 보낼 때 원래 경로를 싣고 (2) 로그인 화면에서
 * 그 값을 걸러 OAuth 앵커에 붙인다.
 */
import { describe, it, expect, afterEach } from "vitest";
import {
  loginNextPath,
  loginHref,
  oauthHref,
  currentLocationPath,
} from "@/lib/login-redirect";

describe("loginNextPath", () => {
  it("keeps same-origin paths with their query", () => {
    expect(loginNextPath("/journal")).toBe("/journal");
    expect(loginNextPath("/portfolio?tab=trades")).toBe("/portfolio?tab=trades");
  });

  it("rejects anything that could leave the site or loop back to login", () => {
    for (const bad of [
      "https://evil.example",
      "//evil.example/x",
      "/\\evil.example",
      "javascript:alert(1)",
      "/redirect?to=https://evil.example",
      "journal",
      "/login",
      "/login?expired=1",
      "/login/",
      "/signup",
      "/signup/oauth-finalize",
      "/",
      "",
      null,
      undefined,
    ]) {
      expect(loginNextPath(bad as string | null | undefined)).toBeNull();
    }
  });
});

describe("loginHref", () => {
  it("is plain /login without a usable next", () => {
    expect(loginHref(null)).toBe("/login");
    expect(loginHref("/login")).toBe("/login");
    expect(loginHref("https://evil.example")).toBe("/login");
  });

  it("carries the original path+query, encoded", () => {
    expect(loginHref("/journal?id=3&x=1")).toBe(
      "/login?next=%2Fjournal%3Fid%3D3%26x%3D1",
    );
  });

  it("keeps the expired banner flag alongside next", () => {
    expect(loginHref("/portfolio", { expired: true })).toBe(
      "/login?expired=1&next=%2Fportfolio",
    );
    expect(loginHref(null, { expired: true })).toBe("/login?expired=1");
  });
});

describe("oauthHref", () => {
  it("appends an encoded next to the OAuth start route", () => {
    expect(oauthHref("/api/auth/google", "/journal?id=3")).toBe(
      "/api/auth/google?next=%2Fjournal%3Fid%3D3",
    );
  });

  it("leaves the route untouched when next is unsafe or absent", () => {
    expect(oauthHref("/api/auth/kakao", null)).toBe("/api/auth/kakao");
    expect(oauthHref("/api/auth/kakao", "//evil.example")).toBe("/api/auth/kakao");
  });

  it("appends with & when the route already has a query", () => {
    expect(oauthHref("/api/auth/google?ref=AB12", "/journal")).toBe(
      "/api/auth/google?ref=AB12&next=%2Fjournal",
    );
  });
});

describe("currentLocationPath", () => {
  afterEach(() => {
    window.history.replaceState(null, "", "/");
  });

  it("reads pathname + search from window.location", () => {
    window.history.replaceState(null, "", "/journal?id=7");
    expect(currentLocationPath()).toBe("/journal?id=7");
  });
});
