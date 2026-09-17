import { describe, expect, it } from "vitest";
import { chunkText, extractMain, splitForCitation } from "../text";

describe("extractMain", () => {
  it("nav·script 를 버리고 main 의 제목·문단·목록만 남긴다", () => {
    const html = `<html><head><title>설치 가이드 | Docs</title><script>x()</script></head>
      <body><nav><a>홈</a></nav><main><h1>설치</h1><p>요구사항은 다음과 같다.</p><ul><li><p>Java 17</p></li><li>Docker</li></ul>
      <h2>단계</h2><pre>docker compose up</pre></main><footer>©</footer></body></html>`;
    const { title, text } = extractMain(html);
    expect(title).toBe("설치 가이드 | Docs");
    expect(text).toContain("# 설치");
    expect(text).toContain("## 단계");
    expect(text).toContain("- Java 17");
    expect(text).not.toContain("홈");
    expect(text).not.toContain("x()");
    // li 안의 p 가 두 번 잡히지 않는다
    expect(text.split("Java 17").length - 1).toBe(1);
  });
});

describe("chunkText", () => {
  it("소제목 경계를 지키고 소제목 경로를 붙인다", () => {
    const text = ["# 설치", "첫 문단", "## 요구사항", "자바가 필요하다. ".repeat(40), "## 단계", "짧다"].join("\n");
    const chunks = chunkText(text, { maxChars: 300, overlapChars: 40, minChars: 50 });
    expect(chunks[0]).toEqual({ heading: "설치", text: "첫 문단" });
    const req = chunks.filter((c) => c.heading === "설치 > 요구사항");
    expect(req.length).toBeGreaterThan(1);
    for (const c of req) expect(c.text.length).toBeLessThanOrEqual(300);
    expect(chunks.at(-1)).toEqual({ heading: "설치 > 단계", text: "짧다" });
  });
  it("짧은 꼬리는 같은 소제목의 앞 조각에 붙인다", () => {
    const text = ["# A", "x".repeat(250), "y".repeat(250), "끝"].join("\n");
    const chunks = chunkText(text, { maxChars: 300, overlapChars: 0, minChars: 50 });
    expect(chunks.length).toBe(2);
    expect(chunks[1].text.endsWith("\n끝")).toBe(true);
  });
});

describe("splitForCitation", () => {
  it("문단 수가 상한을 넘으면 묶는다", () => {
    expect(splitForCitation("a\nb\nc")).toEqual(["a", "b", "c"]);
    expect(splitForCitation(Array.from({ length: 13 }, (_, i) => `p${i}`).join("\n"), 6).length).toBeLessThanOrEqual(7);
    expect(splitForCitation("   ")).toEqual(["   "]);
  });
});
