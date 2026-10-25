/**
 * Postgres + pgvector 저장소. 스키마는 db/schema.sql.
 * 벡터 검색(코사인) 과 전문 검색(tsvector) 을 각각 뽑아 RRF 로 합친다.
 */
import { Pool } from "pg";
import { rrf } from "./store-memory";
import type { Chunk, Doc, KbStats, KbStore, Retrieved } from "./types";

function vec(v: Float32Array): string {
  return `[${Array.from(v).join(",")}]`;
}

export class PgStore implements KbStore {
  private pool: Pool;
  constructor(connectionString = process.env.DATABASE_URL) {
    if (!connectionString) throw new Error("DATABASE_URL 이 없다.");
    this.pool = new Pool({ connectionString, max: 4 });
  }

  async hasDoc(docId: string, contentHash: string): Promise<boolean> {
    const r = await this.pool.query("select 1 from kb_docs where id = $1 and content_hash = $2", [docId, contentHash]);
    return (r.rowCount ?? 0) > 0;
  }

  async upsertDoc(doc: Doc, chunks: Chunk[]): Promise<void> {
    const client = await this.pool.connect();
    try {
      await client.query("begin");
      await client.query(
        `insert into kb_docs (id, source_id, url, title, content_hash, fetched_at)
         values ($1,$2,$3,$4,$5,$6)
         on conflict (id) do update set source_id=excluded.source_id, url=excluded.url, title=excluded.title, content_hash=excluded.content_hash, fetched_at=excluded.fetched_at`,
        [doc.id, doc.sourceId, doc.url, doc.title, doc.contentHash, doc.fetchedAt],
      );
      await client.query("delete from kb_chunks where doc_id = $1", [doc.id]);
      for (const c of chunks) {
        if (!c.embedding) throw new Error(`chunk ${c.id} 에 임베딩이 없다`);
        await client.query(
          `insert into kb_chunks (id, doc_id, source_id, url, title, heading, ordinal, text, fetched_at, embedding)
           values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::vector)`,
          [c.id, c.docId, c.sourceId, c.url, c.title, c.heading, c.ordinal, c.text, c.fetchedAt, vec(c.embedding)],
        );
      }
      await client.query("commit");
    } catch (e) {
      await client.query("rollback");
      throw e;
    } finally {
      client.release();
    }
  }

  async search(query: { embedding: Float32Array; text: string }, k: number): Promise<Retrieved[]> {
    const n = k * 3;
    const v = await this.pool.query<{ id: string; score: number }>(
      `select id, 1 - (embedding <=> $1::vector) as score from kb_chunks order by embedding <=> $1::vector limit $2`,
      [vec(query.embedding), n],
    );
    const t = await this.pool.query<{ id: string; score: number }>(
      `select id, ts_rank_cd(tsv, q) as score from kb_chunks, plainto_tsquery('simple', $1) q where tsv @@ q order by score desc limit $2`,
      [query.text, n],
    );
    const fused = rrf([v.rows, t.rows]);
    const ids = [...fused.entries()].sort((a, b) => b[1] - a[1]).slice(0, k);
    if (ids.length === 0) return [];
    const rows = await this.pool.query<{ id: string; doc_id: string; source_id: string; url: string; title: string; heading: string; ordinal: number; text: string; fetched_at: string }>(
      `select id, doc_id, source_id, url, title, heading, ordinal, text, fetched_at::text from kb_chunks where id = any($1)`,
      [ids.map(([id]) => id)],
    );
    const byId = new Map(rows.rows.map((r) => [r.id, r]));
    return ids
      .map(([id, score]) => {
        const r = byId.get(id);
        if (!r) return null;
        const chunk: Chunk = { id: r.id, docId: r.doc_id, sourceId: r.source_id, url: r.url, title: r.title, heading: r.heading, ordinal: r.ordinal, text: r.text, fetchedAt: r.fetched_at };
        return { chunk, score };
      })
      .filter((x): x is Retrieved => x !== null);
  }

  async stats(): Promise<KbStats> {
    const tot = await this.pool.query<{ docs: string; chunks: string }>("select (select count(*) from kb_docs) as docs, (select count(*) from kb_chunks) as chunks");
    const per = await this.pool.query<{ source_id: string; docs: string; chunks: string; last: string | null }>(
      `select d.source_id, count(distinct d.id) as docs, count(c.id) as chunks, max(d.fetched_at)::text as last
       from kb_docs d left join kb_chunks c on c.doc_id = d.id group by d.source_id order by d.source_id`,
    );
    return {
      docs: Number(tot.rows[0].docs),
      chunks: Number(tot.rows[0].chunks),
      sources: per.rows.map((r) => ({ sourceId: r.source_id, docs: Number(r.docs), chunks: Number(r.chunks), lastFetchedAt: r.last })),
    };
  }

  async close(): Promise<void> {
    await this.pool.end();
  }
}
