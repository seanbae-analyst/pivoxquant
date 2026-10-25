import { SseParser } from "./research/sse";
import type { AskEvent } from "./kb/types";

export async function askStream(question: string, onEvent: (ev: AskEvent) => void, signal?: AbortSignal): Promise<void> {
  const res = await fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }), signal });
  if (!res.ok || !res.body) {
    let message = `서버 오류 (${res.status})`;
    try {
      const body = (await res.json()) as { error?: string };
      if (body.error) message = body.error;
    } catch {
      /* 상태 코드만 */
    }
    throw new Error(message);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SseParser<AskEvent>();
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    for (const ev of parser.push(decoder.decode(value, { stream: true }))) onEvent(ev);
  }
}
