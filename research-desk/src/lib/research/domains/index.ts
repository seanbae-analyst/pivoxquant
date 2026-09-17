/**
 * 도메인 팩 등록부. 기본 도메인은 환경변수 NEXT_PUBLIC_RESEARCH_DOMAIN 로 바꾼다
 * (같은 코드로 데이터 사이트, 컨설팅 사이트를 따로 띄울 수 있다).
 */
import { consulting } from "./consulting";
import { data } from "./data";
import type { DomainPack, TypeSpec } from "./types";

export type { DomainPack, TypeSpec } from "./types";

export const DOMAINS: readonly DomainPack[] = [data, consulting];

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
