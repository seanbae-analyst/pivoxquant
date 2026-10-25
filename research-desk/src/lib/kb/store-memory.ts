/**
 * 파일/메모리 저장소 — DB 없이 돌리는 v1. ingest 가 kb/index.json 을 쓰고, 서버가 읽는다.
 * 검색은 벡터 내적 + 키워드 점수의 하이브리드(RRF). 수천 조각까지는 충분히 빠르다.
 */
import { promises as fs } from "node:fs";
import path from "node:path";
import { dot } from "./embed";
import type { Chunk, Doc, KbStats, KbStore, Retrieved } from "./types";

interface Persisted {
  version: 1;
  docs: Array<Omit<Doc, "text">>;
  chunks: Array<Omit<Chunk, "embedding"> & { embedding: string }>; // base64 Float32
}

function toB64(v: Float32Array): string {
  return Buffer.from(v.buffer, v.byteOffset, v.byteLength).toString("base64");
}
function fromB64(s: string): Float32Array {
  const buf = Buffer.from(s, "base64");
  return new Float32Array(buf.buffer, buf.byteOffset, buf.byteLength / 4);
}

const TOKEN = /[\p{L}\p{N}]{2,}/gu;
export function tokens(s: string): string[] {
  return (s.toLowerCase().match(TOKEN) ?? []);
}

/** 두 순위 목록을 Reciprocal Rank Fusion 으로 합친다. */
export function rrf(lists: Array<Array<{ id: string; score: number }>>, k = 60): Map<string, number> {
  const out = new Map<string, number>();
  for (const list of lists) {
    list.forEach((item, rank) => out.set(item.id, (out.get(item.id) ?? 0) + 1 / (k + rank + 1)));
  }
  return out;
}

export class MemoryStore implements KbStore {
  private docs = new Map<string, Omit<Doc, "text">>();
  private chunks = new Map<string, Chunk>();
  private byDoc = new Map<string, string[]>();
  constructor(private readonly filePath?: string) {}

  static async open(filePath: string): Promise<MemoryStore> {
    const s = new MemoryStore(filePath);
    try {
      const raw = JSON.parse(await fs.readFile(filePath, "utf8")) as Persisted;
      for (const d of raw.docs) s.docs.set(d.id, d);
      for (const c of raw.chunks) {
        const chunk: Chunk = { ...c, embedding: fromB64(c.embedding) };
        s.chunks.set(chunk.id, chunk);
        s.byDoc.set(chunk.docId, [...(s.byDoc.get(chunk.docId) ?? []), chunk.id]);
      }
    } catch (err) {
      if ((err as NodeJS.ErrnoException).code !== "ENOENT") throw err;
    }
    return s;
  }

  async hasDoc(docId: string, contentHash: string): Promise<boolean> {
    return this.docs.get(docId)?.contentHash === contentHash;
  }

  async upsertDoc(doc: Doc, chunks: Chunk[]): Promise<void> {
    for (const id of this.byDoc.get(doc.id) ?? []) this.chunks.delete(id);
    const { text: _text, ...meta } = doc;
    void _text;
    this.docs.set(doc.id, meta);
    this.byDoc.set(doc.id, chunks.map((c) => c.id));
    for (const c of chunks) {
      if (!c.embedding) throw new Error(`chunk ${c.id} 에 임베딩이 없다`);
      this.chunks.set(c.id, c);
    }
  }

  async search(query: { embedding: Float32Array; text: string }, k: number): Promise<Retrieved[]> {
    const all = [...this.chunks.values()];
    if (all.length === 0) return [];
    const vec = all.map((c) => ({ id: c.id, score: dot(query.embedding, c.embedding!) })).sort((a, b) => b.score - a.score).slice(0, k * 3);
    const q = new Set(tokens(query.text));
    const kw = all
      .map((c) => {
        const t = tokens(c.title + " " + c.heading + " " + c.text);
        let hit = 0;
        for (const w of t) if (q.has(w)) hit++;
        return { id: c.id, score: t.length ? hit / Math.sqrt(t.length) : 0 };
      })
      .filter((x) => x.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, k * 3);
    const fused = rrf([vec, kw]);
    return [...fused.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, k)
      .map(([id, score]) => ({ chunk: this.chunks.get(id)!, score }));
  }

  async stats(): Promise<KbStats> {
    const per = new Map<string, { docs: number; chunks: number; last: string | null }>();
    for (const d of this.docs.values()) {
      const p = per.get(d.sourceId) ?? { docs: 0, chunks: 0, last: null };
      p.docs++;
      p.chunks += this.byDoc.get(d.id)?.length ?? 0;
      if (!p.last || d.fetchedAt > p.last) p.last = d.fetchedAt;
      per.set(d.sourceId, p);
    }
    return {
      docs: this.docs.size,
      chunks: this.chunks.size,
      sources: [...per.entries()].map(([sourceId, p]) => ({ sourceId, docs: p.docs, chunks: p.chunks, lastFetchedAt: p.last })),
    };
  }

  async save(): Promise<void> {
    if (!this.filePath) return;
    const data: Persisted = {
      version: 1,
      docs: [...this.docs.values()],
      chunks: [...this.chunks.values()].map(({ embedding, ...c }) => ({ ...c, embedding: toB64(embedding!) })),
    };
    await fs.mkdir(path.dirname(this.filePath), { recursive: true });
    await fs.writeFile(this.filePath, JSON.stringify(data));
  }

  async close(): Promise<void> {
    await this.save();
  }
}
