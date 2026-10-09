import { describe, it, expect } from "vitest";
import { classifyRouteChange, shouldRestoreScroll, isTopLevel } from "@/lib/route-motion";

describe("classifyRouteChange", () => {
  it("bottom-nav destination to destination is a tab fade", () => {
    expect(classifyRouteChange("/mirror", "/journal", false)).toBe("tab");
    expect(classifyRouteChange("/journal/import", "/mirror", false)).toBe("tab");
    expect(classifyRouteChange("/portfolio", "/settings", true)).toBe("tab");
  });
  it("deeper inside a section is a push, back out of it a pop", () => {
    expect(classifyRouteChange("/journal", "/journal/import", false)).toBe("push");
    expect(classifyRouteChange("/support/inbox", "/support/inbox/7", false)).toBe("push");
    expect(classifyRouteChange("/journal/import", "/journal", false)).toBe("pop");
    expect(classifyRouteChange("/support/inbox/7", "/support/inbox", true)).toBe("pop");
  });
  it("a card linking deep into another section is a push", () => {
    expect(classifyRouteChange("/pre-trade", "/journal/import", false)).toBe("push");
  });
  it("history back into a deeper screen still reads as back", () => {
    expect(classifyRouteChange("/mirror", "/journal/import", true)).toBe("pop");
  });
  it("same path or first render does not move", () => {
    expect(classifyRouteChange(null, "/mirror", false)).toBe("none");
    expect(classifyRouteChange("/mirror", "/mirror", true)).toBe("none");
  });
});

describe("shouldRestoreScroll", () => {
  it("restores the remembered tab roots on any arrival", () => {
    for (const p of ["/mirror", "/journal", "/portfolio", "/settings"]) {
      expect(shouldRestoreScroll(p, false)).toBe(true);
    }
  });
  it("starts /pre-trade (a flow) and drill-downs at the top unless going back", () => {
    expect(shouldRestoreScroll("/pre-trade", false)).toBe(false);
    expect(shouldRestoreScroll("/journal/import", false)).toBe(false);
    expect(shouldRestoreScroll("/journal/import", true)).toBe(true);
  });
  it("isTopLevel", () => {
    expect(isTopLevel("/journal")).toBe(true);
    expect(isTopLevel("/journal/import?tab=image")).toBe(false);
  });
});
