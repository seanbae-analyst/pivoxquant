import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { MemoryStore, rrf, tokens } from "../store-memory";
import type { Chunk, Doc } from "../types";

function vec(...xs: number[]): Float32Array {
  const v = new Float32Array(4);
  xs.forEach((x, i) => (v[i] = x));
  const n = Math.hypot(...v);
  return v.map((x) => x / n) as Float32Array;
}
function doc(id: string, sourceId = "s"): Doc {
  return { id, sourceId, url: `https://x/${id}`, title: `T${id}`, text: "본문", contentHash: "h" + id, fetchedAt: "2026-09-17T00:00:00.000Z" };
}
function chunk(docId: string, i: number, text: string, embedding: Float32Array): Chunk {
  return { id: `${docId}#${i}`, docId, sourceId: "s", url: `https://x/${docId}`, title: `T${docId}`, heading: "", ordinal: i, text, fetchedAt: "2026-09-17T00:00:00.000Z", embedding };
}

describe("MemoryStore", () => {
  it("벡터와 키워드를 합쳐 찾고, 같은 해시는 건너뛴다, 파일로 왕복한다", async () => {
    const file = path.join(mkdtempSync(path.join(tmpdir(), "kb-")), "index.json");
    const s = await MemoryStore.open(file);
    await s.upsertDoc(doc("a"), [chunk("a", 0, "Iceberg 스키마 진화는 컬럼 추가를 지원한다", vec(1, 0, 0, 0))]);
    await s.upsertDoc(doc("b"), [chunk("b", 0, "Delta Lake 의 시간 여행", vec(0, 1, 0, 0)), chunk("b", 1, "리니지 자동 추출", vec(0, 0, 1, 0))]);
    expect(await s.hasDoc("a", "ha")).toBe(true);
    expect(await s.hasDoc("a", "other")).toBe(false);

    // 벡터는 b#1 에 가깝지만 키워드는 a 를 가리킨다 → 둘 다 상위에
    const hits = await s.search({ embedding: vec(0, 0, 1, 0.1), text: "Iceberg 스키마" }, 2);
    expect(hits.map((h) => h.chunk.id).sort()).toEqual(["a#0", "b#1"]);

    // 문서 갱신은 옛 조각을 지운다
    await s.upsertDoc({ ...doc("b"), contentHash: "hb2" }, [chunk("b", 0, "새 본문", vec(0, 1, 0, 0))]);
    expect((await s.stats()).chunks).toBe(2);

    await s.close();
    const r = await MemoryStore.open(file);
    const st = await r.stats();
    expect(st).toEqual({ docs: 2, chunks: 2, sources: [{ sourceId: "s", docs: 2, chunks: 2, lastFetchedAt: "2026-09-17T00:00:00.000Z" }] });
    const again = await r.search({ embedding: vec(1, 0, 0, 0), text: "" }, 1);
    expect(again[0].chunk.id).toBe("a#0");
  });
  it("빈 저장소는 빈 결과", async () => {
    const s = new MemoryStore();
    expect(await s.search({ embedding: vec(1), text: "x" }, 5)).toEqual([]);
  });
});

describe("rrf / tokens", () => {
  it("두 목록 모두에 있는 항목이 위로 온다", () => {
    const m = rrf([[{ id: "a", score: 1 }, { id: "b", score: 0.5 }], [{ id: "b", score: 1 }, { id: "c", score: 0.5 }]]);
    const order = [...m.entries()].sort((x, y) => y[1] - x[1]).map(([id]) => id);
    expect(order[0]).toBe("b");
  });
  it("한글·영문·숫자 토큰을 소문자로 뽑는다", () => {
    expect(tokens("Iceberg v2 스키마-진화")).toEqual(["iceberg", "v2", "스키마", "진화"]);
  });
});
