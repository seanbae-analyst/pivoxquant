/**
 * Regression guard (frontend mirror of tests/test_no_misleading_marketing_copy.py)
 *
 * 표시광고법 §3 ① 1호 — 거짓 / 과장 표시광고 금지.
 *
 * Stripe 결제가 아직 활성화되지 않은 상태에서 "무료 체험" / "Free Trial"
 * 카피는 실제로 제공하지 않는 혜택을 광고하는 것이 되어 표시광고법
 * 위반이다. v33 PR #251 옵션 C 카피 적용 + (Wave 1 Task 3) 본 게이트로
 * 프론트엔드 단계에서 회귀를 차단한다.
 *
 * 본 게이트는 backend pytest (tests/test_no_misleading_marketing_copy.py)
 * 의 mirror — vitest 환경에서 frontend 만 빠르게 검증해 PR 머지 전 피드백
 * 사이클을 단축한다.
 */
import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const FRONTEND_SRC = join(__dirname, "..");

const FORBIDDEN_PHRASES = [
  "무료 체험",
  "Pro 무료 체험",
  "free trial",
  "Free Trial",
  "체험판",
] as const;

const REMOVAL_MARKERS = [
  "REMOVED",
  "retired",
  "기능 제거",
  "removed",
  "removal",
] as const;

const TARGET_DIRS = [
  join(FRONTEND_SRC, "i18n"),
  join(FRONTEND_SRC, "app"),
  join(FRONTEND_SRC, "components", "landing"),
];

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
      // Exclude the test files themselves so phrase mentions in docstrings
      // don't self-trigger.
      if (name.endsWith(".test.ts") || name.endsWith(".test.tsx")) continue;
      if (name.endsWith(".spec.ts") || name.endsWith(".spec.tsx")) continue;
      acc.push(full);
    }
  }
  return acc;
}

function lineHasRemovalMarker(line: string): boolean {
  return REMOVAL_MARKERS.some((m) => line.includes(m));
}

describe("표시광고법 §3 ① 1호 — no 'free trial' marketing copy", () => {
  const files = TARGET_DIRS.flatMap((d) => walk(d));

  it("collects at least one target file (sanity)", () => {
    expect(files.length).toBeGreaterThan(0);
  });

  for (const phrase of FORBIDDEN_PHRASES) {
    it(`forbidden phrase "${phrase}" not present in user-visible source`, () => {
      const offenders: string[] = [];
      for (const file of files) {
        const text = readFileSync(file, "utf-8");
        const lines = text.split("\n");
        for (let i = 0; i < lines.length; i++) {
          const line = lines[i];
          if (lineHasRemovalMarker(line)) continue;
          if (line.toLowerCase().includes(phrase.toLowerCase())) {
            offenders.push(
              `${relative(FRONTEND_SRC, file)}:${i + 1} → ${line.trim()}`,
            );
          }
        }
      }
      if (offenders.length > 0) {
        const detail = offenders.slice(0, 5).join("\n  ");
        throw new Error(
          `"${phrase}" 카피가 ${offenders.length}개 surface 에 잔존. ` +
            `Stripe 활성화 전 "무료 체험" 광고는 표시광고법 §3 ① 1호 위반.\n  ${detail}`,
        );
      }
      expect(offenders).toEqual([]);
    });
  }
});
