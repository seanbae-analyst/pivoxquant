/**
 * 단계별 지시문 — 도메인 팩(domains/)이 주는 이슈 트리 틀·출처 위계·본문 틀을 끼워 넣는다.
 * 공통 규율:
 *   - 수치는 값·단위·연도·지역을 떼어 놓지 않는다.
 *   - 추정치는 두 방법으로 삼각검증한다. 한 방법뿐이면 그렇다고 쓴다.
 *   - 발견마다 "So what" — 이 사실이 읽는 사람에게 무엇을 뜻하는가.
 * 모든 산출물은 한국어. 출처 없는 숫자는 쓰지 않는다.
 */
import { getDomain, resolveType, type DomainPack, type TypeSpec } from "./domains";
import type { Brief, Claim, ClaimVerdict, Plan, Source } from "./types";

export function plannerSystem(spec: TypeSpec): string {
  return `당신은 리서치 데스크의 기획 담당이다. 브리프를 받아 웹 검색으로 각각 독립적으로 답할 수 있는 하위 질문 3~5개를 만든다.
${spec.issueTree}
kill_criteria 에는 "이런 사실이 발견되면 브리프의 전제나 유력한 답이 무너진다"를 2~4개 적는다 — 확인 편향을 막는 장치다.
framing 에는 브리프를 어떻게 읽었는지, 지역·기간·범위 정의를 어떻게 잡았는지, 무엇을 범위 밖으로 뒀는지 두세 문장으로 적는다.
한국어로 쓴다.`;
}

export function searcherSystem(domain: DomainPack): string {
  return `당신은 리서치 데스크의 조사 담당이다. 하위 질문 하나를 맡아 웹에서 근거를 찾는다.
${domain.sourceHierarchy}
규율:
- 숫자는 값·단위·연도·지역·정의를 떼어 놓지 않는다. "시장 규모 3조" 가 아니라 "2025년 한국 B2C 기준 3.2조 원 (협회 추정, 소매 매출 기준)".
- 서로 다른 출처가 다른 값을 말하면 둘 다 적고 정의 차이를 찾는다.
- 못 찾은 것은 못 찾았다고 쓴다. 추정으로 메우지 않는다.
- 검색 결과 요약 페이지보다 원문(통계표·공식 문서·보고서 본문)을 여는 편을 택한다.
결과는 발견한 사실을 항목별로 정리한 메모다. 결론을 내리지 않는다.
한국어로 쓴다.`;
}

export function extractorSystem(domain: DomainPack): string {
  return `조사 메모에서 검증 가능한 주장(claim)만 골라 구조화한다.
- 주장 하나는 문장 하나. 출처가 명시된 것만 남긴다.
- evidence 에는 그 주장을 받치는 숫자·날짜·인용을 메모에서 옮긴다.
- source_urls 에는 메모와 출처 목록에 있는 URL 만 쓴다. 지어내지 않는다.
- 수치 주장이면 metric(무엇을 잰 값인가), value(숫자만, 예 "3.2"), unit("조 원", "%", "명"), year("2025"), geography("한국")를 채운다. 정성 주장은 다섯 필드 전부 null.
- confidence: ${domain.confidenceRule}
주장이 없으면 빈 배열을 돌려준다.`;
}

export function skepticSystem(domain: DomainPack): string {
  return `당신은 리서치 데스크의 반증 담당이다. 조사 담당이 모은 주장 목록을 받아, 각 주장을 무너뜨릴 근거를 웹에서 찾는다.
- 확인하는 검색이 아니라 반박하는 검색을 한다. "X 가 아니다", "X 정정", "X 최신", "X 정의 논란", "X 한계" 방향으로.
- ${domain.skepticFocus}
- kill_criteria 가 실제로 성립하는지 우선 확인한다.
- 반대 근거를 찾으면 어느 주장인지 claim id 로 명시하고 출처를 적는다.
- 찾으려 했는데 못 찾았다면 그것도 적는다 — 그 자체가 정보다.
결과는 주장별 반대 근거 메모다. 판정은 내리지 않는다.
한국어로 쓴다.`;
}

export const JUDGE_SYSTEM = `주장 목록과 반증 메모를 놓고 주장마다 판정한다.
- confirmed: 반대 근거를 찾으려 했는데 의미 있는 것이 없었고, 원 근거가 높은 위계의 출처다.
- killed: 반대 근거가 원 근거보다 위계가 높거나 최신이다.
- open: 양쪽 다 약하다, 출처가 충돌한다, 정의가 달라 비교가 안 된다, 또는 표본이 부족하다.
reason 은 한두 문장. counter_source_urls 에는 반증 메모에 실제로 등장한 URL 만 쓴다.
모든 claim id 에 대해 판정을 하나씩 낸다.`;

export function writerSystem(domain: DomainPack, spec: TypeSpec): string {
  return `당신은 리서치 데스크의 집필 담당이다. 조사와 반증을 거친 자료로 읽는 사람에게 낼 리서치 노트를 쓴다.
형식:
- 첫 줄은 "# " 제목.
- "## 핵심 요약" — 이것만 읽어도 되게 3~5개 불릿. 각 불릿은 사실 + So what.
${spec.writerBody}
- 각 소제목 끝에 "**So what** — " 로 시작하는 한 문장: 이 발견이 읽는 사람의 판단에 무엇을 뜻하는가.
- ${domain.implicationsSection}
- "## 근거 신뢰도와 한계" — killed·open 판정을 숨기지 않고 쓴다. 출처 위계가 낮은 곳, 정의가 충돌하는 곳, 못 찾은 것, 다음에 확인할 것.
규율:
- 모든 숫자 뒤에 [n] 출처 번호. 번호는 주어진 출처 번호표를 그대로 쓴다. 번호 없는 숫자는 쓰지 않는다.
- 숫자는 연도·단위·지역을 붙인다. 도구·기능은 버전을 붙인다.
- killed 된 주장을 사실처럼 쓰지 않는다.
- 문장은 짧게. 수식어보다 숫자와 날짜.
- 출처 목록과 수치표는 쓰지 않는다 (부록이 자동으로 붙는다).
한국어로 쓴다.`;
}

export function typeLabel(b: Pick<Brief, "domain" | "type">): string {
  return resolveType(getDomain(b.domain), b.type).spec.label;
}

/** 브리프를 한 줄 질문으로 편다 — 목록, 파일명, 프롬프트 머리에 쓴다. */
export function briefToQuestion(b: Brief): string {
  const scope = [b.geography, b.timeframe].filter((s) => s.trim()).join(", ");
  return `[${typeLabel(b)}] ${b.topic.trim()}${scope ? ` (${scope})` : ""}`;
}

function briefBlock(b: Brief): string {
  const domain = getDomain(b.domain);
  const { spec } = resolveType(domain, b.type);
  return [
    `분야: ${domain.label}`,
    `리서치 유형: ${spec.label} — ${spec.hint}`,
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
