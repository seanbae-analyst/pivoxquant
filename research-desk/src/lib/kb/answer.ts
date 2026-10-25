/**
 * 질의응답 — 지식 베이스에서 찾은 조각을 search_result 블록으로 주고, Claude 가 인용을 달아 답한다.
 * search_result 는 정식 Messages API 기능(베타 헤더 없음). 인용은 search_result_location 으로 돌아온다.
 * 구조화 출력(output_config.format)과는 같이 못 쓴다 — 여기선 쓰지 않는다.
 */
import Anthropic from "@anthropic-ai/sdk";
import { splitForCitation } from "./text";
import type { AnswerSource, AskEvent, Embedder, KbStore, Reranker, Retrieved } from "./types";

export const DEFAULT_MODEL = "claude-opus-5";
const RETRIEVE_K = 24;
const CONTEXT_K = 8;

export const ANSWER_SYSTEM = `당신은 데이터 관리(데이터 카탈로그, AI-ready 데이터, 거버넌스, 플랫폼, 품질·리니지) 지식 베이스의 답변 담당이다.
규율:
- 주어진 검색 결과 안의 내용으로만 답한다. 검색 결과에 없는 사실은 쓰지 않는다. 그 대신 "지식 베이스에 없다"고 말하고, 무엇을 더 수집하거나 조사해야 하는지 한 줄 적는다.
- 사실을 말하는 문장마다 인용을 단다. 도구·기능은 문서의 버전과 날짜가 보이면 함께 적는다.
- 출처끼리 다르게 말하면 둘 다 적고 어느 쪽이 더 최신·공식인지 밝힌다. 벤더 문서의 자기 주장과 제3자 서술을 구분한다.
- 짧게. 결론 먼저, 근거 다음. 목록이 맞으면 목록.
- 질문 언어로 답한다. 한국어 질문이면 한국어.`;

/** 테스트에서 갈아 끼우는 최소 스트림 인터페이스. 기본은 client.messages.stream(). */
export interface StreamLike {
  [Symbol.asyncIterator](): AsyncIterator<Anthropic.MessageStreamEvent>;
  finalMessage(): Promise<Anthropic.Message>;
}
export type StreamFactory = (params: Anthropic.MessageStreamParams) => StreamLike;

export interface AskDeps {
  embedder: Embedder;
  store: KbStore;
  reranker?: Reranker | null;
  stream?: StreamFactory;
  model?: string;
}

export function toSearchResults(hits: Retrieved[]): Anthropic.SearchResultBlockParam[] {
  return hits.map((h) => ({
    type: "search_result",
    source: h.chunk.url,
    title: h.chunk.heading ? `${h.chunk.title} — ${h.chunk.heading}` : h.chunk.title,
    content: splitForCitation(h.chunk.text).map((t) => ({ type: "text", text: t })),
    citations: { enabled: true },
  }));
}

export async function askKb(question: string, deps: AskDeps, emit: (ev: AskEvent) => void): Promise<{ answer: string; sources: AnswerSource[]; grounded: boolean }> {
  const q = question.trim();
  if (!q) throw new Error("질문이 비어 있다.");
  const model = deps.model ?? process.env.RESEARCH_MODEL ?? DEFAULT_MODEL;
  const stream = deps.stream ?? ((params) => new Anthropic().messages.stream(params));

  emit({ type: "status", message: "지식 베이스를 검색하는 중" });
  const qv = await deps.embedder.embedQuery(q);
  let hits = await deps.store.search({ embedding: qv, text: q }, RETRIEVE_K);
  if (hits.length === 0) {
    const answer = "지식 베이스에 아직 문서가 없거나 관련 조각을 찾지 못했다. 수집(ingest)을 먼저 돌리거나, 리서치 데스크로 웹에서 조사하라.";
    emit({ type: "retrieved", count: 0 });
    emit({ type: "token", text: answer });
    emit({ type: "done", answer, sources: [], grounded: false });
    return { answer, sources: [], grounded: false };
  }
  if (deps.reranker) {
    emit({ type: "status", message: "관련도 순으로 다시 정렬하는 중" });
    const ranked = await deps.reranker.rerank(q, hits.map((h) => `${h.chunk.title}\n${h.chunk.heading}\n${h.chunk.text}`), CONTEXT_K);
    hits = ranked.map((r) => ({ chunk: hits[r.index].chunk, score: r.score }));
  } else {
    hits = hits.slice(0, CONTEXT_K);
  }
  emit({ type: "retrieved", count: hits.length });

  const sources: AnswerSource[] = hits.map((h, i) => ({
    n: i + 1,
    url: h.chunk.url,
    title: h.chunk.title,
    heading: h.chunk.heading,
    sourceId: h.chunk.sourceId,
    fetchedAt: h.chunk.fetchedAt,
    cited: [],
  }));

  emit({ type: "status", message: "답을 쓰는 중" });
  const s = stream({
    model,
    max_tokens: 4000,
    system: ANSWER_SYSTEM,
    messages: [{ role: "user", content: [...toSearchResults(hits), { type: "text", text: `질문: ${q}` }] }],
  });

  const parts: string[] = [];
  for await (const ev of s) {
    if (ev.type !== "content_block_delta") continue;
    if (ev.delta.type === "text_delta") {
      parts.push(ev.delta.text);
      emit({ type: "token", text: ev.delta.text });
    } else if (ev.delta.type === "citations_delta" && ev.delta.citation.type === "search_result_location") {
      const c = ev.delta.citation;
      const src = sources[c.search_result_index];
      if (src) {
        if (!src.cited.includes(c.cited_text)) src.cited.push(c.cited_text);
        emit({ type: "citation", n: src.n, citedText: c.cited_text });
      }
    }
  }
  const final = await s.finalMessage();
  if (final.stop_reason === "refusal") throw new Error("모델이 요청을 거절했다.");
  const answer = parts.join("");
  const grounded = sources.some((x) => x.cited.length > 0);
  emit({ type: "done", answer, sources, grounded });
  return { answer, sources, grounded };
}
