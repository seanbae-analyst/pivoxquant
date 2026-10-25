/**
 * HTML → 본문 평문, 본문 → 조각. 순수 함수. 네트워크 없음.
 */
import * as cheerio from "cheerio";
import { createHash } from "node:crypto";

export function sha1(s: string): string {
  return createHash("sha1").update(s).digest("hex");
}

const STRIP = ["script", "style", "noscript", "svg", "canvas", "iframe", "nav", "header", "footer", "aside", "form", "button", "[role=navigation]", "[role=banner]", "[role=contentinfo]", ".sidebar", ".toc", ".breadcrumb", ".breadcrumbs", ".cookie", "#cookie-banner"];

/** 페이지에서 제목과 본문을 뽑는다. main/article 을 우선하고 없으면 body. */
export function extractMain(html: string): { title: string; text: string } {
  const $ = cheerio.load(html);
  const title = ($("meta[property='og:title']").attr("content") || $("title").first().text() || $("h1").first().text() || "").trim().replace(/\s+/g, " ");
  for (const sel of STRIP) $(sel).remove();
  const root = $("main").first().length ? $("main").first() : $("article").first().length ? $("article").first() : $("body");
  const BLOCKS = "h1, h2, h3, h4, p, li, pre, td, th, blockquote, dt, dd";
  const lines: string[] = [];
  root.find(BLOCKS).each((_, el) => {
    const tag = (el as { tagName?: string }).tagName?.toLowerCase() ?? "";
    const heading = /^h[1-4]$/.test(tag);
    // 블록 안에 또 블록이 있으면(li 안의 p 등) 바깥은 건너뛴다 — 안쪽이 낸다. 같은 문장이 두 번 잡히는 걸 막는다.
    if (!heading && $(el).find(BLOCKS).length > 0) return;
    const t = $(el).text().replace(/\s+/g, " ").trim();
    if (!t) return;
    const inList = tag === "li" || $(el).parent().is("li");
    if (heading) lines.push(`\n${"#".repeat(Number(tag[1]))} ${t}\n`);
    else if (tag === "pre") lines.push("```\n" + $(el).text().trim() + "\n```");
    else if (inList) lines.push(`- ${t}`);
    else lines.push(t);
  });
  const seen = new Set<string>();
  const dedup = lines.filter((l) => {
    const k = l.trim().replace(/^- /, "");
    if (!k || seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  return { title, text: dedup.join("\n").replace(/\n{3,}/g, "\n\n").trim() };
}

export interface ChunkOptions {
  maxChars?: number;
  overlapChars?: number;
  minChars?: number;
}

/**
 * 소제목 경계를 우선 지키며 maxChars 안팎으로 자른다. 각 조각은 자기 소제목 경로를 안다.
 * 아주 짧은 꼬리(minChars 미만)는 앞 조각에 붙인다.
 */
export function chunkText(text: string, opt: ChunkOptions = {}): Array<{ heading: string; text: string }> {
  const maxChars = opt.maxChars ?? 1800;
  const overlap = opt.overlapChars ?? 200;
  const minChars = opt.minChars ?? 200;

  // 1) 소제목 단위 섹션
  const sections: Array<{ heading: string; body: string[] }> = [{ heading: "", body: [] }];
  const path: string[] = [];
  for (const raw of text.split("\n")) {
    const m = /^(#{1,4})\s+(.+)$/.exec(raw.trim());
    if (m) {
      const level = m[1].length;
      path.length = Math.max(0, level - 1);
      path[level - 1] = m[2].trim();
      sections.push({ heading: path.filter(Boolean).join(" > "), body: [] });
    } else if (raw.trim()) {
      sections[sections.length - 1].body.push(raw.trim());
    }
  }

  // 2) 섹션 안에서 문단을 모아 maxChars 로 자른다
  const out: Array<{ heading: string; text: string }> = [];
  for (const s of sections) {
    const paras = s.body;
    if (paras.length === 0) continue;
    let buf = "";
    const flush = () => {
      const t = buf.trim();
      if (t) out.push({ heading: s.heading, text: t });
      buf = "";
    };
    for (const p of paras) {
      if (p.length > maxChars) {
        flush();
        for (let i = 0; i < p.length; i += maxChars - overlap) out.push({ heading: s.heading, text: p.slice(i, i + maxChars) });
        continue;
      }
      if ((buf + "\n" + p).length > maxChars) {
        // 앞 조각의 꼬리를 겹쳐 문맥을 잇는다. overlap 0 이면 slice(-0) 이 전체를 돌려주므로 따로 처리.
        const tail = overlap > 0 ? buf.slice(-overlap) : "";
        flush();
        buf = tail && (tail + "\n" + p).length <= maxChars ? tail + "\n" + p : p;
      } else {
        buf = buf ? buf + "\n" + p : p;
      }
    }
    flush();
  }

  // 3) 짧은 꼬리는 같은 소제목의 앞 조각에 붙인다
  const merged: Array<{ heading: string; text: string }> = [];
  for (const c of out) {
    const prev = merged[merged.length - 1];
    if (prev && prev.heading === c.heading && c.text.length < minChars && (prev.text + "\n" + c.text).length <= maxChars + minChars) {
      prev.text += "\n" + c.text;
    } else {
      merged.push({ ...c });
    }
  }
  return merged;
}

/** 조각 본문을 인용 단위(문단)로 쪼갠다 — search_result 의 content 블록 하나가 인용 최소 단위다. */
export function splitForCitation(text: string, maxBlocks = 6): string[] {
  const parts = text.split(/\n+/).map((s) => s.trim()).filter(Boolean);
  if (parts.length <= maxBlocks) return parts.length ? parts : [text];
  const per = Math.ceil(parts.length / maxBlocks);
  const out: string[] = [];
  for (let i = 0; i < parts.length; i += per) out.push(parts.slice(i, i + per).join("\n"));
  return out;
}
