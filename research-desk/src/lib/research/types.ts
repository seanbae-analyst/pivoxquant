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

/** 컨설팅 리서치의 정형 유형. 유형마다 이슈 트리 틀·추출 규칙·보고서 구조가 다르다. */
export type ResearchType =
  | "market_sizing"          // 시장 규모 — TAM/SAM/SOM, 탑다운·바텀업 삼각검증
  | "competitive_landscape"  // 경쟁 환경 — 플레이어, 점유율, 포지셔닝, 최근 움직임
  | "industry_structure"     // 산업 구조 — 밸류체인, 5 forces, 수익 풀
  | "benchmark"              // 사례 벤치마크 — 비슷한 시도의 결과와 조건
  | "regulation"             // 규제·정책 — 현행 규정, 개정 동향, 인허가
  | "custom";                // 자유 질문 — 일반 이슈 트리

export const RESEARCH_TYPES: ResearchType[] = ["market_sizing", "competitive_landscape", "industry_structure", "benchmark", "regulation", "custom"];

/** 사용자가 넣는 리서치 브리프. topic 만 필수. */
export interface Brief {
  type: ResearchType;
  topic: string;
  /** 지역 범위 ("한국", "미국+한국", "글로벌"). 비면 모델이 정하고 framing 에 적는다. */
  geography: string;
  /** 기간 ("2024~2026", "최근 3년"). */
  timeframe: string;
  /** 의뢰 배경 — 누가 왜 묻는가. 시사점의 방향을 정한다. */
  context: string;
}
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
  /** 수치 주장이면 채워진다 — 부록 수치표와 삼각검증에 쓴다. 정성 주장은 전부 null. */
  metric: string | null;
  value: string | null;
  unit: string | null;
  year: string | null;
  geography: string | null;
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
  brief: Brief;
  /** 브리프를 한 줄로 편 것 — 목록·파일명·프롬프트에 쓴다. */
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
