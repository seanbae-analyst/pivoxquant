/**
 * Landing Import Inbox section — copy parity + claim limits.
 *
 * import-inbox-preview.tsx reads every string from `landing.inbox` via useT().
 * A key missing in one locale renders the raw key on the page, so both locales
 * must carry the same keys. The screenshot path (p4, PR #594) may only claim
 * "major brokers' fill screens" — never every broker — and must not say the
 * image reaches the server.
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import ko from "@/messages/ko.json";
import en from "@/messages/en.json";

const inboxKo = (ko as { landing: { inbox: Record<string, string> } }).landing.inbox;
const inboxEn = (en as { landing: { inbox: Record<string, string> } }).landing.inbox;

describe("landing.inbox copy", () => {
  it("has identical, non-empty keys in ko and en", () => {
    expect(Object.keys(inboxKo).sort()).toEqual(Object.keys(inboxEn).sort());
    for (const [k, v] of Object.entries({ ...inboxKo, ...inboxEn })) {
      expect(v, k).toBeTruthy();
    }
  });

  it("has title + body for every path the component renders", () => {
    const src = readFileSync(
      join(__dirname, "..", "components", "landing", "import-inbox-preview.tsx"),
      "utf8",
    );
    const keys = [...src.matchAll(/\{ key: "(p\d)", route:/g)].map((m) => m[1]);
    expect(keys).toEqual(["p1", "p4", "p2", "p3"]);
    for (const k of keys) {
      expect(inboxKo[`${k}title`]).toBeTruthy();
      expect(inboxKo[`${k}body`]).toBeTruthy();
    }
  });

  it("screenshot copy does not overclaim", () => {
    const text = Object.values(inboxKo).join(" ") + " " + Object.values(inboxEn).join(" ");
    expect(text).not.toMatch(/모든 증권사|every broker|all brokers/i);
    expect(text).not.toMatch(/이미지 파일은 받지 않습니다|Image files are not accepted/);
    expect(inboxKo.p4body).toContain("주요 증권사");
    expect(inboxKo.p4body).toContain("기기 밖으로 나가지 않습니다");
  });
});
