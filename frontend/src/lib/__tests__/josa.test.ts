import { describe, expect, it } from "vitest";
import { josa } from "@/lib/josa";

describe("josa", () => {
  it("picks 이/가 by the final consonant", () => {
    expect(josa("섹터 분산", "이/가")).toBe("섹터 분산이");
    expect(josa("매매 회전율", "이/가")).toBe("매매 회전율이");
    expect(josa("보유기간 편차", "이/가")).toBe("보유기간 편차가");
  });

  it("uses 로 after ㄹ and no final consonant, 으로 otherwise", () => {
    expect(josa("거울", "으로/로")).toBe("거울로");
    expect(josa("기록", "으로/로")).toBe("기록으로");
    expect(josa("포트폴리오", "으로/로")).toBe("포트폴리오로");
  });

  it("falls back to the no-final form for non-Hangul endings", () => {
    expect(josa("AAPL", "을/를")).toBe("AAPL를");
    expect(josa("", "은/는")).toBe("는");
  });
});
