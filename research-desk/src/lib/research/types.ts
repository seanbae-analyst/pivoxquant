/**
 * 리서치 데스크 — 파이프라인이 주고받는 자료형.
 *
 * 흐름: 질문 → Plan(하위 질문 + 반증 조건) → 하위 질문마다 웹 검색 → Claim 추출
 *      → 반증 검색 → ClaimVerdict → 보고서(markdown).
 *
 * 판정 어휘는 셋뿐이다. confirmed(반대 근거를 찾으려 했는데 못 찾았다),
 * killed(반대 근거가 더 강하다), open(양쪽 다 약하거나 표본이 없다).
 * "정답"을 만들지 않는다 — 근거의 상태만 표시한다.
 */

export type Verdict = "confirmed" | "killed" | "open";
export type Confidence = "high" | "medium" | "low";
export type Effort = "low" | "medium" | "high" | "xhigh" | "max";

export interface Source {
  url: string;
  title: string;
  /** 검색 결과가 알려주는 페이지 나이 ("2 weeks ago" 등). 없으면 null. */
  pageAge: string | null;
}

export interface Plan {
  /** 질문을 어떻게 읽었는지 한두 문장. */
  framing: string;
  subQuestions: string[];
  /** 무엇이 발견되면 이 가설이 무너지는가. 반증 단계가 이 목록을 든다. */
  killCriteria: string[];
}

export interface Claim {
  id: string;
  subQuestion: string;
  text: string;
  /** 출처에서 직접 끌어온 근거 요약. 숫자·날짜는 여기 남긴다. */
  evidence: string;
  sourceUrls: string[];
  confidence: Confidence;
}

export interface ClaimVerdict {
  claimId: string;
  verdict: Verdict;
  reason: string;
  counterSourceUrls: string[];
}

export interface SubResult {
  index: number;
  subQuestion: string;
  notes: string;
  sources: Source[];
  claims: Claim[];
  /** 검색 호출이 실패하면 사유. 성공이면 null. */
  error: string | null;
}

export interface Report {
  id: string;
  question: string;
  createdAt: string;
  model: string;
  plan: Plan;
  claims: Claim[];
  verdicts: ClaimVerdict[];
  sources: Source[];
  /** 집필 단계가 쓴 본문 + 부록(주장 표·출처 목록). */
  markdown: string;
}

export type Stage = "planning" | "searching" | "verifying" | "writing" | "done";

export type ResearchEvent =
  | { type: "status"; stage: Stage; message: string }
  | { type: "plan"; plan: Plan }
  | { type: "sub_done"; index: number; subQuestion: string; claimCount: number; sourceCount: number; error: string | null }
  | { type: "verdicts"; verdicts: ClaimVerdict[] }
  | { type: "token"; text: string }
  | { type: "done"; report: Report }
  | { type: "error"; message: string };

/** 검색 한 턴의 결과 — 모델이 쓴 글 + 그 과정에서 열어 본 출처. */
export interface SearchTurn {
  text: string;
  sources: Source[];
}

/**
 * 파이프라인이 모델에 요구하는 세 가지 원시 동작. 실제 구현은 llm.ts,
 * 테스트는 가짜 구현을 넣는다. 파이프라인 자체는 네트워크를 모른다.
 */
export interface Llm {
  readonly model: string;
  searchTurn(system: string, user: string, opts: { maxSearches: number; effort: Effort }): Promise<SearchTurn>;
  parseJson<T>(schema: import("zod").ZodType<T>, system: string, user: string, effort: Effort): Promise<T>;
  streamText(system: string, user: string, onToken: (text: string) => void): Promise<string>;
}
