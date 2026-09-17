/**
 * 수집 → 임베딩 → 저장. 변경 없는 문서(contentHash 동일)는 임베딩을 건너뛴다.
 */
import { crawlSource, type CrawlOptions } from "./crawl";
import type { Embedder, KbStore, SourceConfig } from "./types";

export interface IngestResult {
  sourceId: string;
  fetched: number;
  updated: number;
  skipped: number;
  chunks: number;
}

export async function ingestSource(
  source: SourceConfig,
  store: KbStore,
  embedder: Embedder | null,
  opt: CrawlOptions & { dryRun?: boolean } = {},
): Promise<IngestResult> {
  const log = opt.log ?? (() => {});
  const pages = await crawlSource(source, opt);
  const result: IngestResult = { sourceId: source.id, fetched: pages.length, updated: 0, skipped: 0, chunks: 0 };
  for (const page of pages) {
    if (await store.hasDoc(page.doc.id, page.doc.contentHash)) {
      result.skipped++;
      continue;
    }
    if (opt.dryRun || !embedder) {
      result.updated++;
      result.chunks += page.chunks.length;
      log(`[dry] ${page.doc.title} — 조각 ${page.chunks.length}`);
      continue;
    }
    const vectors = await embedder.embedDocuments(page.chunks.map((c) => `${c.title}\n${c.heading}\n${c.text}`));
    page.chunks.forEach((c, i) => (c.embedding = vectors[i]));
    await store.upsertDoc(page.doc, page.chunks);
    result.updated++;
    result.chunks += page.chunks.length;
    log(`[ok] ${page.doc.title} — 조각 ${page.chunks.length}`);
  }
  return result;
}
