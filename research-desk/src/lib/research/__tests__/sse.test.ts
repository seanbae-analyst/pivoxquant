import { describe, expect, it } from "vitest";
import { SseParser, encodeEvent } from "../sse";
import type { ResearchEvent } from "../types";

describe("SSE 왕복", () => {
  it("청크가 프레임 중간에서 끊겨도 이벤트를 온전히 복원한다", () => {
    const events: ResearchEvent[] = [
      { type: "status", stage: "planning", message: "시작" },
      { type: "token", text: "가\n나" },
      { type: "error", message: "끝" },
    ];
    const wire = events.map(encodeEvent).join("");
    const parser = new SseParser();
    const got: ResearchEvent[] = [];
    for (let i = 0; i < wire.length; i += 7) got.push(...parser.push(wire.slice(i, i + 7)));
    expect(got).toEqual(events);
  });
  it("깨진 JSON 은 error 이벤트로 바꾼다", () => {
    expect(new SseParser().push("data: {nope\n\n")).toEqual([{ type: "error", message: "이벤트를 해석하지 못했다." }]);
  });
});
