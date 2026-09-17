/**
 * Server-Sent Events 인코딩/디코딩 — 서버와 브라우저가 같은 파일을 쓴다.
 * 한 이벤트 = `data: <json>\n\n`. 브라우저는 POST 로 시작하므로 EventSource 대신
 * fetch 스트림을 직접 읽는다 (SseParser).
 */
import type { ResearchEvent } from "./types";

export function encodeEvent(ev: ResearchEvent): string {
  return `data: ${JSON.stringify(ev)}\n\n`;
}

/** 조각난 청크를 이어 붙여 완전한 이벤트만 내놓는다. */
export class SseParser {
  private buffer = "";

  push(chunk: string): ResearchEvent[] {
    this.buffer += chunk;
    const out: ResearchEvent[] = [];
    let idx: number;
    while ((idx = this.buffer.indexOf("\n\n")) !== -1) {
      const frame = this.buffer.slice(0, idx);
      this.buffer = this.buffer.slice(idx + 2);
      for (const line of frame.split("\n")) {
        if (!line.startsWith("data:")) continue;
        const json = line.slice(5).trim();
        if (!json) continue;
        try {
          out.push(JSON.parse(json) as ResearchEvent);
        } catch {
          out.push({ type: "error", message: "이벤트를 해석하지 못했다." });
        }
      }
    }
    return out;
  }
}
