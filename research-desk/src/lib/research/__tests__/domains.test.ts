import { describe, expect, it } from "vitest";
import { DEFAULT_DOMAIN_ID, DOMAINS, getDomain, resolveType, selectDomains, typeIds } from "../domains";

describe("도메인 팩", () => {
  it("모든 팩에 custom 유형이 있고, 유형마다 틀·본문·예시가 비어 있지 않다", () => {
    expect(DOMAINS.length).toBeGreaterThanOrEqual(2);
    for (const d of DOMAINS) {
      expect(d.types.custom).toBeDefined();
      for (const id of typeIds(d)) {
        const t = d.types[id];
        for (const field of ["label", "hint", "placeholder", "issueTree", "writerBody"] as const) {
          expect(t[field].trim().length, `${d.id}.${id}.${field}`).toBeGreaterThan(0);
        }
        expect(t.writerBody).toContain("## ");
      }
      expect(d.sourceHierarchy).toContain(">");
      expect(d.implicationsSection).toContain("## ");
    }
  });
  it("기본 도메인은 data 이고, 모르는 id 는 기본 도메인으로 간다", () => {
    expect(DEFAULT_DOMAIN_ID).toBe("data");
    expect(getDomain("nope").id).toBe("data");
    expect(getDomain("consulting").id).toBe("consulting");
    expect(resolveType(getDomain("data"), "ai_ready_data").spec.label).toBe("AI-ready 데이터");
    expect(resolveType(getDomain("data"), "market_sizing").id).toBe("custom");
  });
  it("데이터 팩은 카탈로그·AI-ready·거버넌스·플랫폼·품질·도구 비교를 다룬다", () => {
    expect(typeIds(getDomain("data"))).toEqual(["data_catalog", "ai_ready_data", "governance", "platform", "quality_observability", "tool_comparison", "custom"]);
  });

  it("selectDomains 는 환경변수 목록으로 노출 분야를 고르고, 모르는 id 만 있으면 전부 보여준다", () => {
    expect(selectDomains(DOMAINS, "data").map((d) => d.id)).toEqual(["data"]);
    expect(selectDomains(DOMAINS, " consulting , data ").map((d) => d.id)).toEqual(["consulting", "data"]);
    expect(selectDomains(DOMAINS, "nope").map((d) => d.id)).toEqual(["data", "consulting"]);
    expect(selectDomains(DOMAINS, undefined).length).toBe(2);
  });
});
