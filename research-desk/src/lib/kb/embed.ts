/**
 * Voyage AI 임베딩·재정렬 — Anthropic 이 권장하는 임베딩 파트너.
 * https://platform.claude.com/docs/en/build-with-claude/embeddings
 * 문서와 질문은 input_type 을 다르게 준다 (검색 품질에 직접 영향).
 */
import type { Embedder, Reranker } from "./types";

const EMBED_URL = "https://api.voyageai.com/v1/embeddings";
const RERANK_URL = "https://api.voyageai.com/v1/rerank";
export const DEFAULT_EMBED_MODEL = "voyage-4";
export const DEFAULT_RERANK_MODEL = "rerank-2.5";
export const EMBED_DIMENSIONS = 1024;
const BATCH = 64;

function apiKey(): string {
  const k = process.env.VOYAGE_API_KEY;
  if (!k) throw new Error("VOYAGE_API_KEY 가 없다. 임베딩과 검색에 필요하다.");
  return k;
}

async function post<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${apiKey()}` },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Voyage ${res.status}: ${(await res.text()).slice(0, 300)}`);
  return (await res.json()) as T;
}

interface EmbedResponse { data: Array<{ embedding: number[]; index: number }> }
interface RerankResponse { data: Array<{ index: number; relevance_score: number }> }

export function createVoyageEmbedder(model = process.env.VOYAGE_EMBED_MODEL || DEFAULT_EMBED_MODEL): Embedder {
  async function embed(texts: string[], inputType: "document" | "query"): Promise<Float32Array[]> {
    const out: Float32Array[] = [];
    for (let i = 0; i < texts.length; i += BATCH) {
      const slice = texts.slice(i, i + BATCH);
      const res = await post<EmbedResponse>(EMBED_URL, { input: slice, model, input_type: inputType, output_dimension: EMBED_DIMENSIONS });
      const sorted = [...res.data].sort((a, b) => a.index - b.index);
      for (const d of sorted) out.push(Float32Array.from(d.embedding));
    }
    return out;
  }
  return {
    model,
    dimensions: EMBED_DIMENSIONS,
    embedDocuments: (texts) => embed(texts, "document"),
    embedQuery: async (text) => (await embed([text], "query"))[0],
  };
}

export function createVoyageReranker(model = process.env.VOYAGE_RERANK_MODEL || DEFAULT_RERANK_MODEL): Reranker {
  return {
    async rerank(query, docs, topK) {
      if (docs.length === 0) return [];
      const res = await post<RerankResponse>(RERANK_URL, { query, documents: docs, model, top_k: Math.min(topK, docs.length) });
      return res.data.map((d) => ({ index: d.index, score: d.relevance_score }));
    },
  };
}

/** 정규화된 벡터끼리는 내적 = 코사인. Voyage 임베딩은 길이 1 로 정규화돼 있다. */
export function dot(a: Float32Array, b: Float32Array): number {
  let s = 0;
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i++) s += a[i] * b[i];
  return s;
}
