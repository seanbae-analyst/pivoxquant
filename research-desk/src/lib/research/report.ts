/**
 * 보고서 부록과 파일 이름 — 순수 함수.
 */
import type { Claim, ClaimVerdict, Report, Source, Verdict } from "./types";

const VERDICT_KO: Record<Verdict, string> = {
  confirmed: "유지",
  killed: "기각",
  open: "미결",
};

export function verdictLabel(v: Verdict): string {
  return VERDICT_KO[v];
}

export function verdictCounts(verdicts: ClaimVerdict[]): Record<Verdict, number> {
  const out: Record<Verdict, number> = { confirmed: 0, killed: 0, open: 0 };
  for (const v of verdicts) out[v.verdict] += 1;
  return out;
}

function refNumbers(urls: string[], sources: Source[]): string {
  const nums = urls.map((u) => sources.findIndex((s) => s.url === u) + 1).filter((n) => n > 0);
  return nums.length ? nums.map((n) => `[${n}]`).join(" ") : "—";
}

function cell(s: string): string {
  return s.replace(/\|/g, "\\|").replace(/\r?\n/g, " ");
}

export function renderAppendix(claims: Claim[], verdicts: ClaimVerdict[], sources: Source[]): string {
  const vmap = new Map(verdicts.map((v) => [v.claimId, v]));
  const counts = verdictCounts(verdicts);
  const lines: string[] = [];
  lines.push("## 부록 A — 주장과 판정");
  lines.push("");
  lines.push(`유지 ${counts.confirmed} · 기각 ${counts.killed} · 미결 ${counts.open} (주장 ${claims.length}건)`);
  lines.push("");
  if (claims.length) {
    lines.push("| # | 판정 | 주장 | 출처 | 반대 출처 | 판정 이유 |");
    lines.push("|---|---|---|---|---|---|");
    for (const c of claims) {
      const v = vmap.get(c.id);
      lines.push(
        `| ${c.id} | ${v ? verdictLabel(v.verdict) : "미결"} | ${cell(c.text)} | ${refNumbers(c.sourceUrls, sources)} | ${v ? refNumbers(v.counterSourceUrls, sources) : "—"} | ${cell(v?.reason ?? "판정 없음")} |`,
      );
    }
  } else {
    lines.push("검증 가능한 주장을 추출하지 못했다.");
  }
  lines.push("");
  lines.push("## 부록 B — 출처");
  lines.push("");
  if (sources.length) {
    sources.forEach((s, i) => {
      lines.push(`${i + 1}. [${s.title}](${s.url})${s.pageAge ? ` — ${s.pageAge}` : ""}`);
    });
  } else {
    lines.push("열어 본 출처가 없다.");
  }
  return lines.join("\n");
}

export function slugify(question: string, max = 40): string {
  const s = question
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, max)
    .replace(/-+$/g, "");
  return s || "report";
}

export function reportFilename(report: Pick<Report, "question" | "createdAt">): string {
  const day = report.createdAt.slice(0, 10);
  return `${day}_${slugify(report.question)}.md`;
}

export function reportHeader(report: Report): string {
  return [
    `> 질문: ${report.question}`,
    `> 작성: ${report.createdAt} · 모델: ${report.model} · 출처 ${report.sources.length}건`,
    "",
  ].join("\n");
}
