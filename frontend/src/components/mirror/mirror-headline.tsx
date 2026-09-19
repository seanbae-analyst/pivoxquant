/**
 * MirrorHeadline — "오늘의 거울": one upright editorial sentence + the concrete
 * behavioural dimensions where 관찰 diverges from 선언.
 *
 * Legal posture: never names an 8-code persona (only the 3 disclosed buckets,
 * which arrive pre-collapsed from the backend), never advises, never scores.
 * The gap is stated as neutral facts ("평균 보유기간 ↑"). No italic (CEO 2026-06-15).
 */
import * as React from "react";
import type { MirrorHomeResponse, MirrorGapDimension } from "@/lib/types";

function leadSentence(d: MirrorHomeResponse): string {
  const label = d.declared.label ?? "—";
  if (d.stage === "new") {
    return `${label}으로 시작하셨어요. 거래가 쌓이면, 실제 행동이 여기 비칩니다.`;
  }
  if (d.observed.bucket_changed && d.observed.label) {
    return `${label}으로 선언하셨는데, 최근 30일은 ${d.observed.label} 쪽으로 더 관찰됐어요.`;
  }
  return `${label}으로 선언하셨고, 최근 30일 행동도 같은 결로 관찰됩니다.`;
}

/** 선언 vs 30일 관찰 shape 의 정합도(%) — 측정된 축만의 평균 절대편차 기반.
 *  2026-09-10: 측정되지 않은 축(0.5 기본값)까지 평균에 넣어서, 기록이 거의
 *  없는 사용자에게도 근거 없는 수치가 나왔다. 측정된 축이 없으면 표시하지 않는다. */
function alignmentPct(d: MirrorHomeResponse): number | null {
  const a = d.radar.declared;
  const b = d.radar.observed;
  if (!b || a.length === 0 || a.length !== b.length) return null;
  const measured = d.radar.observed_axes;
  const idx = a
    .map((_, i) => i)
    .filter((i) => !measured || measured.includes(d.radar.keys[i]));
  if (idx.length === 0) return null;
  const mad = idx.reduce((s, i) => s + Math.abs(a[i] - b[i]), 0) / idx.length;
  return Math.round((1 - mad) * 100);
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
  const align = alignmentPct(data);

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

      {align != null && (
        <div className="mt-4 flex items-baseline gap-2.5">
          <span
            className="text-[11px] uppercase tracking-[0.18em]"
            style={{ color: "rgba(var(--pq-ivory-rgb), 0.55)" }}
          >
            선언 ↔ 관찰 정합도
          </span>
          <span
            className="leading-none"
            style={{
              fontFamily: "var(--pq-font-mono)",
              fontSize: "1.9rem",
              color: "var(--pq-ivory)",
            }}
          >
            {align}
            <span className="text-[0.9rem]" style={{ color: "var(--pq-bronze)" }}>
              %
            </span>
          </span>
        </div>
      )}

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
