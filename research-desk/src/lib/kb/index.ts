/**
 * 서버·스크립트가 쓰는 조립 지점. DATABASE_URL 이 있으면 pgvector, 없으면 kb/index.json 파일 저장소.
 */
import path from "node:path";
import { createVoyageEmbedder, createVoyageReranker } from "./embed";
import { MemoryStore } from "./store-memory";
import { PgStore } from "./store-pg";
import type { Embedder, KbStore, Reranker } from "./types";

export const KB_INDEX_PATH = process.env.KB_INDEX_PATH || path.join(process.cwd(), "kb", "index.json");

let cached: Promise<KbStore> | null = null;

export function openStore(): Promise<KbStore> {
  if (!cached) {
    cached = process.env.DATABASE_URL ? Promise.resolve(new PgStore()) : MemoryStore.open(KB_INDEX_PATH);
  }
  return cached;
}

export function getEmbedder(): Embedder {
  return createVoyageEmbedder();
}

export function getReranker(): Reranker | null {
  if (process.env.KB_RERANK === "0") return null;
  return createVoyageReranker();
}

export function kbConfigured(): { ok: boolean; missing: string[] } {
  const missing: string[] = [];
  if (!process.env.VOYAGE_API_KEY) missing.push("VOYAGE_API_KEY");
  if (!process.env.ANTHROPIC_API_KEY && !process.env.ANTHROPIC_AUTH_TOKEN) missing.push("ANTHROPIC_API_KEY");
  return { ok: missing.length === 0, missing };
}
