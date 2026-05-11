/**
 * Regression guard — `<input type="date">` must declare `colorScheme`.
 *
 * Vantablack v3 디자인 시스템 락-인 (project_design_v3) — `<input type="date">`
 * 는 native picker UI 를 OS 가 렌더링한다. `color-scheme` 을 선언하지 않으면
 * Vantablack 베이스(#050505) 위에 흰 사각형 picker 가 떠서 디자인 회귀가 발생.
 *
 * 본 게이트는 frontend/src 안의 모든 `<input type="date">` 매치를 추출 후
 * 같은 element 가 `colorScheme` (style or className) 을 선언하는지 검증한다.
 * 신규 date input 추가 시 자동으로 catch — feedback_thorough_fixes 룰 (한 번
 * 손대면 전수 점검) 을 회귀 게이트로 enforce.
 *
 * 허용 패턴:
 * - `style={{ colorScheme: "dark" }}` (또는 `"light"`)
 * - `style={{ ..., colorScheme: "..." }}`
 * - className 의 `[color-scheme:dark]` Tailwind arbitrary
 * - `style={{ ...someStyleObject, colorScheme: "..." }}` (shared style 위에
 *   element 가 명시적으로 colorScheme 을 추가)
 */
import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const FRONTEND_SRC = join(__dirname, "..");

const TARGET_EXTS = new Set([".ts", ".tsx"]);

function walk(dir: string, acc: string[] = []): string[] {
  let entries: string[];
  try {
    entries = readdirSync(dir);
  } catch {
    return acc;
  }
  for (const name of entries) {
    if (name === "node_modules" || name === ".next") continue;
    const full = join(dir, name);
    let st;
    try {
      st = statSync(full);
    } catch {
      continue;
    }
    if (st.isDirectory()) {
      walk(full, acc);
    } else if (TARGET_EXTS.has(name.slice(name.lastIndexOf(".")))) {
      if (name.endsWith(".test.ts") || name.endsWith(".test.tsx")) continue;
      if (name.endsWith(".spec.ts") || name.endsWith(".spec.tsx")) continue;
      acc.push(full);
    }
  }
  return acc;
}

/**
 * Find `<input ... type="date" ... />` elements (open tag span) and return
 * the raw text of each so we can verify presence of colorScheme on the same
 * element.
 *
 * JSX attributes can contain `{...}` expressions with arbitrary `>` chars
 * (e.g. `onChange={(e) => ...}`). A naive non-greedy regex stops at the
 * first `>` which truncates the element. We walk char-by-char tracking JSX
 * brace depth and string quoting to find the true element close (`>` or
 * `/>` outside any `{...}` and string).
 */
function extractDateInputElements(source: string): string[] {
  const out: string[] = [];
  const tag = "<input";
  let i = 0;
  while (i < source.length) {
    const start = source.indexOf(tag, i);
    if (start === -1) break;
    const after = source.charCodeAt(start + tag.length);
    const isBoundary =
      after === 32 ||
      after === 9 ||
      after === 10 ||
      after === 13 ||
      after === 47 ||
      after === 62;
    if (!isBoundary) {
      i = start + tag.length;
      continue;
    }
    let j = start + tag.length;
    let braceDepth = 0;
    let quote: string | null = null;
    while (j < source.length) {
      const ch = source[j];
      if (quote) {
        if (ch === "\\" && j + 1 < source.length) {
          j += 2;
          continue;
        }
        if (ch === quote) quote = null;
        j++;
        continue;
      }
      if (ch === '"' || ch === "'" || ch === "`") {
        quote = ch;
        j++;
        continue;
      }
      if (ch === "{") {
        braceDepth++;
        j++;
        continue;
      }
      if (ch === "}") {
        braceDepth--;
        j++;
        continue;
      }
      if (braceDepth === 0 && ch === ">") {
        j++;
        break;
      }
      j++;
    }
    const element = source.slice(start, j);
    if (/type\s*=\s*["']date["']/.test(element)) {
      out.push(element);
    }
    i = j;
  }
  return out;
}

describe("design v3 — <input type=\"date\"> must declare colorScheme", () => {
  const files = walk(FRONTEND_SRC);

  it("collects at least one source file (sanity)", () => {
    expect(files.length).toBeGreaterThan(0);
  });

  it("every <input type=\"date\"> element declares colorScheme on the same element", () => {
    const offenders: string[] = [];
    for (const file of files) {
      const text = readFileSync(file, "utf-8");
      if (!text.includes("type=\"date\"") && !text.includes("type='date'")) {
        continue;
      }
      const elements = extractDateInputElements(text);
      for (const el of elements) {
        const hasInline =
          /colorScheme\s*:/.test(el) || /\[color-scheme:/.test(el);
        if (!hasInline) {
          offenders.push(
            `${relative(FRONTEND_SRC, file)} → ${el.replace(/\s+/g, " ").slice(0, 140)}`,
          );
        }
      }
    }
    if (offenders.length > 0) {
      const detail = offenders.slice(0, 10).join("\n  ");
      throw new Error(
        `${offenders.length} date input(s) missing colorScheme — Vantablack v3 회귀 ` +
          `(native picker 흰 사각형 렌더링).\n  ${detail}`,
      );
    }
    expect(offenders).toEqual([]);
  });
});
