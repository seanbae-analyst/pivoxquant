/**
 * MirrorHeadline — "오늘의 거울": one upright editorial sentence + the concrete
 * behavioural dimensions where 관찰 diverges from 선언.
 *
 * Legal posture: names no persona at all, never advises, never scores.
 * The gap is stated as neutral facts ("평균 보유기간 ↑"). No italic (CEO 2026-06-15).
 *
 * 2026-09-29 (CEO — "유형 라벨·점수는 만들지 않는다"): the headline used to read
 * "{성장형}으로 선언하셨는데, 최근 30일은 {균형형} 쪽으로…" and a
 * declared-vs-observed alignment percentage sat under it. Both are gone: the sentence
 * now names the one axis where 관찰 and 선언 part most (``gap[0]`` — the
 * backend sorts by |delta| over comparable axes), and nothing is scored.
 */
import * as React from "react";
import type { MirrorHomeResponse, MirrorGapDimension } from "@/lib/types";

/** Axis values are 0–1 normalised, so the sentence gives direction only —
 *  the chip under it carries the %p. Holding period reads as length. */
function directionWord(dim: MirrorGapDimension): string {
  if (dim.key === "holding_period") return dim.direction === "up" ? "길게" : "짧게";
  return dim.direction === "up" ? "높게" : "낮게";
}

/** Axes on which 선언 and 관찰 can be compared: the declared axes (all of them
 *  for a centroid declaration) that also have observed evidence. Mirrors
 *  ``comparable_axes`` in routes/mirror_home.py. */
function hasComparableAxes(d: MirrorHomeResponse): boolean {
  const declared = d.radar.declared_axes?.length ? d.radar.declared_axes : d.radar.keys;
  const observed = d.radar.observed_axes ?? d.radar.keys;
  return declared.some((k) => observed.includes(k));
}

export function leadSentence(d: MirrorHomeResponse): string {
  if (d.stage === "new") {
    return "거래가 쌓이면, 실제 행동이 선언 옆에 비칩니다.";
  }
  const top = d.gap[0];
  if (top) {
    return `선언과 가장 크게 갈라진 곳: ${top.label} — 최근 30일은 선언보다 ${directionWord(top)} 관찰됐어요.`;
  }
  if (!hasComparableAxes(d)) {
    return "선언한 항목을 최근 30일 기록과 견줄 만큼의 관찰이 아직 쌓이지 않았어요.";
  }
  return "선언한 항목에서 최근 30일 행동은 선언과 크게 다르지 않게 관찰됩니다.";
}

function GapChip({ dim }: { dim: MirrorGapDimension }) {
  const arrow = dim.direction === "up" ? "↑" : "↓";
  const mag = Math.round(Math.abs(dim.delta) * 100);
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[13px]"
      style={{
        color: "var(--pq-ivory)",
        border: "1px solid var(--pq-ivory-line)",
      }}
    >
      {dim.label}
      <span style={{ color: "var(--pq-bronze)", fontFamily: "var(--pq-font-mono)" }}>
        {arrow}{mag}%p
      </span>
    </span>
  );
}

export function MirrorHeadline({ data }: { data: MirrorHomeResponse }) {
  const gap = data.gap.slice(0, 3);

  return (
    <section>
      <div
        className="text-[10.5px] uppercase tracking-[0.25em]"
        style={{ color: "var(--pq-bronze)" }}
      >
        오늘의 거울
      </div>

      <h1
        className="mt-3 text-[clamp(1.5rem,3.4vw,2.1rem)] leading-[1.4]"
        /* --pq-font-display, not the raw next/font --font-display: the alias
            is the one that carries the Korean face (globals.css @theme note).
            Playfair has no Hangul, and this headline is Korean. */
        style={{
          fontFamily: "var(--pq-font-display)",
          color: "var(--pq-ivory)",
        }}
      >
        {leadSentence(data)}
      </h1>

      {gap.length > 0 && (
        <div className="mt-5">
          <div
            className="text-[11px] tracking-wide"
            style={{ color: "rgba(var(--pq-ivory-rgb), 0.55)" }}
          >
            선언 대비 최근 30일
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {gap.map((dim) => (
              <GapChip key={dim.key} dim={dim} />
            ))}
          </div>
        </div>
      )}

      {data.drift.available && data.drift.descriptor && (
        <div
          className="mt-4 inline-flex items-center gap-2 rounded-full px-3 py-1 text-[11px]"
          style={{
            color: "rgba(var(--pq-ivory-rgb), 0.78)",
            border: "1px solid rgba(var(--pq-bronze-rgb), 0.4)",
          }}
        >
          <span style={{ color: "var(--pq-bronze)" }}>◇</span>
          {data.drift.descriptor}
        </div>
      )}
    </section>
  );
}
