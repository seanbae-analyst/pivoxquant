/**
 * 지식 베이스(KB) 자료형.
 *
 * 흐름: SourceConfig(수집 대상) → crawl → Doc(페이지) → chunk → Chunk(조각) → embed → KbStore
 *      질문 → embedQuery → store.search(하이브리드) → rerank → search_result 블록 → Claude 답변(인용)
 */

export type SourceKind = "sitemap" | "rss" | "urls";

/** kb/sources.yaml 의 한 항목. */
export interface SourceConfig {
  id: string;
  name: string;
  kind: SourceKind;
  /** sitemap.xml / RSS 피드 / 시작 URL 목록. */
  url?: string;
  urls?: string[];
  /** 포함할 경로 정규식(문자열). 비면 전부. */
  include?: string[];
  /** 제외할 경로 정규식(문자열). */
  exclude?: string[];
  /** 한 번의 수집에서 가져올 최대 페이지 수. */
  maxPages: number;
  /** 출처 위계 라벨 — 답변 화면과 프롬프트에 그대로 보인다. */
  tier: "standard" | "official_docs" | "paper" | "engineering_blog" | "analyst" | "vendor" | "community";
  /** 이 출처의 언어. 답변 언어 선택에 참고. */
  lang?: string;
}

export interface Doc {
  id: string;            // sha1(url)
  sourceId: string;
  url: string;
  title: string;
  text: string;          // 본문(마크다운 비슷한 평문)
  contentHash: string;   // sha1(text) — 변경 감지
  fetchedAt: string;     // ISO
}

export interface Chunk {
  id: string;            // `${docId}#${ordinal}`
  docId: string;
  sourceId: string;
  url: string;
  title: string;
  /** 조각이 속한 소제목 경로 ("설치 > 요구사항"). 인용 제목에 붙인다. */
  heading: string;
  ordinal: number;
  text: string;
  fetchedAt: string;
  embedding?: Float32Array;
}

export interface Retrieved {
  chunk: Chunk;
  /** 하이브리드 점수 (0~1 근사). 재정렬 뒤엔 재정렬 점수. */
  score: number;
}

export interface KbStats {
  docs: number;
  chunks: number;
  sources: Array<{ sourceId: string; docs: number; chunks: number; lastFetchedAt: string | null }>;
}

export interface KbStore {
  upsertDoc(doc: Doc, chunks: Chunk[]): Promise<void>;
  /** 이미 같은 contentHash 로 저장돼 있으면 true — 임베딩을 건너뛴다. */
  hasDoc(docId: string, contentHash: string): Promise<boolean>;
  search(query: { embedding: Float32Array; text: string }, k: number): Promise<Retrieved[]>;
  stats(): Promise<KbStats>;
  close(): Promise<void>;
}

export interface Embedder {
  readonly model: string;
  readonly dimensions: number;
  embedDocuments(texts: string[]): Promise<Float32Array[]>;
  embedQuery(text: string): Promise<Float32Array>;
}

export interface Reranker {
  rerank(query: string, docs: string[], topK: number): Promise<Array<{ index: number; score: number }>>;
}

export interface AnswerSource {
  n: number;             // 답변 안 [n]
  url: string;
  title: string;
  heading: string;
  sourceId: string;
  fetchedAt: string;
  /** 인용된 문장들. 없으면 검색만 됐고 인용은 안 된 것. */
  cited: string[];
}

export type AskEvent =
  | { type: "status"; message: string }
  | { type: "retrieved"; count: number }
  | { type: "token"; text: string }
  | { type: "citation"; n: number; citedText: string }
  | { type: "done"; answer: string; sources: AnswerSource[]; grounded: boolean }
  | { type: "error"; message: string };
