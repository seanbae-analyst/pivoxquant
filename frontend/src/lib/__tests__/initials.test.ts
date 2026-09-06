import { describe, expect, it } from "vitest";
import { initials } from "../initials";

describe("initials", () => {
  it("takes one letter per word for multi-word names", () => {
    expect(initials("Sean Bae")).toBe("SB");
    expect(initials("  sean   bae  ")).toBe("SB");
    expect(initials("Ada Byron Lovelace")).toBe("AB");
  });

  it("takes the first two characters of a single-token name", () => {
    // Regression: "게스트" (the logged-out label) rendered as a lone "게".
    expect(initials("게스트")).toBe("게스");
    expect(initials("배상현")).toBe("배상");
    expect(initials("sean")).toBe("SE");
  });

  it("falls back to the e-mail, then to PQ", () => {
    expect(initials(undefined, "seanbae@example.com")).toBe("SE");
    expect(initials("", "seanbae@example.com")).toBe("SE");
    expect(initials(null, null)).toBe("PQ");
    expect(initials("   ", "  ")).toBe("PQ");
  });
});
