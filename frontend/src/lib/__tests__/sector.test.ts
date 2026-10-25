import { describe, expect, it } from "vitest";
import { sectorLabel } from "@/lib/sector";

describe("sectorLabel", () => {
  it("shows vendor sector names in Korean, merging the two spellings", () => {
    expect(sectorLabel("Technology")).toBe("기술");
    expect(sectorLabel("Consumer Cyclical")).toBe("경기소비재");
    expect(sectorLabel("Consumer Discretionary")).toBe("경기소비재");
    expect(sectorLabel("HEALTHCARE")).toBe("헬스케어");
  });

  it("keeps an unknown name as given and maps empty to empty", () => {
    expect(sectorLabel("반도체")).toBe("반도체");
    expect(sectorLabel(null)).toBe("");
  });
});
