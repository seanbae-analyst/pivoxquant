/**
 * 브라우저 쪽 실행기 — POST 스트림을 읽어 이벤트로 바꾼다. React 를 모른다.
 */
import { SseParser } from "./research/sse";
import type { Brief, ResearchEvent } from "./research/types";

export async function runResearchStream(
  brief: Brief,
  onEvent: (ev: ResearchEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch("/api/research", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(brief),
    signal,
  });
  if (!res.ok || !res.body) {
    let message = `서버 오류 (${res.status})`;
    try {
      const body = (await res.json()) as { error?: string };
      if (body.error) message = body.error;
    } catch {
      /* 본문이 JSON 이 아니면 상태 코드만 */
    }
    throw new Error(message);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SseParser();
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    for (const ev of parser.push(decoder.decode(value, { stream: true }))) onEvent(ev);
  }
}
