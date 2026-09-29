/**
 * No copy or control may point at a surface that no longer exists
 * (CLAUDE.md "없는 기능을 파는 카피 금지"). 2026-09-29 sweep:
 *   - /watchlist is gone → Settings no longer offers a watchlist CSV.
 *   - /pricing 307s to /mirror → its route code is deleted, not kept dark.
 *   - Settings has no "연동 / Connections" section → brokerOnboarding.note
 *     must not send the user there.
 */
import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import ko from "@/messages/ko.json";
import en from "@/messages/en.json";

const SRC = join(__dirname, "..");

describe("dead-surface copy", () => {
  it("settings offers no watchlist CSV download", () => {
    const src = readFileSync(
      join(SRC, "components", "settings", "v2", "privacy-card-v2.tsx"),
      "utf8",
    );
    expect(src).not.toMatch(/\["watchlist",/);
    expect(src).not.toMatch(/관심종목/);
  });

  it("the /pricing route code is gone", () => {
    expect(existsSync(join(SRC, "app", "pricing"))).toBe(false);
  });

  it("brokerOnboarding.note does not point at a Settings connections section", () => {
    const noteKo = (ko as unknown as { brokerOnboarding: { note: string } }).brokerOnboarding.note;
    const noteEn = (en as unknown as { brokerOnboarding: { note: string } }).brokerOnboarding.note;
    expect(noteKo).not.toMatch(/설정|연동/);
    expect(noteEn).not.toMatch(/Settings|Connections/);
  });
});
