import { describe, it, expect, beforeEach } from "vitest";
import {
  __resetScrollMemoryForTests,
  nodePath,
  persistScrollMemory,
  readRouteScroll,
  rememberInnerScroll,
  rememberWindowScroll,
  resolveNodePath,
} from "@/lib/scroll-memory";

beforeEach(() => {
  window.sessionStorage.clear();
  __resetScrollMemoryForTests();
});

describe("scroll memory", () => {
  it("keeps each route's window scroll and inner containers", () => {
    rememberWindowScroll("/journal", 900.4);
    rememberInnerScroll("/portfolio", "0.1.2", 340, 0);
    rememberWindowScroll("/mirror", 0);
    expect(readRouteScroll("/journal")).toEqual({ y: 900, inner: {} });
    expect(readRouteScroll("/portfolio")?.inner["0.1.2"]).toEqual({ top: 340, left: 0 });
    expect(readRouteScroll("/mirror")?.y).toBe(0);
    expect(readRouteScroll("/settings")).toBeNull();
  });

  it("forgets a container scrolled back to its origin", () => {
    rememberInnerScroll("/portfolio", "0.1", 120, 0);
    rememberInnerScroll("/portfolio", "0.1", 0, 0);
    expect(readRouteScroll("/portfolio")?.inner).toEqual({});
  });

  it("survives a reload through sessionStorage", () => {
    rememberWindowScroll("/journal", 640);
    persistScrollMemory();
    __resetScrollMemoryForTests();
    expect(readRouteScroll("/journal")?.y).toBe(640);
  });

  it("works without storage", () => {
    const original = window.sessionStorage.getItem;
    window.sessionStorage.getItem = () => {
      throw new Error("blocked");
    };
    try {
      __resetScrollMemoryForTests();
      rememberWindowScroll("/mirror", 50);
      expect(readRouteScroll("/mirror")?.y).toBe(50);
    } finally {
      window.sessionStorage.getItem = original;
    }
  });
});

describe("nodePath", () => {
  it("round-trips an element path under a root", () => {
    const root = document.createElement("div");
    root.innerHTML = "<section><p></p><div><span id='t'></span></div></section>";
    const t = root.querySelector("#t") as Element;
    const path = nodePath(root, t);
    expect(path).toBe("0.1.0");
    expect(resolveNodePath(root, path!)).toBe(t);
    expect(nodePath(root, document.createElement("i"))).toBeNull();
    expect(resolveNodePath(root, "0.9")).toBeNull();
  });
});
