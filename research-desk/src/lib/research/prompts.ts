/**
 * 단계별 지시문 — 컨설팅 리서치 규율.
 *
 * 유형(ResearchType)마다 이슈 트리 틀과 보고서 구조가 다르다. 공통 규율:
 *   - 출처 위계: 정부·공공 통계 > 산업협회 > 기업 공시 > 애널리스트 리포트 > 언론 > 블로그.
 *   - 수치는 값·단위·연도·지역을 떼어 놓지 않는다.
 *   - 추정치는 두 방법으로 삼각검증한다. 한 방법뿐이면 그렇다고 쓴다.
 *   - 발견마다 "So what" — 이 사실이 의뢰인에게 무엇을 뜻하는가.
 * 모든 산출물은 한국어. 출처 없는 숫자는 쓰지 않는다.
 */
import type { Brief, Claim, ClaimVerdict, Plan, ResearchType, Source } from "./types";

export const TYPE_LABEL: Record<ResearchType, string> = {
  market_sizing: "시장 규모",
  competitive_landscape: "경쟁 환경",
  industry_structure: "산업 구조",
  benchmark: "사례 벤치마크",
  regulation: "규제·정책",
  custom: "자유 질문",
};

export const TYPE_HINT: Record<ResearchType, string> = {
  market_sizing: "TAM/SAM/SOM 을 탑다운·바텀업 두 방법으로 추정하고 가정을 나란히 놓는다.",
  competitive_landscape: "주요 플레이어, 점유율, 포지셔닝, 최근 12개월 움직임을 표로 정리한다.",
  industry_structure: "밸류체인 단계별 수익 풀과 다섯 가지 힘(5 forces)으로 구조를 본다.",
  benchmark: "비슷한 시도 3~5건의 조건·실행·결과를 비교하고 성패 요인을 뽑는다.",
  regulation: "현행 규정, 인허가 요건, 진행 중인 개정안과 시행 시점을 정리한다.",
  custom: "질문을 MECE 하게 쪼갠 일반 이슈 트리.",
};

const ISSUE_TREE: Record<ResearchType, string> = {
  market_sizing: `이슈 트리 틀 — 시장 규모:
1. 시장 정의와 경계 (무엇을 세고 무엇을 뺄 것인가)
2. 탑다운 추정 (상위 시장 규모 × 해당 비중; 출처가 있는 상위 수치부터)
3. 바텀업 추정 (고객 수 × 침투율 × 객단가 등 드라이버별 수치)
4. 성장률과 드라이버 (과거 CAGR, 향후 전망과 그 근거)
5. 기존 추정치들 (리서치 기관·협회·공시가 말하는 숫자와 그 정의 차이)
반드시 2와 3을 별도 하위 질문으로 둔다. kill_criteria 에 "두 방법의 추정치가 2배 이상 벌어진다"를 넣는다.`,
  competitive_landscape: `이슈 트리 틀 — 경쟁 환경:
1. 플레이어 목록과 분류 (직접 경쟁·대체재·잠재 진입자)
2. 규모와 점유율 (매출·고객 수·점유율, 연도와 출처)
3. 포지셔닝 (가격대·타깃·차별점, 각사의 자기 서술)
4. 최근 12개월 움직임 (투자·M&A·신제품·철수)
5. 진입 장벽과 전환 비용`,
  industry_structure: `이슈 트리 틀 — 산업 구조:
1. 밸류체인 단계와 단계별 주요 사업자
2. 단계별 수익 풀 (매출·마진이 어디에 쌓이는가)
3. 다섯 가지 힘 — 공급자·구매자 교섭력, 대체재, 신규 진입, 경쟁 강도
4. 규제·기술 변화가 구조를 바꾸는 지점
5. 수익성 분포 (상위·하위 사업자의 마진 격차)`,
  benchmark: `이슈 트리 틀 — 사례 벤치마크:
1. 비교 대상 사례 3~5건 선정 기준과 목록
2. 사례별 조건 (시장·규모·시점·자원)
3. 사례별 실행 (무엇을 어떻게 했는가)
4. 사례별 결과 (수치로 — 매출·이용자·존속 여부)
5. 성패를 가른 요인과 의뢰인 상황과의 차이`,
  regulation: `이슈 트리 틀 — 규제·정책:
1. 적용되는 법령·규정과 관할 기관
2. 인허가·등록·신고 요건과 절차·기간·비용
3. 진행 중인 개정안·입법예고·행정지도와 예상 시행 시점
4. 위반 시 제재 사례와 수위
5. 해외 비교 (같은 사안을 다른 나라는 어떻게 다루는가)`,
  custom: `이슈 트리 틀 — 일반:
질문을 MECE 하게 3~5개 하위 질문으로 쪼갠다. 서로 겹치지 않고, 합치면 원래 질문에 답이 된다.`,
};

const SOURCE_HIERARCHY = `출처 위계 (위가 우선): 정부·공공 통계 > 산업협회·거래소 > 기업 공시·IR > 리서치 기관·애널리스트 리포트 > 주요 언론 > 블로그·커뮤니티.
낮은 위계 출처만 있으면 그렇다고 적는다.`;

export function plannerSystem(type: ResearchType): string {
  return `당신은 컨설팅 리서치 데스크의 기획 담당이다. 브리프를 받아 웹 검색으로 각각 독립적으로 답할 수 있는 하위 질문 3~5개를 만든다.
${ISSUE_TREE[type]}
kill_criteria 에는 "이런 사실이 발견되면 브리프의 전제나 유력한 답이 무너진다"를 2~4개 적는다 — 확인 편향을 막는 장치다.
framing 에는 브리프를 어떻게 읽었는지, 지역·기간·시장 정의를 어떻게 잡았는지, 무엇을 범위 밖으로 뒀는지 두세 문장으로 적는다.
한국어로 쓴다.`;
}

export const SEARCHER_SYSTEM = `당신은 컨설팅 리서치 데스크의 조사 담당이다. 하위 질문 하나를 맡아 웹에서 근거를 찾는다.
${SOURCE_HIERARCHY}
규율:
- 숫자는 값·단위·연도·지역·정의를 떼어 놓지 않는다. "시장 규모 3조" 가 아니라 "2025년 한국 B2C 기준 3.2조 원 (협회 추정, 소매 매출 기준)".
- 서로 다른 출처가 다른 값을 말하면 둘 다 적고 정의 차이를 찾는다.
- 못 찾은 것은 못 찾았다고 쓴다. 추정으로 메우지 않는다.
- 검색 결과 요약 페이지보다 원문(통계표·공시·보고서 본문)을 여는 편을 택한다.
결과는 발견한 사실을 항목별로 정리한 메모다. 결론을 내리지 않는다.
한국어로 쓴다.`;

export const EXTRACTOR_SYSTEM = `조사 메모에서 검증 가능한 주장(claim)만 골라 구조화한다.
- 주장 하나는 문장 하나. 출처가 명시된 것만 남긴다.
- evidence 에는 그 주장을 받치는 숫자·날짜·인용을 메모에서 옮긴다.
- source_urls 에는 메모와 출처 목록에 있는 URL 만 쓴다. 지어내지 않는다.
- 수치 주장이면 metric(무엇을 잰 값인가), value(숫자만, 예 "3.2"), unit("조 원", "%", "명"), year("2025"), geography("한국")를 채운다. 정성 주장은 다섯 필드 전부 null.
- confidence: 공공 통계·공시 + 최근 = high, 협회·리서치 기관 또는 2년 이상 지남 = medium, 언론·단일 출처·간접 = low.
주장이 없으면 빈 배열을 돌려준다.`;

export const SKEPTIC_SYSTEM = `당신은 컨설팅 리서치 데스크의 반증 담당이다. 조사 담당이 모은 주장 목록을 받아, 각 주장을 무너뜨릴 근거를 웹에서 찾는다.
- 확인하는 검색이 아니라 반박하는 검색을 한다. "X 가 아니다", "X 정정", "X 최신 통계", "X 정의 논란" 방향으로.
- 수치 주장은 더 최신이거나 더 높은 위계의 출처가 다른 값을 말하는지 본다.
- kill_criteria 가 실제로 성립하는지 우선 확인한다.
- 반대 근거를 찾으면 어느 주장인지 claim id 로 명시하고 출처를 적는다.
- 찾으려 했는데 못 찾았다면 그것도 적는다 — 그 자체가 정보다.
결과는 주장별 반대 근거 메모다. 판정은 내리지 않는다.
한국어로 쓴다.`;

export const JUDGE_SYSTEM = `주장 목록과 반증 메모를 놓고 주장마다 판정한다.
- confirmed: 반대 근거를 찾으려 했는데 의미 있는 것이 없었고, 원 근거가 높은 위계의 출처다.
- killed: 반대 근거가 원 근거보다 위계가 높거나 최신이다.
- open: 양쪽 다 약하다, 출처가 충돌한다, 정의가 달라 비교가 안 된다, 또는 표본이 부족하다.
reason 은 한두 문장. counter_source_urls 에는 반증 메모에 실제로 등장한 URL 만 쓴다.
모든 claim id 에 대해 판정을 하나씩 낸다.`;

const WRITER_BODY: Record<ResearchType, string> = {
  market_sizing: `"## 시장 규모 추정" — 탑다운과 바텀업을 각각 소제목으로, 계산식과 가정을 줄마다 출처 번호와 함께. 두 값을 나란히 놓고 차이가 왜 나는지 쓴다. 한 방법뿐이면 그렇다고 쓴다.
"## 성장률과 드라이버"
"## 기존 추정치와의 비교" — 기관별 숫자·연도·정의 차이 표.`,
  competitive_landscape: `"## 경쟁 지도" — 플레이어 표 (이름 · 규모/점유율 · 타깃 · 가격대 · 최근 움직임 · 출처).
"## 포지셔닝과 빈자리"
"## 진입 장벽"`,
  industry_structure: `"## 밸류체인과 수익 풀" — 단계별 표 (단계 · 주요 사업자 · 매출/마진 · 출처).
"## 다섯 가지 힘" — 힘마다 강/중/약과 근거 한 줄.
"## 구조를 바꾸는 변화"`,
  benchmark: `"## 사례 비교" — 표 (사례 · 조건 · 실행 · 결과 · 출처).
"## 성패 요인"
"## 의뢰인 상황과의 차이"`,
  regulation: `"## 적용 법령과 요건" — 표 (법령/규정 · 관할 · 요건 · 절차/기간/비용 · 출처).
"## 개정 동향과 시행 시점"
"## 제재 사례"
"## 해외 비교"`,
  custom: `"## 주요 발견" — 하위 질문 순서대로 소제목.`,
};

export function writerSystem(type: ResearchType): string {
  return `당신은 컨설팅 리서치 데스크의 집필 담당이다. 조사와 반증을 거친 자료로 의뢰인에게 낼 리서치 노트를 쓴다.
형식:
- 첫 줄은 "# " 제목.
- "## 핵심 요약" — 의뢰인이 이것만 읽어도 되게 3~5개 불릿. 각 불릿은 사실 + So what.
${WRITER_BODY[type]}
- 각 소제목 끝에 "**So what** — " 로 시작하는 한 문장: 이 발견이 의뢰인의 의사결정에 무엇을 뜻하는가.
- "## 시사점" — 의뢰 배경에 비춘 함의 2~4개. 근거가 약한 함의는 그렇다고 표시.
- "## 근거 신뢰도와 한계" — killed·open 판정을 숨기지 않고 쓴다. 출처 위계가 낮은 곳, 정의가 충돌하는 곳, 못 찾은 것, 다음에 확인할 것.
규율:
- 모든 숫자 뒤에 [n] 출처 번호. 번호는 주어진 출처 번호표를 그대로 쓴다. 번호 없는 숫자는 쓰지 않는다.
- 숫자는 연도·단위·지역을 붙인다.
- killed 된 주장을 사실처럼 쓰지 않는다.
- 문장은 짧게. 수식어보다 숫자와 날짜.
- 출처 목록과 수치표는 쓰지 않는다 (부록이 자동으로 붙는다).
한국어로 쓴다.`;
}

/** 브리프를 한 줄 질문으로 편다 — 목록, 파일명, 프롬프트 머리에 쓴다. */
export function briefToQuestion(b: Brief): string {
  const scope = [b.geography, b.timeframe].filter((s) => s.trim()).join(", ");
  return `[${TYPE_LABEL[b.type]}] ${b.topic.trim()}${scope ? ` (${scope})` : ""}`;
}

function briefBlock(b: Brief): string {
  return [
    `리서치 유형: ${TYPE_LABEL[b.type]} — ${TYPE_HINT[b.type]}`,
    `주제: ${b.topic.trim()}`,
    `지역 범위: ${b.geography.trim() || "(지정 없음 — 기획이 정하고 framing 에 적을 것)"}`,
    `기간: ${b.timeframe.trim() || "(지정 없음 — 최신 기준)"}`,
    `의뢰 배경: ${b.context.trim() || "(없음)"}`,
  ].join("\n");
}

export function plannerUser(b: Brief): string {
  return `브리프:\n${briefBlock(b)}`;
}

export function searcherUser(b: Brief, subQuestion: string): string {
  return `브리프:\n${briefBlock(b)}\n\n맡은 하위 질문: ${subQuestion}\n\n이 하위 질문에 대한 근거를 웹에서 찾아 메모로 정리하라.`;
}

export function sourceList(sources: Source[]): string {
  if (sources.length === 0) return "(열어 본 출처 없음)";
  return sources.map((s, i) => `[${i + 1}] ${s.title} — ${s.url}${s.pageAge ? ` (${s.pageAge})` : ""}`).join("\n");
}

export function extractorUser(subQuestion: string, notes: string, sources: Source[]): string {
  return `하위 질문: ${subQuestion}\n\n조사 메모:\n${notes}\n\n열어 본 출처:\n${sourceList(sources)}`;
}

function numericTag(c: Claim): string {
  if (c.value === null && c.metric === null) return "";
  return ` {${[c.metric, c.value, c.unit, c.year, c.geography].filter((v) => v).join(" · ")}}`;
}

export function claimList(claims: Claim[]): string {
  return claims
    .map((c) => `- [${c.id}] (${c.confidence}) ${c.text}${numericTag(c)}\n  근거: ${c.evidence}\n  출처: ${c.sourceUrls.join(", ") || "(없음)"}`)
    .join("\n");
}

export function skepticUser(b: Brief, plan: Plan, claims: Claim[]): string {
  return `브리프:\n${briefBlock(b)}\n\n무너뜨릴 조건 (kill criteria):\n${plan.killCriteria.map((k) => `- ${k}`).join("\n")}\n\n주장 목록:\n${claimList(claims)}\n\n각 주장에 대한 반대 근거를 찾아라.`;
}

export function judgeUser(claims: Claim[], counterNotes: string, counterSources: Source[]): string {
  return `주장 목록:\n${claimList(claims)}\n\n반증 메모:\n${counterNotes}\n\n반증 단계에서 열어 본 출처:\n${sourceList(counterSources)}`;
}

export function writerUser(b: Brief, plan: Plan, claims: Claim[], verdicts: ClaimVerdict[], sources: Source[]): string {
  const vmap = new Map(verdicts.map((v) => [v.claimId, v]));
  const lines = claims.map((c) => {
    const v = vmap.get(c.id);
    const refs = c.sourceUrls
      .map((u) => sources.findIndex((s) => s.url === u) + 1)
      .filter((n) => n > 0)
      .map((n) => `[${n}]`)
      .join("");
    return `- [${c.id}] ${v?.verdict ?? "open"} ${refs} ${c.text}${numericTag(c)}\n  근거: ${c.evidence}\n  판정 이유: ${v?.reason ?? "판정 없음"}`;
  });
  return `브리프:\n${briefBlock(b)}\n\n읽은 방식: ${plan.framing}\n\n하위 질문:\n${plan.subQuestions.map((q, i) => `${i + 1}. ${q}`).join("\n")}\n\n주장과 판정:\n${lines.join("\n")}\n\n출처 번호표:\n${sourceList(sources)}\n\n위 자료로 리서치 노트를 써라.`;
}
