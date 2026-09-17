/**
 * 리서치 파이프라인 — 계획 → 조사(병렬) → 반증 → 판정 → 집필.
 *
 * 이 파일은 네트워크를 모른다. Llm 인터페이스의 세 동작(searchTurn / parseJson /
 * streamText)만 호출하고, 진행 상황은 emit 으로 내보낸다. 그래서 가짜 Llm 으로
 * 전 구간을 결정론적으로 테스트할 수 있다.
 */
import { ClaimsSchema, PlanSchema, VerdictsSchema } from "./schemas";
import { getDomain, resolveType } from "./domains";
import {
  JUDGE_SYSTEM,
  briefToQuestion,
  extractorSystem,
  extractorUser,
  judgeUser,
  plannerSystem,
  plannerUser,
  searcherSystem,
  searcherUser,
  skepticSystem,
  skepticUser,
  writerSystem,
  writerUser,
} from "./prompts";
import { renderAppendix, reportHeader } from "./report";
import { mergeSources } from "./sources";
import type { Brief, Claim, ClaimVerdict, Llm, Plan, Report, ResearchEvent, Source, SubResult } from "./types";

export interface PipelineOptions {
  /** 하위 질문 상한. 기획이 더 내놓아도 여기서 자른다. */
  maxSubQuestions?: number;
  /** 하위 질문 하나당 웹 검색 상한. 반증 단계는 +2. */
  maxSearches?: number;
  now?: () => Date;
  id?: () => string;
}

const DEFAULTS: Required<PipelineOptions> = {
  maxSubQuestions: 5,
  maxSearches: 6,
  now: () => new Date(),
  id: () => Math.random().toString(36).slice(2, 10),
};

export function normalizePlan(raw: { framing: string; sub_questions: string[]; kill_criteria: string[] }, max: number): Plan {
  const subQuestions = raw.sub_questions.map((q) => q.trim()).filter(Boolean).slice(0, max);
  return {
    framing: raw.framing.trim(),
    subQuestions,
    killCriteria: raw.kill_criteria.map((k) => k.trim()).filter(Boolean),
  };
}

type RawClaim = {
  text: string;
  evidence: string;
  source_urls: string[];
  confidence: "high" | "medium" | "low";
  metric?: string | null;
  value?: string | null;
  unit?: string | null;
  year?: string | null;
  geography?: string | null;
};

function nz(v: string | null | undefined): string | null {
  const t = (v ?? "").trim();
  return t.length ? t : null;
}

/** 추출된 주장에 id 를 붙이고, 출처 목록에 없는 URL 은 버린다 (지어낸 URL 차단). */
export function toClaims(subIndex: number, subQuestion: string, raw: { claims: RawClaim[] }, known: Source[]): Claim[] {
  const knownUrls = new Set(known.map((s) => s.url));
  return raw.claims
    .filter((c) => c.text.trim().length > 0)
    .map((c, i) => ({
      id: `C${subIndex + 1}.${i + 1}`,
      subQuestion,
      text: c.text.trim(),
      evidence: c.evidence.trim(),
      sourceUrls: c.source_urls.filter((u) => knownUrls.has(u)),
      confidence: c.confidence,
      metric: nz(c.metric),
      value: nz(c.value),
      unit: nz(c.unit),
      year: nz(c.year),
      geography: nz(c.geography),
    }));
}

/** 요청 본문을 Brief 로 정리한다. 모르는 domain 은 기본 도메인, 모르는 type 은 그 도메인의 custom. topic 이 비면 null. */
export function normalizeBrief(raw: unknown): Brief | null {
  const r = (typeof raw === "object" && raw !== null ? raw : {}) as Record<string, unknown>;
  const str = (k: string) => (typeof r[k] === "string" ? (r[k] as string).trim() : "");
  const topic = str("topic") || str("question");
  if (!topic) return null;
  const domain = getDomain(str("domain"));
  const { id: type } = resolveType(domain, str("type"));
  return { domain: domain.id, type, topic, geography: str("geography"), timeframe: str("timeframe"), context: str("context") };
}

/** 모든 주장에 판정이 하나씩 있게 맞춘다. 빠진 건 open, 모르는 id 는 버린다. */
export function normalizeVerdicts(claims: Claim[], raw: { verdicts: Array<{ claim_id: string; verdict: "confirmed" | "killed" | "open"; reason: string; counter_source_urls: string[] }> }, known: Source[]): ClaimVerdict[] {
  const knownUrls = new Set(known.map((s) => s.url));
  const byId = new Map<string, ClaimVerdict>();
  for (const v of raw.verdicts) {
    if (byId.has(v.claim_id)) continue;
    byId.set(v.claim_id, {
      claimId: v.claim_id,
      verdict: v.verdict,
      reason: v.reason.trim(),
      counterSourceUrls: v.counter_source_urls.filter((u) => knownUrls.has(u)),
    });
  }
  return claims.map(
    (c) => byId.get(c.id) ?? { claimId: c.id, verdict: "open", reason: "판정 단계가 이 주장을 다루지 않았다.", counterSourceUrls: [] },
  );
}

export async function runResearch(
  input: Brief | string,
  llm: Llm,
  emit: (ev: ResearchEvent) => void,
  options: PipelineOptions = {},
): Promise<Report> {
  const opt = { ...DEFAULTS, ...options };
  const brief = normalizeBrief(typeof input === "string" ? { topic: input, type: "custom" } : input);
  if (!brief) throw new Error("질문이 비어 있다.");
  const q = briefToQuestion(brief);
  const domain = getDomain(brief.domain);
  const { spec } = resolveType(domain, brief.type);

  // 1. 계획 — 유형별 이슈 트리 틀
  emit({ type: "status", stage: "planning", message: "브리프를 이슈 트리로 쪼개는 중" });
  const plan = normalizePlan(await llm.parseJson(PlanSchema, plannerSystem(spec), plannerUser(brief), "medium"), opt.maxSubQuestions);
  if (plan.subQuestions.length === 0) throw new Error("기획 단계가 하위 질문을 내놓지 않았다.");
  emit({ type: "plan", plan });

  // 2. 조사 — 하위 질문마다 독립 검색, 병렬
  emit({ type: "status", stage: "searching", message: `하위 질문 ${plan.subQuestions.length}개를 병렬로 조사하는 중` });
  const subResults: SubResult[] = await Promise.all(
    plan.subQuestions.map(async (sq, index): Promise<SubResult> => {
      try {
        const turn = await llm.searchTurn(searcherSystem(domain), searcherUser(brief, sq), { maxSearches: opt.maxSearches, effort: "high" });
        const parsed = await llm.parseJson(ClaimsSchema, extractorSystem(domain), extractorUser(sq, turn.text, turn.sources), "medium");
        const claims = toClaims(index, sq, parsed, turn.sources);
        emit({ type: "sub_done", index, subQuestion: sq, claimCount: claims.length, sourceCount: turn.sources.length, error: null });
        return { index, subQuestion: sq, notes: turn.text, sources: turn.sources, claims, error: null };
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        emit({ type: "sub_done", index, subQuestion: sq, claimCount: 0, sourceCount: 0, error: message });
        return { index, subQuestion: sq, notes: "", sources: [], claims: [], error: message };
      }
    }),
  );
  if (subResults.every((r) => r.error !== null)) {
    throw new Error(`조사 단계가 전부 실패했다: ${subResults[0].error}`);
  }
  const claims = subResults.flatMap((r) => r.claims);
  let sources = mergeSources(...subResults.map((r) => r.sources));

  // 3. 반증 + 판정
  let verdicts: ClaimVerdict[] = [];
  if (claims.length > 0) {
    emit({ type: "status", stage: "verifying", message: `주장 ${claims.length}건의 반대 근거를 찾는 중` });
    const counter = await llm.searchTurn(skepticSystem(domain), skepticUser(brief, plan, claims), { maxSearches: opt.maxSearches + 2, effort: "high" });
    sources = mergeSources(sources, counter.sources);
    const judged = await llm.parseJson(VerdictsSchema, JUDGE_SYSTEM, judgeUser(claims, counter.text, counter.sources), "high");
    verdicts = normalizeVerdicts(claims, judged, sources);
  }
  emit({ type: "verdicts", verdicts });

  // 4. 집필
  emit({ type: "status", stage: "writing", message: "리서치 노트를 쓰는 중" });
  const body = await llm.streamText(writerSystem(domain, spec), writerUser(brief, plan, claims, verdicts, sources), (text) => emit({ type: "token", text }));

  const createdAt = opt.now().toISOString();
  const report: Report = {
    id: opt.id(),
    brief,
    question: q,
    createdAt,
    model: llm.model,
    plan,
    claims,
    verdicts,
    sources,
    markdown: "",
  };
  report.markdown = `${reportHeader(report)}\n${body.trim()}\n\n${renderAppendix(claims, verdicts, sources)}\n`;
  emit({ type: "status", stage: "done", message: "완료" });
  emit({ type: "done", report });
  return report;
}
