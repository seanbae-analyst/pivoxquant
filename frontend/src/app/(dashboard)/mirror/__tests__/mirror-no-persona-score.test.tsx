/**
 * /mirror renders no persona score — 2026-09-29.
 *
 * The collapsed 「자세히」 area held PersonaEvolution: a 12-week 0–100
 * "Weekly persona score" line with a "Persona score N" tooltip. Mirrors make
 * no scores, grades or type labels (CLAUDE.md "유형 라벨·점수는 만들지 않는다"),
 * so the chart, its section and the `sparkline` field that fed it are gone.
 * Even if a stale cached persona payload still carries a sparkline, nothing
 * on the page may render it.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import type { MirrorHomeResponse } from "@/lib/types";

const payload: MirrorHomeResponse = {
  ok: true,
  stage: "observed",
  declared: { label: "성장형", tagline: "x", source: "self" },
  observed: { label: "균형형", bucket_changed: true, trade_count: 12 },
  gap: [
    {
      key: "holding_period",
      label: "평균 보유기간",
      direction: "down",
      delta: 0.3,
      declared: 0.8,
      observed: 0.5,
    },
  ],
  drift: { available: true, descriptor: "이동 중" },
  radar: {
    keys: ["holding_period", "turnover", "concentration"],
    labels: ["평균 보유기간", "회전율", "집중도"],
    declared: [0.8, 0.2, 0.4],
    observed: [0.5, 0.4, 0.6],
  },
};

vi.mock("@/lib/auth", () => ({ useAuth: () => ({ loading: false }) }));
vi.mock("@/lib/hooks", () => ({
  useMirrorHome: () => ({ data: payload, isLoading: false, error: null }),
}));
// A stale cache could still hold the old score series — it must not surface.
vi.mock("@/lib/cfo/hooks", async (orig) => ({
  ...(await orig<typeof import("@/lib/cfo/hooks")>()),
  usePersona: () => ({
    data: {
      declared: { persona: "growth", label: "성장형", tagline: "x" },
      observed: {},
      sparkline: [{ week: "2026-09-01", score: 73 }],
      last_computed_at: null,
    },
    isLoading: false,
  }),
  usePulse: () => ({ data: { history: [] } }),
}));

import MirrorPage from "@/app/(dashboard)/mirror/page";

describe("/mirror — no persona score", () => {
  it("renders no score, score chart or 자세히 toggle", () => {
    const { container } = render(<MirrorPage />);
    // Open every expander that exists, in case a details area comes back.
    for (const b of screen.queryAllByRole("button", { expanded: false })) {
      fireEvent.click(b);
    }
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/persona score/i);
    expect(text).not.toMatch(/페르소나 점수/);
    expect(text).not.toMatch(/has drifted/i);
    expect(text).not.toContain("자세히");
    expect(container.querySelector(".pq-persona-evolution")).toBeNull();
    expect(screen.queryByText("73")).toBeNull();
  });

  it("page source mounts neither PersonaEvolution nor MirrorDetails", () => {
    const src = readFileSync(join(__dirname, "..", "page.tsx"), "utf8");
    expect(src).not.toMatch(/import .*PersonaEvolution/);
    expect(src).not.toMatch(/<MirrorDetails|<PersonaEvolution/);
  });
});
