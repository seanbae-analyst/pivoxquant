import { describe, expect, it } from "vitest";
import { renderAppendix, reportFilename, reportHeader, slugify, verdictCounts } from "../report";
import type { Claim, ClaimVerdict, Report, Source } from "../types";

const NUM = { metric: null, value: null, unit: null, year: null, geography: null };

const sources: Source[] = [
  { url: "https://a.example", title: "A", pageAge: null },
  { url: "https://b.example", title: "B", pageAge: "3 days ago" },
];
const claims: Claim[] = [
  { id: "C1.1", subQuestion: "q1", text: "값은 | 12% 다", evidence: "표 3", sourceUrls: ["https://a.example"], confidence: "high", metric: "침투율", value: "12", unit: "%", year: "2025", geography: "한국" },
  { id: "C1.2", subQuestion: "q1", text: "둘째", evidence: "", sourceUrls: [], confidence: "low", ...NUM },
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
    // 수치 주장만 수치표에 오른다
    expect(md).toContain("## 부록 B — 수치표");
    expect(md).toContain("| C1.1 | 침투율 | 12 | % | 2025 | 한국 | 기각 | [1] |");
    expect(md).not.toContain("| C1.2 | — |");
    expect(md).toContain("## 부록 C — 출처");
  });
  it("수치 주장이 없으면 수치표를 만들지 않는다", () => {
    const md = renderAppendix([claims[1]], [verdicts[1]], sources);
    expect(md).not.toContain("수치표");
    expect(md).toContain("## 부록 C — 출처");
  });
  it("머리말에 브리프의 유형·범위·배경을 쓴다", () => {
    const report: Report = {
      id: "r", question: "q", createdAt: "2026-09-17T00:00:00.000Z", model: "m", plan: { framing: "", subQuestions: [], killCriteria: [] },
      claims: [], verdicts: [], sources, markdown: "",
      brief: { domain: "consulting", type: "market_sizing", topic: "반려동물 보험", geography: "한국", timeframe: "2024~2026", context: "신규 진입 검토" },
    };
    const h = reportHeader(report);
    expect(h).toContain("> 분야: 컨설팅 · 유형: 시장 규모 · 주제: 반려동물 보험 · 지역 한국 · 기간 2024~2026");
    expect(h).toContain("> 의뢰 배경: 신규 진입 검토");
    expect(reportHeader({ ...report, brief: { ...report.brief, geography: "", timeframe: "", context: "" } })).not.toContain("의뢰 배경");
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
