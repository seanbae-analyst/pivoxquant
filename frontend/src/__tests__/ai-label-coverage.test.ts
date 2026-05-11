/**
 * Regression guard — AI 생성물 표시제 (regulatory ③ 2026-01 시행)
 *
 * AI가 생성한 텍스트(SWOT, chat 응답, coaching message 등)를 사용자에게
 * 노출하는 모든 surface 는 `<AiContentBadge />` 라벨을 의무 렌더해야 한다.
 *
 * 본 게이트는 W3 P0 B1 (audit 부서 발견) 후속 작업 — `detail/[ticker]/page.tsx`
 * 가 `/api/ai/swot` 응답을 라벨 없이 렌더하던 결함을 close 하면서, 향후
 * 신규 AI surface 가 라벨 없이 추가되는 회귀를 차단한다.
 *
 * 룰:
 *   1) `/api/ai/...` consumer 페이지 → `AiContentBadge` import 필수
 *   2) AI 응답 텍스트 키 (`swot_kr`, `swot_en`, `coachingMessage`,
 *      `aiAnalysis`, `aiSwot`, `aiCommentary`, `ai_summary`, `ai_response`)
 *      를 렌더하는 파일 → `AiContentBadge` import 필수
 *
 * Allowlist:
 *   - 타입 정의 파일 (`lib/types.ts`) — 렌더 surface 아님
 *   - badge 컴포넌트 자체 + 그 테스트
 *   - trigger-only 파일 (AI 호출만 하고 응답 텍스트를 렌더하지 않음)
 */
import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const FRONTEND_SRC = join(__dirname, "..");

const TARGET_DIRS = [join(FRONTEND_SRC, "app"), join(FRONTEND_SRC, "components")];

const TARGET_EXTS = new Set([".ts", ".tsx"]);

// AI 호출 패턴 — 호출이 있으면 응답을 렌더하므로 라벨 의무
const AI_API_PATTERN = /["'`]\/api\/ai\//;

// AI 응답 텍스트 키 — 백엔드에서 LLM 출력으로 채워지는 필드
const AI_RESPONSE_KEY_PATTERN =
  /\b(swot_kr|swot_en|coachingMessage|aiAnalysis|aiSwot|aiCommentary|ai_summary|ai_response)\b/;

const BADGE_IMPORT_PATTERN = /AiContentBadge/;

// Allowlist (relative to FRONTEND_SRC)
const ALLOWLIST = new Set<string>([
  "lib/types.ts", // 타입 정의만, 렌더 surface 아님
  "components/ui/ai-content-badge.tsx", // badge 자체
  // /sample-reports/page.tsx — 18-tile navigator. Renders titles/tiers only,
  // no AI content surface. Detail route ([slug]/page.tsx) is gated below.
  "app/sample-reports/page.tsx",
]);

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
    } else {
      const ext = name.slice(name.lastIndexOf("."));
      if (!TARGET_EXTS.has(ext)) continue;
      if (name.endsWith(".test.ts") || name.endsWith(".test.tsx")) continue;
      if (name.endsWith(".spec.ts") || name.endsWith(".spec.tsx")) continue;
      acc.push(full);
    }
  }
  return acc;
}

function isAllowlisted(rel: string): boolean {
  // Normalize path separators for cross-platform safety
  const normalized = rel.split(/[\\/]/).join("/");
  return ALLOWLIST.has(normalized);
}

interface Offender {
  rel: string;
  reason: string;
  matchedLine: string;
}

describe("AI 생성물 표시제 (regulatory ③ 2026-01) — AiContentBadge coverage", () => {
  const files = TARGET_DIRS.flatMap((d) => walk(d));

  it("collects at least one source file (sanity)", () => {
    expect(files.length).toBeGreaterThan(0);
  });

  it("every /api/ai/ consumer renders <AiContentBadge />", () => {
    const offenders: Offender[] = [];
    for (const file of files) {
      const rel = relative(FRONTEND_SRC, file);
      if (isAllowlisted(rel)) continue;
      const text = readFileSync(file, "utf-8");
      const apiMatch = text.match(AI_API_PATTERN);
      if (!apiMatch) continue;
      if (BADGE_IMPORT_PATTERN.test(text)) continue;
      // Find the matched line for the error message
      const lines = text.split("\n");
      const idx = lines.findIndex((l) => AI_API_PATTERN.test(l));
      offenders.push({
        rel,
        reason: "calls /api/ai/* but no AiContentBadge import",
        matchedLine: idx >= 0 ? `${idx + 1}: ${lines[idx].trim()}` : "(unknown)",
      });
    }
    if (offenders.length > 0) {
      const detail = offenders
        .map((o) => `  ${o.rel} — ${o.reason}\n    ${o.matchedLine}`)
        .join("\n");
      throw new Error(
        `${offenders.length} surface(s) call /api/ai/* without <AiContentBadge />.\n` +
          `regulatory ③ (AI 생성물 표시제, 2026-01 시행) 위반.\n${detail}`,
      );
    }
    expect(offenders).toEqual([]);
  });

  it("every /sample-reports/** surface imports AiContentBadge (regulatory ③ thorough-fixes gate)", () => {
    // Why: PR #277 (Artifact 템플릿 라벨) + PR #282 (detail/[ticker] 라벨)
    // 두 번 연속 sample-reports surface 를 누락. memory [feedback_thorough_fixes]
    // 3차 위반 admit 후 추가된 게이트. 향후 신규 sample-report 라우트가
    // 라벨 없이 머지되는 회귀를 차단한다.
    //
    // 룰: app/sample-reports/** 아래 모든 .ts/.tsx 파일에 AiContentBadge import 필수
    //     단, 위 ALLOWLIST 항목 (index navigator) 만 예외.
    const offenders: Offender[] = [];
    for (const file of files) {
      const rel = relative(FRONTEND_SRC, file);
      const normalized = rel.split(/[\\/]/).join("/");
      if (!normalized.startsWith("app/sample-reports/")) continue;
      if (isAllowlisted(rel)) continue;
      const text = readFileSync(file, "utf-8");
      if (BADGE_IMPORT_PATTERN.test(text)) continue;
      offenders.push({
        rel,
        reason: "sample-reports surface without AiContentBadge import",
        matchedLine: "(file-level guard)",
      });
    }
    if (offenders.length > 0) {
      const detail = offenders
        .map((o) => `  ${o.rel} — ${o.reason}\n    ${o.matchedLine}`)
        .join("\n");
      throw new Error(
        `${offenders.length} /sample-reports/** surface(s) missing <AiContentBadge />.\n` +
          `regulatory ③ (AI 생성물 표시제, 2026-01 시행 / 정통망법 §50 6% 과징금) 위반.\n` +
          `feedback_thorough_fixes 3차 위반 (PR #277 / #282 누락) 후 추가된 게이트.\n${detail}`,
      );
    }
    expect(offenders).toEqual([]);
  });

  it("every AI response key renderer imports AiContentBadge", () => {
    const offenders: Offender[] = [];
    for (const file of files) {
      const rel = relative(FRONTEND_SRC, file);
      if (isAllowlisted(rel)) continue;
      const text = readFileSync(file, "utf-8");
      const keyMatch = text.match(AI_RESPONSE_KEY_PATTERN);
      if (!keyMatch) continue;
      if (BADGE_IMPORT_PATTERN.test(text)) continue;
      const lines = text.split("\n");
      const idx = lines.findIndex((l) => AI_RESPONSE_KEY_PATTERN.test(l));
      offenders.push({
        rel,
        reason: `renders AI key "${keyMatch[1]}" but no AiContentBadge import`,
        matchedLine: idx >= 0 ? `${idx + 1}: ${lines[idx].trim()}` : "(unknown)",
      });
    }
    if (offenders.length > 0) {
      const detail = offenders
        .map((o) => `  ${o.rel} — ${o.reason}\n    ${o.matchedLine}`)
        .join("\n");
      throw new Error(
        `${offenders.length} surface(s) render AI response keys without <AiContentBadge />.\n` +
          `regulatory ③ (AI 생성물 표시제, 2026-01 시행) 위반.\n${detail}`,
      );
    }
    expect(offenders).toEqual([]);
  });
});
