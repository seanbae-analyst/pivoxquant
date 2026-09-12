import { describe, it, expect } from "vitest";
import { safeNext } from "@/lib/safe-next";

describe("safeNext", () => {
  it("keeps same-origin paths", () => {
    expect(safeNext("/portfolio")).toBe("/portfolio");
    expect(safeNext("/journal?tab=1#x")).toBe("/journal?tab=1#x");
  });
  it("falls back for anything that could leave the site", () => {
    for (const bad of [
      "https://evil.example",
      "//evil.example/path",
      "/\\evil.example",
      "javascript:alert(1)",
      "mirror",
      "/\u0000x",
      "",
      null,
      undefined,
    ]) {
      expect(safeNext(bad as string | null | undefined)).toBe("/mirror");
    }
  });
});
