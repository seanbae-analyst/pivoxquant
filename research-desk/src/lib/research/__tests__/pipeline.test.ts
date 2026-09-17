import { describe, expect, it } from "vitest";
import type { ZodType } from "zod";
import { normalizeVerdicts, runResearch, toClaims } from "../pipeline";
import { ClaimsSchema, PlanSchema, VerdictsSchema } from "../schemas";
import type { Effort, Llm, ResearchEvent, Source } from "../types";

const A: Source = { url: "https://a.example", title: "A", pageAge: null };
const B: Source = { url: "https://b.example", title: "B", pageAge: null };
const X: Source = { url: "https://x.example", title: "X", pageAge: null };

/** 가짜 모델 — 어떤 스키마를 요구받았는지로 단계를 구분한다. */
function fakeLlm(overrides: Partial<Llm> = {}): Llm & { calls: string[] } {
  const calls: string[] = [];
  return {
    model: "fake-model",
    calls,
    async searchTurn(system, user, opts) {
      calls.push(`search:${opts.maxSearches}`);
      if (system.includes("반증")) return { text: "C1.1 에 대한 반대 근거: X 가 다르게 말한다", sources: [X] };
      if (user.includes("둘째")) throw new Error("검색 실패");
      return { text: `메모: ${user}`, sources: [A, B] };
    },
    async parseJson<T>(schema: ZodType<T>, _system: string, user: string, effort: Effort): Promise<T> {
      calls.push(`parse:${effort}`);
      if (Object.is(schema, PlanSchema)) {
        return { framing: "이렇게 읽었다", sub_questions: ["첫째 질문", "둘째 질문", "셋째", "넷째", "다섯째", "여섯째"], kill_criteria: ["K1"] } as T;
      }
      if (Object.is(schema, ClaimsSchema)) {
        return {
          claims: [
            { text: "주장 하나", evidence: "근거", source_urls: ["https://a.example", "https://fake.example"], confidence: "high" },
            { text: "   ", evidence: "", source_urls: [], confidence: "low" },
          ],
        } as T;
      }
      if (Object.is(schema, VerdictsSchema)) {
        return { verdicts: [{ claim_id: "C1.1", verdict: "killed", reason: "X 가 더 최신", counter_source_urls: ["https://x.example", "https://nope.example"] }] } as T;
      }
      throw new Error(`unknown schema in ${user.slice(0, 20)}`);
    },
    async streamText(_system, _user, onToken) {
      calls.push("write");
      onToken("# 제목\n");
      onToken("## 한 줄 답\n본문");
      return "# 제목\n## 한 줄 답\n본문";
    },
    ...overrides,
  };
}

describe("runResearch", () => {
  it("계획→조사→반증→집필 순서로 이벤트를 내고, 실패한 하위 질문을 건너뛴 채 보고서를 만든다", async () => {
    const llm = fakeLlm();
    const events: ResearchEvent[] = [];
    const report = await runResearch("  질문?  ", llm, (ev) => events.push(ev), {
      maxSubQuestions: 3,
      maxSearches: 4,
      now: () => new Date("2026-09-17T00:00:00Z"),
      id: () => "r1",
    });

    // 하위 질문은 상한에서 잘린다
    expect(report.plan.subQuestions).toEqual(["첫째 질문", "둘째 질문", "셋째"]);
    // 둘째는 검색 실패 → 주장 0, 나머지 둘은 주장 1건씩 (빈 주장은 버려짐)
    const subDone = events.filter((e) => e.type === "sub_done");
    expect(subDone.map((e) => (e.type === "sub_done" ? [e.index, e.claimCount, e.error] : null))).toEqual(
      expect.arrayContaining([
        [0, 1, null],
        [1, 0, "검색 실패"],
        [2, 1, null],
      ]),
    );
    expect(report.claims.map((c) => c.id)).toEqual(["C1.1", "C3.1"]);
    // 지어낸 URL 은 걸러진다
    expect(report.claims[0].sourceUrls).toEqual(["https://a.example"]);
    // 판정: C1.1 은 killed, C3.1 은 판정이 없어 open 으로 채워진다
    expect(report.verdicts).toEqual([
      { claimId: "C1.1", verdict: "killed", reason: "X 가 더 최신", counterSourceUrls: ["https://x.example"] },
      { claimId: "C3.1", verdict: "open", reason: "판정 단계가 이 주장을 다루지 않았다.", counterSourceUrls: [] },
    ]);
    // 출처는 조사 + 반증을 합친 것
    expect(report.sources.map((s) => s.url)).toEqual(["https://a.example", "https://b.example", "https://x.example"]);
    // 반증 검색은 maxSearches + 2
    expect(llm.calls).toContain("search:6");
    // 보고서 = 머리말 + 본문 + 부록
    expect(report.markdown).toContain("> 질문: 질문?");
    expect(report.markdown).toContain("## 한 줄 답");
    expect(report.markdown).toContain("## 부록 A — 주장과 판정");
    expect(report.markdown).toContain("3. [X](https://x.example)");
    expect(report.model).toBe("fake-model");

    const stages = events.filter((e) => e.type === "status").map((e) => (e.type === "status" ? e.stage : ""));
    expect(stages).toEqual(["planning", "searching", "verifying", "writing", "done"]);
    expect(events.filter((e) => e.type === "token").length).toBe(2);
    expect(events.at(-1)).toEqual({ type: "done", report });
  });

  it("조사가 전부 실패하면 던진다", async () => {
    const llm = fakeLlm({
      async searchTurn() {
        throw new Error("네트워크");
      },
    });
    await expect(runResearch("q", llm, () => {})).rejects.toThrow("조사 단계가 전부 실패했다: 네트워크");
  });

  it("주장이 하나도 없으면 반증 단계를 건너뛰고 빈 판정으로 쓴다", async () => {
    const llm = fakeLlm({
      async parseJson<T>(schema: ZodType<T>): Promise<T> {
        if (Object.is(schema, PlanSchema)) return { framing: "f", sub_questions: ["a"], kill_criteria: [] } as T;
        if (Object.is(schema, ClaimsSchema)) return { claims: [] } as T;
        throw new Error("반증 판정이 호출되면 안 된다");
      },
    });
    const events: ResearchEvent[] = [];
    const report = await runResearch("q", llm, (ev) => events.push(ev));
    expect(report.verdicts).toEqual([]);
    expect(events.some((e) => e.type === "status" && e.stage === "verifying")).toBe(false);
    expect(report.markdown).toContain("검증 가능한 주장을 추출하지 못했다.");
  });

  it("빈 질문과 빈 계획은 거부한다", async () => {
    await expect(runResearch("   ", fakeLlm(), () => {})).rejects.toThrow("질문이 비어 있다.");
    const llm = fakeLlm({
      async parseJson<T>(): Promise<T> {
        return { framing: "", sub_questions: ["  "], kill_criteria: [] } as T;
      },
    });
    await expect(runResearch("q", llm, () => {})).rejects.toThrow("하위 질문을 내놓지 않았다");
  });
});

describe("helpers", () => {
  it("toClaims 는 id 를 붙이고 모르는 URL 을 버린다", () => {
    const out = toClaims(1, "sq", { claims: [{ text: " t ", evidence: " e ", source_urls: ["u", "z"], confidence: "medium" }] }, [{ url: "u", title: "U", pageAge: null }]);
    expect(out).toEqual([{ id: "C2.1", subQuestion: "sq", text: "t", evidence: "e", sourceUrls: ["u"], confidence: "medium" }]);
  });
  it("normalizeVerdicts 는 중복 id 의 첫 판정만 쓴다", () => {
    const claims = toClaims(0, "sq", { claims: [{ text: "a", evidence: "", source_urls: [], confidence: "low" }] }, []);
    const out = normalizeVerdicts(
      claims,
      { verdicts: [{ claim_id: "C1.1", verdict: "confirmed", reason: "첫", counter_source_urls: [] }, { claim_id: "C1.1", verdict: "killed", reason: "둘", counter_source_urls: [] }, { claim_id: "C9.9", verdict: "open", reason: "", counter_source_urls: [] }] },
      [],
    );
    expect(out).toEqual([{ claimId: "C1.1", verdict: "confirmed", reason: "첫", counterSourceUrls: [] }]);
  });
});
