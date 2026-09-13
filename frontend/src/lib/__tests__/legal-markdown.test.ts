/**
 * /terms and /privacy render through lib/legal-markdown.ts. These tests read
 * the real documents from src/content/ and render them exactly as the pages
 * do (`renderLegalMarkdown(raw)`), so a content edit that re-breaks bold shows
 * up here rather than on the page.
 *
 * Regression: 2026-09-12 sweep — literal `**` on /terms (6) and /privacy (10),
 * including "투자 추천이 ** 아닙니다**", caused by an unanchored hair-space regex.
 * There are no English versions of these documents (src/content/ holds only
 * terms-ko.md and privacy-ko.md).
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { marked } from "marked";

import {
  pairBoldDelimiters,
  renderLegalMarkdown,
  stripFrontmatter,
} from "@/lib/legal-markdown";

const CONTENT_DIR = join(__dirname, "..", "..", "content");
const DOCS = ["terms-ko.md", "privacy-ko.md"] as const;

const textOf = (html: string) => html.replace(/<[^>]+>/g, "");
const count = (s: string, re: RegExp) => (s.match(re) ?? []).length;
/** Sequence of opening/closing tag names, ignoring <strong>. */
const blockSkeleton = (html: string) =>
  (html.match(/<\/?[a-z][a-z0-9]*/g) ?? []).filter(
    (tag) => tag !== "<strong" && tag !== "</strong",
  );

describe("renderLegalMarkdown — real legal documents", () => {
  for (const name of DOCS) {
    const raw = readFileSync(join(CONTENT_DIR, name), "utf8");
    const html = renderLegalMarkdown(raw);
    const delimiters = count(stripFrontmatter(raw), /\*\*/g);

    it(`${name}: no literal ** reaches the reader`, () => {
      expect(textOf(html).match(/\*\*[^\n]{0,20}/g) ?? []).toEqual([]);
    });

    it(`${name}: every ** pair becomes exactly one <strong>`, () => {
      expect(delimiters).toBeGreaterThan(0);
      expect(delimiters % 2).toBe(0);
      expect(count(html, /<strong>/g)).toBe(delimiters / 2);
      expect(count(html, /<\/strong>/g)).toBe(delimiters / 2);
    });

    it(`${name}: pairing bold leaves the block structure unchanged`, () => {
      const withoutBold = marked.parse(
        stripFrontmatter(raw).replaceAll("**", ""),
        { async: false },
      );
      expect(blockSkeleton(html)).toEqual(blockSkeleton(withoutBold));
    });
  }

  it("terms-ko.md: the not-a-recommendation clause is bold, not asterisks", () => {
    const html = renderLegalMarkdown(
      readFileSync(join(CONTENT_DIR, "terms-ko.md"), "utf8"),
    );
    expect(html).toContain("투자 추천이 <strong>아닙니다</strong>");
    expect(html).toMatch(/<strong>(&quot;|")서비스(&quot;|")<\/strong>란/);
  });
});

describe("pairBoldDelimiters", () => {
  const render = (md: string) => marked.parse(pairBoldDelimiters(md), { async: false });

  it("closes bold before a Hangul particle that follows punctuation", () => {
    // CommonMark would leave both ** literal here (closing is not right-flanking).
    expect(render('**"회원"**이란 가입한 자')).toMatch(
      /<strong>(&quot;|")회원(&quot;|")<\/strong>이란/,
    );
  });

  it("does not bridge a closing ** to the next opening ** on the same line", () => {
    // The shape the old unanchored regex broke.
    const html = render("값은 **A**이며, 추천이 **아닙니다**.");
    expect(html).toContain("<strong>A</strong>이며");
    expect(html).toContain("추천이 <strong>아닙니다</strong>.");
    expect(textOf(html)).not.toContain("**");
  });

  it("pairs a bold span that wraps across blockquote lines", () => {
    const html = render("> 앞 **굵게 시작\n> 여기서 끝**이며 뒤");
    expect(html).toContain("<strong>굵게 시작\n여기서 끝</strong>이며");
  });

  it("leaves an unpaired ** literal and does not let it swallow the next paragraph", () => {
    const html = render("열린 **채로\n\n다음 **문단**입니다");
    expect(html).toContain("열린 **채로");
    expect(html).toContain("다음 <strong>문단</strong>입니다");
  });

  it("does not pair across list items or table rows", () => {
    expect(render("- 하나 **x\n- 둘 y**")).not.toContain("<strong>");
    expect(render("| a **b |\n|---|\n| c** d |")).not.toContain("<strong>");
  });

  it("ignores ** inside code spans and fenced code", () => {
    expect(render("`**코드**` 그리고 **굵게**")).toContain(
      "<code>**코드**</code> 그리고 <strong>굵게</strong>",
    );
    expect(render("```\n**코드**\n```")).not.toContain("<strong>");
  });
});
