import { describe, expect, it } from "vitest";
import { initials } from "../initials";

describe("initials", () => {
  it("takes one letter per word for multi-word names", () => {
    expect(initials("Sean Bae")).toBe("SB");
    expect(initials("  sean   bae  ")).toBe("SB");
    expect(initials("Ada Byron Lovelace")).toBe("AB");
  });

  it("takes the first two characters of a single-token Latin name", () => {
    expect(initials("sean")).toBe("SE");
  });

  it("shows a 2–3 syllable Korean name whole", () => {
    // CEO 2026-10-22: "배상현", not "배상". Regression kept: "게스트" (the
    // logged-out label) once rendered as a lone "게".
    expect(initials("배상현")).toBe("배상현");
    expect(initials("게스트")).toBe("게스트");
    expect(initials("  배상현 ")).toBe("배상현");
    expect(initials("이준")).toBe("이준");
    // Longer or spaced Korean falls back to the old rule.
    expect(initials("남궁민수진")).toBe("남궁");
    expect(initials("데모 투자자")).toBe("데투");
  });

  it("falls back to the e-mail, then to PQ", () => {
    expect(initials(undefined, "seanbae@example.com")).toBe("SE");
    expect(initials("", "seanbae@example.com")).toBe("SE");
    expect(initials(null, null)).toBe("PQ");
    expect(initials("   ", "  ")).toBe("PQ");
  });
});
