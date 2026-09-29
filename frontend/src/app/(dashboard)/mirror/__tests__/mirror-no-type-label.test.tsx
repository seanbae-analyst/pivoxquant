/**
 * /mirror names no type and scores nothing — CEO 2026-09-29.
 *
 * The headline used to read "{성장형}으로 선언하셨는데, 최근 30일은 {균형형}
 * 쪽으로…" with a "선언 ↔ 관찰 정합도 NN%" figure under it. Mirrors show
 * facts, no type labels and no scores (CLAUDE.md "유형 라벨·점수는 만들지
 * 않는다"): the sentence now names the axis where 선언 and 관찰 part most.
 * A stale backend that still sends the old label fields must not bring them
 * back.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";

import type { MirrorHomeResponse } from "@/lib/types";
import { MirrorHeadline, leadSentence } from "@/components/mirror/mirror-headline";

const BUCKETS = ["성장형", "균형형", "수익형", "Growth", "Balanced", "Income"];

const base: MirrorHomeResponse = {
  ok: true,
  stage: "observed",
  declared: { source: "self" },
  observed: { trade_count: 12 },
  gap: [
    { key: "holding_period", label: "평균 보유기간", direction: "down", delta: -0.3, declared: 0.8, observed: 0.5 },
    { key: "turnover", label: "매매 회전율", direction: "up", delta: 0.2, declared: 0.2, observed: 0.4 },
  ],
  drift: { available: false, descriptor: null },
  radar: {
    keys: ["holding_period", "turnover", "concentration"],
    labels: ["평균 보유기간", "매매 회전율", "집중도"],
    declared: [0.8, 0.2, 0.4],
    declared_axes: ["holding_period", "turnover"],
    observed: [0.5, 0.4, 0.6],
    observed_axes: ["holding_period", "turnover"],
  },
};

// What an older backend still sends — the client must ignore it.
const stale = {
  ...base,
  declared: { ...base.declared, label: "성장형", tagline: "x" },
  observed: { ...base.observed, label: "균형형", bucket_changed: true },
} as unknown as MirrorHomeResponse;

function text(d: MirrorHomeResponse): string {
  return render(<MirrorHeadline data={d} />).container.textContent ?? "";
}

describe("MirrorHeadline — no type label, no alignment score", () => {
  it("renders no bucket label and no 정합도 / % figure, even from a stale payload", () => {
    for (const d of [base, stale, { ...stale, stage: "new" as const, gap: [] }]) {
      const t = text(d);
      for (const b of BUCKETS) expect(t).not.toContain(b);
      expect(t).not.toContain("정합도");
      expect(t).not.toMatch(/alignment/i);
      expect(t).not.toMatch(/\d+%(?!p)/);
    }
  });

  it("names the axis with the largest gap, direction only", () => {
    expect(leadSentence(base)).toBe(
      "선언과 가장 크게 갈라진 곳: 평균 보유기간 — 최근 30일은 선언보다 짧게 관찰됐어요.",
    );
    const up = { ...base, gap: [base.gap[1]] };
    expect(leadSentence(up)).toBe(
      "선언과 가장 크게 갈라진 곳: 매매 회전율 — 최근 30일은 선언보다 높게 관찰됐어요.",
    );
  });

  it("keeps an insufficient-data state when no axis is comparable", () => {
    const none = {
      ...base,
      gap: [],
      radar: { ...base.radar, observed_axes: ["concentration"] },
    };
    expect(leadSentence(none)).toContain("아직 쌓이지 않았어요");
    const close = { ...base, gap: [] };
    expect(leadSentence(close)).toContain("크게 다르지 않게");
    expect(leadSentence({ ...base, stage: "new", gap: [] })).toContain("거래가 쌓이면");
  });

  it("source reads no label field and computes no alignment", () => {
    const src = readFileSync(
      join(__dirname, "..", "..", "..", "..", "components", "mirror", "mirror-headline.tsx"),
      "utf8",
    );
    expect(src).not.toMatch(/declared\.label|observed\.label|bucket_changed/);
    expect(src).not.toMatch(/alignmentPct/);
    expect(src).not.toContain("선언 ↔ 관찰 정합도");
  });
});
