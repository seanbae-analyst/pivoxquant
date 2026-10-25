import { describe, expect, it } from "vitest";
import { allowedByPatterns, crawlSource, readFeed, readSitemap, type Fetcher } from "../crawl";
import { ingestSource } from "../ingest";
import { MemoryStore } from "../store-memory";
import type { SourceConfig } from "../types";

const page = (title: string, body: string) => `<html><head><title>${title}</title></head><body><nav>메뉴</nav><main><h1>${title}</h1>${body}</main></body></html>`;
const LONG = `<p>${"데이터 카탈로그는 메타데이터를 모아 검색·발견·거버넌스에 쓴다. ".repeat(8)}</p><h2>커넥터</h2><p>${"커넥터가 스키마와 리니지를 자동 수집한다. ".repeat(8)}</p>`;

const SITE: Record<string, { status?: number; type?: string; body: string }> = {
  "https://docs.example/robots.txt": { type: "text/plain", body: "User-agent: *\nDisallow: /private/\n" },
  "https://docs.example/sitemap.xml": { type: "application/xml", body: `<sitemapindex><sitemap><loc>https://docs.example/sitemap-1.xml</loc></sitemap></sitemapindex>` },
  "https://docs.example/sitemap-1.xml": {
    type: "application/xml",
    body: `<urlset><url><loc>https://docs.example/docs/intro</loc></url><url><loc>https://docs.example/docs/intro</loc></url><url><loc>https://docs.example/private/x</loc></url><url><loc>https://docs.example/docs/api/ref</loc></url><url><loc>https://docs.example/blog/hi</loc></url><url><loc>https://docs.example/docs/short</loc></url><url><loc>https://docs.example/docs/file.pdf</loc></url></urlset>`,
  },
  "https://docs.example/docs/intro": { body: page("소개", LONG) },
  "https://docs.example/private/x": { body: page("비공개", LONG) },
  "https://docs.example/docs/api/ref": { body: page("API", LONG) },
  "https://docs.example/blog/hi": { body: page("블로그", LONG) },
  "https://docs.example/docs/short": { body: page("짧음", "<p>한 줄</p>") },
  "https://docs.example/docs/file.pdf": { type: "application/pdf", body: "%PDF" },
  "https://blog.example/feed": {
    type: "application/rss+xml",
    body: `<rss><channel><item><link>https://blog.example/a</link></item><item><link>https://blog.example/b</link></item></channel></rss>`,
  },
  "https://atom.example/feed": {
    type: "application/atom+xml",
    body: `<feed><entry><link rel="alternate" href="https://atom.example/1"/></entry><entry><link href="https://atom.example/2"/></entry></feed>`,
  },
};

const fetcher: Fetcher = async (url) => {
  const hit = SITE[url];
  if (!hit) return new Response("nope", { status: 404 });
  return new Response(hit.body, { status: hit.status ?? 200, headers: { "content-type": hit.type ?? "text/html; charset=utf-8" } });
};

const SRC: SourceConfig = { id: "docs", name: "Docs", kind: "sitemap", url: "https://docs.example/sitemap.xml", include: ["^/docs/"], exclude: ["/api/"], maxPages: 10, tier: "official_docs" };

describe("crawlSource", () => {
  it("사이트맵 인덱스를 따라가고, 패턴·robots·짧은 본문·비HTML 을 거른다", async () => {
    const log: string[] = [];
    const pages = await crawlSource(SRC, { fetcher, delayMs: 0, now: () => new Date("2026-09-17T00:00:00Z"), log: (l) => log.push(l) });
    expect(pages.map((p) => p.doc.url)).toEqual(["https://docs.example/docs/intro"]);
    const p = pages[0];
    expect(p.doc.title).toBe("소개");
    expect(p.doc.fetchedAt).toBe("2026-09-17T00:00:00.000Z");
    expect(p.chunks.length).toBeGreaterThanOrEqual(2);
    expect(p.chunks.map((c) => c.heading)).toContain("소개 > 커넥터");
    expect(p.chunks[0].id).toBe(`${p.doc.id}#0`);
    expect(log.join("\n")).toContain("본문 짧음");
    expect(log.join("\n")).toContain("건너뜀 200 https://docs.example/docs/file.pdf");
  });
  it("robots 가 막은 경로는 include 에 맞아도 가져오지 않는다", async () => {
    const log: string[] = [];
    const pages = await crawlSource({ ...SRC, include: ["^/private/"], exclude: [] }, { fetcher, delayMs: 0, log: (l) => log.push(l) });
    expect(pages).toEqual([]);
    expect(log.join("\n")).toContain("robots 차단");
  });
  it("RSS 와 Atom 링크를 읽는다", async () => {
    expect(await readFeed("https://blog.example/feed", fetcher)).toEqual(["https://blog.example/a", "https://blog.example/b"]);
    expect(await readFeed("https://atom.example/feed", fetcher)).toEqual(["https://atom.example/1", "https://atom.example/2"]);
    expect(await readSitemap("https://docs.example/sitemap.xml", fetcher)).toHaveLength(7);
  });
  it("allowedByPatterns", () => {
    expect(allowedByPatterns("https://x/docs/a?b=1", [/^\/docs\//], [/\?/])).toBe(false);
    expect(allowedByPatterns("https://x/docs/a", [], [])).toBe(true);
  });
});

describe("ingestSource", () => {
  it("dry-run 은 저장하지 않고 세기만 하며, 같은 해시는 건너뛴다", async () => {
    const store = new MemoryStore();
    const dry = await ingestSource(SRC, store, null, { fetcher, delayMs: 0, dryRun: true });
    expect(dry).toMatchObject({ sourceId: "docs", fetched: 1, updated: 1, skipped: 0 });
    expect((await store.stats()).chunks).toBe(0);

    const embedder = { model: "fake", dimensions: 2, embedDocuments: async (t: string[]) => t.map(() => new Float32Array([1, 0])), embedQuery: async () => new Float32Array([1, 0]) };
    const first = await ingestSource(SRC, store, embedder, { fetcher, delayMs: 0 });
    expect(first.updated).toBe(1);
    expect((await store.stats()).docs).toBe(1);
    const second = await ingestSource(SRC, store, embedder, { fetcher, delayMs: 0 });
    expect(second).toMatchObject({ updated: 0, skipped: 1 });
  });
});
