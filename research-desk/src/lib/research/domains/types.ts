/**
 * 도메인 팩 — 리서치 데스크가 다루는 분야 하나의 정의.
 *
 * 팩 하나 = 리서치 유형 목록(유형마다 이슈 트리 틀 + 노트 본문 틀) + 출처 위계 +
 * 시사점 절의 이름. 파이프라인과 화면은 팩만 읽고, 팩은 파이프라인을 모른다.
 * 새 분야를 더하려면 이 모양의 파일 하나를 domains/ 에 넣고 index.ts 에 등록한다.
 */

export interface TypeSpec {
  /** 화면 칩과 보고서 머리말에 쓰는 이름. */
  label: string;
  /** 칩 아래 한 줄 설명. */
  hint: string;
  /** 주제 입력창의 예시. */
  placeholder: string;
  /** 기획 단계에 넣는 이슈 트리 틀. 하위 질문의 뼈대. */
  issueTree: string;
  /** 집필 단계에 넣는 본문 구조. "## " 소제목 목록. */
  writerBody: string;
}

export interface DomainPack {
  id: string;
  label: string;
  tagline: string;
  /** 유형 id → 정의. 반드시 "custom" 이 하나 있어야 한다 (모르는 유형의 기본값). */
  types: Record<string, TypeSpec>;
  /** 조사·판정 단계가 신뢰도를 매길 때 쓰는 출처 위계 문장. */
  sourceHierarchy: string;
  /** confidence 기준 — 어떤 출처가 high / medium / low 인가. */
  confidenceRule: string;
  /** 시사점 절의 제목과 지시. 컨설팅은 의뢰인 의사결정, 데이터는 실무 적용. */
  implicationsSection: string;
  /** 반증 단계가 우선 확인할 방향 한 줄. */
  skepticFocus: string;
}
