/**
 * 구조화 출력 스키마. 모델은 이 모양으로만 답한다 (output_config.format).
 * 제약(min/max)은 두지 않는다 — 구조화 출력이 지원하는 JSON Schema 부분집합
 * 안에 머물고, 개수 상한은 파이프라인이 자른다.
 */
import { z } from "zod";

export const PlanSchema = z.object({
  framing: z.string(),
  sub_questions: z.array(z.string()),
  kill_criteria: z.array(z.string()),
});
export type PlanOut = z.infer<typeof PlanSchema>;

export const ClaimsSchema = z.object({
  claims: z.array(
    z.object({
      text: z.string(),
      evidence: z.string(),
      source_urls: z.array(z.string()),
      confidence: z.enum(["high", "medium", "low"]),
      // 수치 주장에만 채운다. 정성 주장은 전부 null.
      metric: z.string().nullable(),
      value: z.string().nullable(),
      unit: z.string().nullable(),
      year: z.string().nullable(),
      geography: z.string().nullable(),
    }),
  ),
});
export type ClaimsOut = z.infer<typeof ClaimsSchema>;

export const VerdictsSchema = z.object({
  verdicts: z.array(
    z.object({
      claim_id: z.string(),
      verdict: z.enum(["confirmed", "killed", "open"]),
      reason: z.string(),
      counter_source_urls: z.array(z.string()),
    }),
  ),
});
export type VerdictsOut = z.infer<typeof VerdictsSchema>;
