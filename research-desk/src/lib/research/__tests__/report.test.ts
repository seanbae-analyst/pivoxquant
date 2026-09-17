import { describe, expect, it } from "vitest";
import { renderAppendix, reportFilename, slugify, verdictCounts } from "../report";
import type { Claim, ClaimVerdict, Source } from "../types";

const sources: Source[] = [
  { url: "https://a.example", title: "A", pageAge: null },
  { url: "https://b.example", title: "B", pageAge: "3 days ago" },
];
const claims: Claim[] = [
  { id: "C1.1", subQuestion: "q1", text: "값은 | 12% 다", evidence: "표 3", sourceUrls: ["https://a.example"], confidence: "high" },
  { id: "C1.2", subQuestion: "q1", text: "둘째", evidence: "", sourceUrls: [], confidence: "low" },
];
const verdicts: ClaimVerdict[] = [
  { claimId: "C1.1", verdict: "killed", reason: "최신 자료가 다르다", counterSourceUrls: ["https://b.example"] },
  { claimId: "C1.2", verdict: "open", reason: "출처 없음", counterSourceUrls: [] },
];

describe("renderAppendix", () => {
  it("판정 집계, 표 이스케이프, 출처 번호를 낸다", () => {
    const md = renderAppendix(claims, verdicts, sources);
    expect(md).toContain("유지 0 · 기각 1 · 미결 1 (주장 2건)");
    expect(md).toContain("| C1.1 | 기각 | 값은 \\| 12% 다 | [1] | [2] | 최신 자료가 다르다 |");
    expect(md).toContain("| C1.2 | 미결 | 둘째 | — | — | 출처 없음 |");
    expect(md).toContain("2. [B](https://b.example) — 3 days ago");
  });
  it("주장·출처가 없을 때도 깨지지 않는다", () => {
    const md = renderAppendix([], [], []);
    expect(md).toContain("검증 가능한 주장을 추출하지 못했다.");
    expect(md).toContain("열어 본 출처가 없다.");
  });
});

describe("filenames", () => {
  it("한글 질문도 슬러그가 된다", () => {
    expect(slugify("한국 개인투자자는 기록을 하는가?")).toBe("한국-개인투자자는-기록을-하는가");
    expect(slugify("???")).toBe("report");
    expect(reportFilename({ question: "A b", createdAt: "2026-09-17T10:00:00.000Z" })).toBe("2026-09-17_a-b.md");
  });
  it("verdictCounts", () => {
    expect(verdictCounts(verdicts)).toEqual({ confirmed: 0, killed: 1, open: 1 });
  });
});
