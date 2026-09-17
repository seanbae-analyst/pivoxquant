/**
 * 수집기 — robots.txt 를 지키고, 호스트마다 간격을 두고, 사이트맵·RSS·URL 목록에서 페이지를 가져온다.
 * 네트워크는 fetch 하나로만 나간다. 테스트는 fetch 를 주입한다.
 */
import { XMLParser } from "fast-xml-parser";
import robotsParser from "robots-parser";
import { chunkText, extractMain, sha1 } from "./text";
import type { Chunk, Doc, SourceConfig } from "./types";

export const USER_AGENT = "ResearchDeskBot/0.1 (+https://github.com/seanbae-analyst; data knowledge base; respects robots.txt)";

export type Fetcher = (url: string, init?: RequestInit) => Promise<Response>;

export interface CrawlOptions {
  fetcher?: Fetcher;
  /** 같은 호스트에 대한 요청 간격(ms). */
  delayMs?: number;
  now?: () => Date;
  log?: (line: string) => void;
}

function compile(patterns: string[] | undefined): RegExp[] {
  return (patterns ?? []).map((p) => new RegExp(p));
}

export function allowedByPatterns(url: string, include: RegExp[], exclude: RegExp[]): boolean {
  const path = (() => {
    try {
      const u = new URL(url);
      return u.pathname + u.search;
    } catch {
      return url;
    }
  })();
  if (exclude.some((r) => r.test(path))) return false;
  if (include.length === 0) return true;
  return include.some((r) => r.test(path));
}

/** sitemap.xml (sitemapindex 포함) 에서 URL 을 모은다. */
export async function readSitemap(url: string, fetcher: Fetcher, depth = 0, acc: string[] = []): Promise<string[]> {
  if (depth > 2) return acc;
  const res = await fetcher(url, { headers: { "User-Agent": USER_AGENT } });
  if (!res.ok) return acc;
  const xml = await res.text();
  const parsed = new XMLParser({ ignoreAttributes: true }).parse(xml) as Record<string, unknown>;
  const index = parsed.sitemapindex as { sitemap?: unknown } | undefined;
  if (index?.sitemap) {
    const list = Array.isArray(index.sitemap) ? index.sitemap : [index.sitemap];
    for (const s of list as Array<{ loc?: string }>) if (s.loc) await readSitemap(s.loc, fetcher, depth + 1, acc);
    return acc;
  }
  const set = parsed.urlset as { url?: unknown } | undefined;
  if (set?.url) {
    const list = Array.isArray(set.url) ? set.url : [set.url];
    for (const u of list as Array<{ loc?: string }>) if (u.loc) acc.push(String(u.loc).trim());
  }
  return acc;
}

/** RSS 2.0 / Atom 피드에서 항목 링크를 모은다. */
export async function readFeed(url: string, fetcher: Fetcher): Promise<string[]> {
  const res = await fetcher(url, { headers: { "User-Agent": USER_AGENT } });
  if (!res.ok) return [];
  const parsed = new XMLParser({ ignoreAttributes: false, attributeNamePrefix: "@_" }).parse(await res.text()) as Record<string, unknown>;
  const out: string[] = [];
  const rss = parsed.rss as { channel?: { item?: unknown } } | undefined;
  if (rss?.channel?.item) {
    const items = Array.isArray(rss.channel.item) ? rss.channel.item : [rss.channel.item];
    for (const it of items as Array<{ link?: string }>) if (it.link) out.push(String(it.link).trim());
  }
  const feed = parsed.feed as { entry?: unknown } | undefined;
  if (feed?.entry) {
    const entries = Array.isArray(feed.entry) ? feed.entry : [feed.entry];
    for (const e of entries as Array<{ link?: unknown }>) {
      const links = Array.isArray(e.link) ? e.link : [e.link];
      for (const l of links as Array<{ "@_href"?: string; "@_rel"?: string } | string | undefined>) {
        if (!l) continue;
        if (typeof l === "string") out.push(l);
        else if (l["@_href"] && (!l["@_rel"] || l["@_rel"] === "alternate")) out.push(l["@_href"]);
      }
    }
  }
  return out;
}

async function robotsFor(origin: string, fetcher: Fetcher, cache: Map<string, ReturnType<typeof robotsParser>>) {
  if (cache.has(origin)) return cache.get(origin)!;
  let body = "";
  try {
    const res = await fetcher(`${origin}/robots.txt`, { headers: { "User-Agent": USER_AGENT } });
    if (res.ok) body = await res.text();
  } catch {
    /* robots.txt 가 없으면 전부 허용으로 본다 */
  }
  const r = robotsParser(`${origin}/robots.txt`, body);
  cache.set(origin, r);
  return r;
}

export interface CrawledPage {
  doc: Doc;
  chunks: Chunk[];
}

/** 한 출처를 돌아 페이지마다 Doc + Chunk(임베딩 없음)를 낸다. 건너뛴 이유는 log 로. */
export async function crawlSource(source: SourceConfig, opt: CrawlOptions = {}): Promise<CrawledPage[]> {
  const fetcher = opt.fetcher ?? ((u, i) => fetch(u, i));
  const delay = opt.delayMs ?? 1000;
  const now = opt.now ?? (() => new Date());
  const log = opt.log ?? (() => {});
  const include = compile(source.include);
  const exclude = compile(source.exclude);

  let candidates: string[] = [];
  if (source.kind === "sitemap" && source.url) candidates = await readSitemap(source.url, fetcher);
  else if (source.kind === "rss" && source.url) candidates = await readFeed(source.url, fetcher);
  else if (source.kind === "urls") candidates = source.urls ?? [];
  const unique = [...new Set(candidates)].filter((u) => allowedByPatterns(u, include, exclude)).slice(0, source.maxPages);
  log(`[${source.id}] 후보 ${candidates.length} → 필터 후 ${unique.length}`);

  const robots = new Map<string, ReturnType<typeof robotsParser>>();
  const lastHit = new Map<string, number>();
  const out: CrawledPage[] = [];
  for (const url of unique) {
    let origin: string;
    try {
      origin = new URL(url).origin;
    } catch {
      continue;
    }
    const rb = await robotsFor(origin, fetcher, robots);
    if (rb.isAllowed(url, USER_AGENT) === false) {
      log(`[${source.id}] robots 차단: ${url}`);
      continue;
    }
    const wait = (lastHit.get(origin) ?? 0) + delay - Date.now();
    if (wait > 0) await new Promise((r) => setTimeout(r, wait));
    lastHit.set(origin, Date.now());
    let res: Response;
    try {
      res = await fetcher(url, { headers: { "User-Agent": USER_AGENT, Accept: "text/html,application/xhtml+xml" } });
    } catch (e) {
      log(`[${source.id}] 실패 ${url}: ${(e as Error).message}`);
      continue;
    }
    if (!res.ok || !(res.headers.get("content-type") ?? "").includes("html")) {
      log(`[${source.id}] 건너뜀 ${res.status} ${url}`);
      continue;
    }
    const { title, text } = extractMain(await res.text());
    if (text.length < 200) {
      log(`[${source.id}] 본문 짧음 ${url}`);
      continue;
    }
    const fetchedAt = now().toISOString();
    const docId = sha1(url);
    const doc: Doc = { id: docId, sourceId: source.id, url, title: title || url, text, contentHash: sha1(text), fetchedAt };
    const chunks: Chunk[] = chunkText(text).map((c, i) => ({
      id: `${docId}#${i}`,
      docId,
      sourceId: source.id,
      url,
      title: doc.title,
      heading: c.heading,
      ordinal: i,
      text: c.text,
      fetchedAt,
    }));
    out.push({ doc, chunks });
  }
  return out;
}
