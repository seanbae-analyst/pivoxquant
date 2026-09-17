/**
 * Server-Sent Events 인코딩/디코딩 — 서버와 브라우저가 같은 파일을 쓴다.
 * 한 이벤트 = `data: <json>\n\n`. 브라우저는 POST 로 시작하므로 EventSource 대신
 * fetch 스트림을 직접 읽는다 (SseParser).
 */
import type { ResearchEvent } from "./types";

export function encodeEvent(ev: object): string {
  return `data: ${JSON.stringify(ev)}\n\n`;
}

/** 조각난 청크를 이어 붙여 완전한 이벤트만 내놓는다. T 는 이벤트 합집합 (기본 ResearchEvent). */
export class SseParser<T extends { type: string } = ResearchEvent> {
  private buffer = "";

  push(chunk: string): T[] {
    this.buffer += chunk;
    const out: T[] = [];
    let idx: number;
    while ((idx = this.buffer.indexOf("\n\n")) !== -1) {
      const frame = this.buffer.slice(0, idx);
      this.buffer = this.buffer.slice(idx + 2);
      for (const line of frame.split("\n")) {
        if (!line.startsWith("data:")) continue;
        const json = line.slice(5).trim();
        if (!json) continue;
        try {
          out.push(JSON.parse(json) as T);
        } catch {
          out.push({ type: "error", message: "이벤트를 해석하지 못했다." } as unknown as T);
        }
      }
    }
    return out;
  }
}
