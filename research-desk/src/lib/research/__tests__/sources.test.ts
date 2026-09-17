import { describe, expect, it } from "vitest";
import { collectSources, mergeSources, textOf } from "../sources";

describe("collectSources", () => {
  it("검색 결과·인용·fetch 블록에서 URL 을 모으고 중복을 합친다", () => {
    const content = [
      { type: "server_tool_use", id: "x", name: "web_search", input: { query: "q" } },
      {
        type: "web_search_tool_result",
        tool_use_id: "x",
        content: [
          { type: "web_search_result", url: "https://a.example/1", title: "A", page_age: "2 days ago", encrypted_content: "..." },
          { type: "web_search_result", url: "https://b.example/2", title: "B", page_age: null, encrypted_content: "..." },
        ],
      },
      {
        type: "text",
        text: "본문",
        citations: [{ type: "web_search_result_location", url: "https://a.example/1", title: "A (cited)", cited_text: "...", encrypted_index: "i" }],
      },
      { type: "web_fetch_tool_result", tool_use_id: "y", content: { type: "web_fetch_result", url: "https://c.example/3", content: { type: "document", title: "C doc" }, retrieved_at: null } },
    ];
    const out = collectSources(content);
    expect(out.map((s) => s.url)).toEqual(["https://a.example/1", "https://b.example/2", "https://c.example/3"]);
    expect(out[0]).toEqual({ url: "https://a.example/1", title: "A (cited)", pageAge: "2 days ago" });
    expect(out[2].title).toBe("C doc");
  });

  it("오류 블록(배열이 아닌 content)과 빈 입력을 무시한다", () => {
    expect(collectSources([{ type: "web_search_tool_result", content: { type: "web_search_tool_result_error", error_code: "max_uses_exceeded" } }])).toEqual([]);
    expect(collectSources(null)).toEqual([]);
  });
});

describe("textOf / mergeSources", () => {
  it("text 블록만 이어 붙인다", () => {
    expect(textOf([{ type: "thinking", thinking: "" }, { type: "text", text: "가" }, { type: "text", text: "나" }])).toBe("가나");
  });
  it("URL 기준으로 합치고 먼저 본 제목을 유지한다", () => {
    const merged = mergeSources(
      [{ url: "u1", title: "첫 제목", pageAge: null }],
      [{ url: "u1", title: "다른 제목", pageAge: "1 week ago" }, { url: "u2", title: "둘", pageAge: null }],
    );
    expect(merged).toEqual([
      { url: "u1", title: "첫 제목", pageAge: "1 week ago" },
      { url: "u2", title: "둘", pageAge: null },
    ]);
  });
});
