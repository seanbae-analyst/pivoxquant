/**
 * <SampleDataBadge /> — shared "this is illustrative sample data" banner for
 * the 18 PDF report templates.
 *
 * WHY (CEO 2026-05-31 직격 버그):
 *   The public /sample-reports/[slug] routes render each template with its
 *   hardcoded `DEFAULT` fixture (no auth, no real holdings). Those fixtures
 *   carry concrete-looking performance numbers (e.g. "FY RETURN +18.4%",
 *   "NVDA +22.4% RIGHT", author "홍길동"). Rendered on a public marketing
 *   surface WITHOUT a prominent label, a visitor can mistake the sample for
 *   real product performance — which damages trust and risks 표시·광고법
 *   (허위·과장 성과표시).
 *
 *   Previously only 3 of 18 templates (earnings-prebrief / dd-checklist /
 *   brag-card) carried an inline bronze SAMPLE banner. This component extracts
 *   that exact pattern so all 18 templates label themselves consistently.
 *
 * RULES:
 *   - Render ONLY in sample mode (template falling back to its DEFAULT
 *     fixture, i.e. no real `data` prop). Real members viewing their own
 *     report must NOT see this badge.
 *   - Placed prominently near the cover/header, BEFORE the first metric block.
 *   - NO `data-print-hidden` — the badge MUST also appear on the printed /
 *     exported PDF so a saved sample PDF cannot be passed off as real.
 *
 * DESIGN: v3 락-인 tokens only — bronze tint box, mono eyebrow, uppercase.
 *   Reuses the exact tokens the original inline banners used
 *   (rgba(184,149,106,0.08) fill + 0.4 border + var(--r-gold-deep) ink).
 */

import * as React from "react";

export function SampleDataBadge({
  style,
}: {
  /** Optional style overrides (e.g. margin tuning per template). */
  style?: React.CSSProperties;
}) {
  return (
    <div
      role="note"
      data-pq-sample-badge="true"
      style={{
        margin: "12px 0 4px",
        padding: "10px 14px",
        background: "rgba(184, 149, 106, 0.08)",
        border: "1px solid rgba(184, 149, 106, 0.4)",
        borderRadius: 2,
        fontSize: "var(--pq-text-eyebrow)",
        letterSpacing: "0.18em",
        textTransform: "uppercase",
        color: "var(--r-gold-deep, #8b6f47)",
        ...style,
      }}
      className="font-mono"
    >
      ▍ 예시 · 가상 포트폴리오 — 실제 보유·실적 데이터가 아닙니다
      {"  ·  "}
      SAMPLE — illustrative data, not real holdings or performance
    </div>
  );
}

export default SampleDataBadge;
