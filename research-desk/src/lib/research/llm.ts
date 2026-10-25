/**
 * Llm 인터페이스의 Anthropic 구현.
 *
 * - 검색 턴: 서버 도구(web_search / web_fetch)를 붙인 수동 루프. 서버 루프가
 *   10회 한도에 걸려 pause_turn 으로 멈추면 assistant 턴을 그대로 붙여 재개한다.
 * - 구조화 출력: beta.messages.parse + zod 스키마. parsed_output 이 null 이면 실패.
 * - 집필: 스트리밍. 토큰이 나오는 대로 콜백.
 * - 세 호출 모두 server-side fallback("default")을 켠다 — 안전 분류기가
 *   거절하면 서버가 대체 모델로 같은 요청을 다시 돌린다.
 */
import Anthropic from "@anthropic-ai/sdk";
import { betaZodOutputFormat } from "@anthropic-ai/sdk/helpers/beta/zod";
import type { ZodType } from "zod";
import { collectSources, textOf } from "./sources";
import type { Effort, Llm, SearchTurn } from "./types";

export const DEFAULT_MODEL = "claude-opus-5";
const FALLBACK_BETA = "server-side-fallback-2026-07-01";
const MAX_PAUSE_RESUMES = 5;

export interface AnthropicLlmOptions {
  client?: Anthropic;
  model?: string;
}

export function createAnthropicLlm(options: AnthropicLlmOptions = {}): Llm {
  const client = options.client ?? new Anthropic();
  const model = options.model ?? process.env.RESEARCH_MODEL ?? DEFAULT_MODEL;

  const base = {
    model,
    betas: [FALLBACK_BETA],
    fallbacks: "default" as const,
  };

  return {
    model,

    async searchTurn(system, user, opts): Promise<SearchTurn> {
      const tools: Anthropic.Beta.BetaToolUnion[] = [
        { type: "web_search_20260209", name: "web_search", max_uses: opts.maxSearches },
        { type: "web_fetch_20260209", name: "web_fetch", max_uses: Math.max(2, Math.ceil(opts.maxSearches / 2)), max_content_tokens: 20000 },
      ];
      const messages: Anthropic.Beta.BetaMessageParam[] = [{ role: "user", content: user }];
      const text: string[] = [];
      const sources = [];
      for (let resumes = 0; ; resumes++) {
        const res = await client.beta.messages.create({
          ...base,
          max_tokens: 16000,
          system,
          output_config: { effort: opts.effort },
          tools,
          messages,
        });
        if (res.stop_reason === "refusal") {
          throw new Error(`모델이 요청을 거절했다 (${res.stop_details?.category ?? "unknown"}).`);
        }
        text.push(textOf(res.content));
        sources.push(...collectSources(res.content));
        if (res.stop_reason === "pause_turn" && resumes < MAX_PAUSE_RESUMES) {
          messages.push({ role: "assistant", content: res.content });
          continue;
        }
        break;
      }
      return { text: text.join("\n"), sources: collectSources(sources.map((s) => ({ type: "web_search_result", url: s.url, title: s.title, page_age: s.pageAge }))) };
    },

    async parseJson<T>(schema: ZodType<T>, system: string, user: string, effort: Effort): Promise<T> {
      const res = await client.beta.messages.parse({
        ...base,
        max_tokens: 16000,
        system,
        output_config: { effort, format: betaZodOutputFormat(schema) },
        messages: [{ role: "user", content: user }],
      });
      if (res.stop_reason === "refusal") {
        throw new Error(`모델이 요청을 거절했다 (${res.stop_details?.category ?? "unknown"}).`);
      }
      if (res.parsed_output == null) {
        throw new Error(`구조화 출력 파싱 실패 (stop_reason=${res.stop_reason}).`);
      }
      return res.parsed_output as T;
    },

    async streamText(system, user, onToken): Promise<string> {
      const stream = client.beta.messages.stream({
        ...base,
        max_tokens: 32000,
        system,
        output_config: { effort: "high" },
        messages: [{ role: "user", content: user }],
      });
      stream.on("text", onToken);
      const final = await stream.finalMessage();
      if (final.stop_reason === "refusal") {
        throw new Error(`모델이 요청을 거절했다 (${final.stop_details?.category ?? "unknown"}).`);
      }
      return textOf(final.content);
    },
  };
}
