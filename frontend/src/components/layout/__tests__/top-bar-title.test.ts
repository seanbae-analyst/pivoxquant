/** Phone app bar names the screen (2026-10-07). */
import { describe, it, expect } from "vitest";
import { screenTitle } from "../top-bar";

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
