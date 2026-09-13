/**
 * Shared renderer for the legal documents — /terms and /privacy.
 *
 * This is the ONLY copy. Both pages import it (CLAUDE.md trap §10: a legally
 * important helper gets one implementation, never a second per-page copy).
 *
 * Why bold is paired here instead of by marked
 * --------------------------------------------
 * CommonMark only closes `**` when the delimiter is "right-flanking". In
 * `**"서비스"**란` the closing `**` has punctuation before it and a Hangul
 * syllable after it, so it is not — marked printed literal asterisks.
 *
 * The previous fix (a hair space inserted by
 * `/(\*\*[^*\n]+?\*\*)([ㄱ-ㆎ가-힣])/g`, one copy per page) was unanchored: a
 * lazy match can START at a closing `**` and end at the next OPENING `**`,
 * which put the space inside the real opening delimiter (`** 아닙니다**`) and
 * broke that pair instead. Measured 2026-09-13, marked 18.0.3: 6 literal `**`
 * on /terms and 10 on /privacy with that regex; 14 and 0 with none at all —
 * so neither "regex" nor "no preprocessing" is correct for both documents.
 *
 * Here the flanking rules are taken out of the picture: delimiters are paired
 * left to right inside one block and emitted as `<strong>` inline HTML. marked
 * passes the tags through and still parses the text between them as markdown.
 * `legal-markdown.test.ts` renders the real documents and checks that no `**`
 * survives and that the block structure is unchanged.
 */
import { marked } from "marked";

export function stripFrontmatter(md: string): string {
  if (!md.startsWith("---")) return md;
  const end = md.indexOf("\n---", 3);
  return end === -1 ? md : md.slice(end + 4).trimStart();
}

const FENCE = /^ {0,3}(```|~~~)/;
/** Lines that always begin a new block: ATX headings, table rows, list items. */
const BLOCK_START = /^ {0,3}(#{1,6}\s|\||[-*+]\s|\d{1,9}[.)]\s)/;

/** Pair `**` delimiters left to right within one block of text. */
function pairWithinBlock(text: string): string {
  const positions: number[] = [];
  let i = 0;
  while (i < text.length) {
    const ch = text[i];
    if (ch === "\\") {
      // Backslash escape — the next character is literal.
      i += 2;
      continue;
    }
    if (ch === "`") {
      // Code span — delimiters inside it are literal.
      let run = 1;
      while (text[i + run] === "`") run++;
      const close = text.indexOf("`".repeat(run), i + run);
      i = close === -1 ? i + run : close + run;
      continue;
    }
    if (ch === "*" && text[i + 1] === "*") {
      positions.push(i);
      i += 2;
      continue;
    }
    i++;
  }

  // An odd delimiter out is left literal rather than guessed at.
  const paired = positions.length - (positions.length % 2);
  if (paired === 0) return text;

  let out = "";
  let last = 0;
  for (let k = 0; k < paired; k++) {
    out += text.slice(last, positions[k]) + (k % 2 === 0 ? "<strong>" : "</strong>");
    last = positions[k] + 2;
  }
  return out + text.slice(last);
}

/**
 * Replace every `**…**` pair with `<strong>…</strong>`.
 *
 * Pairing never crosses a blank line, a fenced code block, a heading, a table
 * row or a list item, so one unpaired `**` cannot swallow the next block. It
 * does cross ordinary line breaks — privacy-ko.md has a bold span that wraps
 * across two `>` blockquote lines.
 */
export function pairBoldDelimiters(md: string): string {
  const out: string[] = [];
  let block: string[] = [];
  let inFence = false;

  const flush = () => {
    if (block.length > 0) {
      out.push(pairWithinBlock(block.join("\n")));
      block = [];
    }
  };

  for (const line of md.split("\n")) {
    if (FENCE.test(line)) {
      flush();
      inFence = !inFence;
      out.push(line);
      continue;
    }
    if (inFence) {
      out.push(line);
      continue;
    }
    if (line.trim() === "") {
      flush();
      out.push(line);
      continue;
    }
    if (BLOCK_START.test(line)) flush();
    block.push(line);
  }
  flush();
  return out.join("\n");
}

/** Frontmatter-stripped, bold-paired, marked-rendered HTML for a legal document. */
export function renderLegalMarkdown(raw: string): string {
  return marked.parse(pairBoldDelimiters(stripFrontmatter(raw)), { async: false });
}
