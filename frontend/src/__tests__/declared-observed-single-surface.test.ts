/**
 * "선언 대 관찰"은 한 곳(/mirror)에서만 — 2026-09-29.
 *
 * /portfolio 의 RollingWindowWidget 은 /mirror 와 다른 정의로 같은 대비를
 * 그렸다: "Declared · {버킷} {점수}" 의 점수는 `25 + risk_tolerance*7`
 * (유형 점수 — CLAUDE.md 가 금지), 회전율은 `len(trades)/window_days` 비율
 * (저널 회전율 거울은 비율이 없고 건수만 센다), 섹터 기울기는 KR 레지스트리가
 * 모르는 종목을 전부 UNKNOWN 으로 묶은 HHI. 선언 대 관찰의 정본은 /mirror
 * (`declared_vector_json` 9축), 보유기간·회전 건수의 정본은 /journal 거울이다.
 *
 * 이 파일은 두 번째 정의가 돌아오는 길목을 막는다: 엔드포인트 심볼, 위젯
 * 파일, /portfolio 의 마운트, 번역 키.
 */
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { API } from "@/lib/endpoints";

const SRC = join(__dirname, "..");

describe("declared-vs-observed lives only on /mirror", () => {
  it("has no rolling-window endpoint symbol", () => {
    expect(Object.keys(API.profile)).not.toContain("rollingWindow");
  });

  it("has no RollingWindowWidget component", () => {
    expect(existsSync(join(SRC, "components/dashboard/rolling-window.tsx"))).toBe(false);
  });

  it("/portfolio does not mount a declared-vs-observed widget", () => {
    const page = readFileSync(join(SRC, "app/(dashboard)/portfolio/page.tsx"), "utf8");
    expect(page).not.toMatch(/components\/dashboard\/rolling-window|<RollingWindow/);
  });

  it("has no rollingWindow message namespace in either locale", () => {
    for (const loc of ["ko", "en"]) {
      const msgs = JSON.parse(readFileSync(join(SRC, `messages/${loc}.json`), "utf8"));
      expect(msgs).not.toHaveProperty("rollingWindow");
    }
  });
});
