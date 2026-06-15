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

function GapChip({ dim }: { dim: MirrorGapDimension }) {
  const arrow = dim.direction === "up" ? "↑" : "↓";
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[13px]"
      style={{
        color: "var(--pq-ivory)",
        border: "1px solid var(--pq-ivory-line)",
      }}
    >
      {dim.label}
      <span style={{ color: "var(--pq-bronze)" }}>{arrow}</span>
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
        style={{ fontFamily: "var(--font-display)", color: "var(--pq-ivory)" }}
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
