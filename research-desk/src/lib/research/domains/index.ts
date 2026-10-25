/**
 * 도메인 팩 등록부.
 *   NEXT_PUBLIC_RESEARCH_DOMAINS  노출할 분야 목록 (쉼표 구분, 예 "data"). 비면 전부.
 *   NEXT_PUBLIC_RESEARCH_DOMAIN   기본 분야. 비면 노출 목록의 첫 번째.
 * 같은 코드로 데이터 전용 사이트("data")와 컨설팅 사이트를 따로 띄울 수 있다.
 */
import { consulting } from "./consulting";
import { data } from "./data";
import type { DomainPack, TypeSpec } from "./types";

export type { DomainPack, TypeSpec } from "./types";

const ALL: readonly DomainPack[] = [data, consulting];

/** 환경변수로 노출 분야를 고른다. 모르는 id 는 무시하고, 하나도 안 남으면 전부. */
export function selectDomains(all: readonly DomainPack[], listEnv: string | undefined): readonly DomainPack[] {
  const wanted = (listEnv ?? "").split(",").map((s) => s.trim()).filter(Boolean);
  if (wanted.length === 0) return all;
  const picked = wanted.map((id) => all.find((d) => d.id === id)).filter((d): d is DomainPack => d !== undefined);
  return picked.length ? picked : all;
}

export const DOMAINS: readonly DomainPack[] = selectDomains(ALL, process.env.NEXT_PUBLIC_RESEARCH_DOMAINS);

const BY_ID = new Map(DOMAINS.map((d) => [d.id, d]));

export const DEFAULT_DOMAIN_ID: string =
  (process.env.NEXT_PUBLIC_RESEARCH_DOMAIN && BY_ID.has(process.env.NEXT_PUBLIC_RESEARCH_DOMAIN) ? process.env.NEXT_PUBLIC_RESEARCH_DOMAIN : null) ?? DOMAINS[0].id;

export function getDomain(id: string | null | undefined): DomainPack {
  return (id && BY_ID.get(id)) || BY_ID.get(DEFAULT_DOMAIN_ID)!;
}

export function typeIds(domain: DomainPack): string[] {
  return Object.keys(domain.types);
}

/** 도메인 안에서 유형을 찾는다. 모르는 유형은 그 도메인의 custom. */
export function resolveType(domain: DomainPack, typeId: string | null | undefined): { id: string; spec: TypeSpec } {
  const id = typeId && domain.types[typeId] ? typeId : "custom";
  return { id, spec: domain.types[id] };
}
