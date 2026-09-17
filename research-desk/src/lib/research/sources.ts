/**
 * 응답 content 블록에서 출처와 본문을 꺼내는 순수 함수.
 *
 * SDK 타입에 기대지 않고 구조로만 본다 — 서버 도구 블록 이름은 버전마다
 * 바뀔 수 있고, 테스트에서 평범한 객체로 넣을 수 있어야 한다.
 * 보는 곳 세 군데:
 *   1. web_search_tool_result → content 배열의 web_search_result (url/title/page_age)
 *   2. text 블록의 citations → web_search_result_location (url/title)
 *   3. web_fetch_tool_result → content.url (열어 본 페이지)
 */
import type { Source } from "./types";

type Obj = Record<string, unknown>;

function isObj(v: unknown): v is Obj {
  return typeof v === "object" && v !== null;
}

function str(v: unknown): string | null {
  return typeof v === "string" && v.length > 0 ? v : null;
}

function pushSource(out: Map<string, Source>, url: unknown, title: unknown, pageAge: unknown): void {
  const u = str(url);
  if (!u) return;
  const existing = out.get(u);
  const t = str(title) ?? existing?.title ?? u;
  const age = str(pageAge) ?? existing?.pageAge ?? null;
  out.set(u, { url: u, title: t, pageAge: age });
}

export function collectSources(content: unknown): Source[] {
  const out = new Map<string, Source>();
  if (!Array.isArray(content)) return [];
  for (const block of content) {
    if (!isObj(block)) continue;
    const type = block.type;
    if (type === "web_search_tool_result" && Array.isArray(block.content)) {
      for (const r of block.content) {
        if (isObj(r) && r.type === "web_search_result") pushSource(out, r.url, r.title, r.page_age);
      }
    } else if (type === "text" && Array.isArray(block.citations)) {
      for (const c of block.citations) {
        if (isObj(c) && c.type === "web_search_result_location") pushSource(out, c.url, c.title, null);
      }
    } else if (type === "web_fetch_tool_result" && isObj(block.content)) {
      const doc = isObj(block.content.content) ? block.content.content : null;
      pushSource(out, block.content.url, doc?.title, null);
    }
  }
  return [...out.values()];
}

export function textOf(content: unknown): string {
  if (!Array.isArray(content)) return "";
  const parts: string[] = [];
  for (const block of content) {
    if (isObj(block) && block.type === "text" && typeof block.text === "string") parts.push(block.text);
  }
  return parts.join("");
}

/** 출처 목록 합치기 — URL 기준 중복 제거, 먼저 본 제목 유지. */
export function mergeSources(...lists: Source[][]): Source[] {
  const out = new Map<string, Source>();
  for (const list of lists) {
    for (const s of list) {
      const prev = out.get(s.url);
      out.set(s.url, prev ? { ...prev, pageAge: prev.pageAge ?? s.pageAge } : s);
    }
  }
  return [...out.values()];
}
