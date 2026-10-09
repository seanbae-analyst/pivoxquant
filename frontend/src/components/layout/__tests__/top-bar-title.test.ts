/** Phone app bar names the screen (2026-10-07). */
import { describe, it, expect } from "vitest";
import { screenTitle, subScreen } from "../top-bar";

describe("screenTitle", () => {
  it("maps each dashboard route, including sub-routes", () => {
    expect(screenTitle("/mirror")).toBe("거울");
    expect(screenTitle("/pre-trade")).toBe("멈춤");
    expect(screenTitle("/journal")).toBe("기록");
    expect(screenTitle("/journal/import")).toBe("기록");
    expect(screenTitle("/portfolio")).toBe("포트폴리오");
    expect(screenTitle("/settings")).toBe("설정");
    expect(screenTitle("/support/inbox/3")).toBe("문의");
  });
  it("no title for unknown or look-alike routes", () => {
    expect(screenTitle(null)).toBeNull();
    expect(screenTitle("/journalism")).toBeNull();
    expect(screenTitle("/")).toBeNull();
  });
});

describe("subScreen (phone app bar back + title)", () => {
  it("names sub-screens and where back goes", () => {
    expect(subScreen("/journal/import", null)).toMatchObject({ title: "체결 가져오기", parent: "/journal" });
    expect(subScreen("/support/inbox/42", null)).toMatchObject({ title: "문의 내용", parent: "/support/inbox" });
    expect(subScreen("/settings", "notifications")).toMatchObject({ title: "알림", parent: "/settings", pane: "notifications" });
  });
  it("top-level screens have no back", () => {
    for (const p of ["/mirror", "/pre-trade", "/journal", "/portfolio", "/settings", "/support/inbox", "/support/contact"]) {
      expect(subScreen(p, null)).toBeNull();
    }
    expect(subScreen("/mirror", "account")).toBeNull();
    expect(subScreen(null, null)).toBeNull();
  });
});
