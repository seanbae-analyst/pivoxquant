import type Anthropic from "@anthropic-ai/sdk";
import { describe, expect, it } from "vitest";
import { askKb, toSearchResults, type StreamLike } from "../answer";
import { MemoryStore } from "../store-memory";
import type { AskEvent, Chunk, Doc, Embedder } from "../types";

const embedder: Embedder = {
  model: "fake",
  dimensions: 2,
  embedDocuments: async (t) => t.map((x) => (x.includes("Iceberg") ? new Float32Array([1, 0]) : new Float32Array([0, 1]))),
  embedQuery: async (q) => (q.includes("Iceberg") ? new Float32Array([1, 0]) : new Float32Array([0, 1])),
};

async function seeded(): Promise<MemoryStore> {
  const s = new MemoryStore();
  const mk = (id: string, text: string, heading: string, emb: Float32Array): [Doc, Chunk[]] => [
    { id, sourceId: "iceberg", url: `https://iceberg.example/${id}`, title: `Doc ${id}`, text, contentHash: "h", fetchedAt: "2026-09-01T00:00:00.000Z" },
    [{ id: `${id}#0`, docId: id, sourceId: "iceberg", url: `https://iceberg.example/${id}`, title: `Doc ${id}`, heading, ordinal: 0, text, fetchedAt: "2026-09-01T00:00:00.000Z", embedding: emb }],
  ];
  await s.upsertDoc(...mk("a", "Iceberg 는 컬럼 추가·삭제·이름 변경을 지원한다.\n파티션 진화도 된다.", "스키마 진화", new Float32Array([1, 0])));
  await s.upsertDoc(...mk("b", "Delta 는 시간 여행을 지원한다.", "기능", new Float32Array([0, 1])));
  return s;
}

function fakeStream(captured: { params?: Anthropic.MessageStreamParams }): (p: Anthropic.MessageStreamParams) => StreamLike {
  return (params) => {
    captured.params = params;
    const events = [
      { type: "content_block_delta", index: 0, delta: { type: "text_delta", text: "Iceberg 는 컬럼 추가를 지원한다" } },
      { type: "content_block_delta", index: 0, delta: { type: "citations_delta", citation: { type: "search_result_location", source: "https://iceberg.example/a", title: "Doc a — 스키마 진화", cited_text: "Iceberg 는 컬럼 추가·삭제·이름 변경을 지원한다.", search_result_index: 0, start_block_index: 0, end_block_index: 1 } } },
      { type: "content_block_delta", index: 0, delta: { type: "text_delta", text: "." } },
    ] as unknown as Anthropic.MessageStreamEvent[];
    return {
      async *[Symbol.asyncIterator]() {
        for (const e of events) yield e;
      },
      finalMessage: async () => ({ stop_reason: "end_turn" }) as unknown as Anthropic.Message,
    };
  };
}

describe("askKb", () => {
  it("검색 → search_result 블록 → 토큰·인용 이벤트 → 출처에 인용문이 붙는다", async () => {
    const store = await seeded();
    const captured: { params?: Anthropic.MessageStreamParams } = {};
    const events: AskEvent[] = [];
    const out = await askKb("Iceberg 스키마 진화 범위는?", { embedder, store, stream: fakeStream(captured), model: "m" }, (e) => events.push(e));

    // 요청: search_result 블록이 먼저, 질문 텍스트가 마지막
    const content = captured.params!.messages[0].content as Anthropic.ContentBlockParam[];
    expect(content.at(-1)).toEqual({ type: "text", text: "질문: Iceberg 스키마 진화 범위는?" });
    const first = content[0] as Anthropic.SearchResultBlockParam;
    expect(first.type).toBe("search_result");
    expect(first.source).toBe("https://iceberg.example/a");
    expect(first.title).toBe("Doc a — 스키마 진화");
    expect(first.content.length).toBe(2); // 문단마다 블록 하나 = 인용 최소 단위
    expect(first.citations).toEqual({ enabled: true });
    expect(captured.params!.model).toBe("m");

    expect(out.answer).toBe("Iceberg 는 컬럼 추가를 지원한다.");
    expect(out.grounded).toBe(true);
    expect(out.sources[0]).toMatchObject({ n: 1, url: "https://iceberg.example/a", cited: ["Iceberg 는 컬럼 추가·삭제·이름 변경을 지원한다."] });
    expect(out.sources[1].cited).toEqual([]);
    expect(events.filter((e) => e.type === "citation")).toEqual([{ type: "citation", n: 1, citedText: "Iceberg 는 컬럼 추가·삭제·이름 변경을 지원한다." }]);
    expect(events.at(-1)?.type).toBe("done");
  });
  it("재정렬기가 있으면 그 순서를 따른다", async () => {
    const store = await seeded();
    const captured: { params?: Anthropic.MessageStreamParams } = {};
    const reranker = { rerank: async (_q: string, docs: string[], k: number) => docs.map((_, i) => ({ index: docs.length - 1 - i, score: 1 - i * 0.1 })).slice(0, k) };
    await askKb("Iceberg", { embedder, store, reranker, stream: fakeStream(captured), model: "m" }, () => {});
    const first = (captured.params!.messages[0].content as Anthropic.SearchResultBlockParam[])[0];
    expect(first.source).toBe("https://iceberg.example/b");
  });
  it("빈 저장소면 모델을 부르지 않고 안내한다", async () => {
    const events: AskEvent[] = [];
    let called = false;
    const out = await askKb("q", { embedder, store: new MemoryStore(), stream: () => { called = true; throw new Error("x"); } }, (e) => events.push(e));
    expect(called).toBe(false);
    expect(out.grounded).toBe(false);
    expect(out.answer).toContain("지식 베이스에 아직 문서가 없거나");
  });
  it("toSearchResults 는 소제목 없는 조각의 제목을 그대로 쓴다", () => {
    const r = toSearchResults([{ score: 1, chunk: { id: "x#0", docId: "x", sourceId: "s", url: "u", title: "T", heading: "", ordinal: 0, text: "a\nb", fetchedAt: "" } }]);
    expect(r[0].title).toBe("T");
  });
});
