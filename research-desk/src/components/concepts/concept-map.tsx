"use client";

/** 개념 지도 — 여섯 영역에 개념 노드를 놓고 관계선을 잇는다. 노드를 누르면 개념 페이지로. */
import Link from "next/link";
import { useState } from "react";
import { AREAS, CONCEPTS, edges, type AreaId } from "@/lib/concepts/concepts";

const W = 960;
const H = 420;
const COL_W = W / AREAS.length;

export function ConceptMap({ focus }: { focus?: string }) {
  const [hover, setHover] = useState<string | null>(null);
  const pos = new Map<string, { x: number; y: number }>();
  const perArea: Record<AreaId, number> = { storage: 0, metadata: 0, quality: 0, governance: 0, ai: 0, org: 0 };
  for (const c of CONCEPTS) {
    const ai = AREAS.findIndex((a) => a.id === c.area);
    const n = perArea[c.area]++;
    pos.set(c.slug, { x: ai * COL_W + COL_W / 2, y: 90 + n * 90 });
  }
  const active = hover ?? focus ?? null;
  const activeC = active ? CONCEPTS.find((c) => c.slug === active) : null;
  const linked = new Set(activeC ? [activeC.slug, ...activeC.neighbors.map((n) => n.slug)] : []);

  return (
    <div>
      <div className="overflow-x-auto rounded-lg border border-line bg-bg">
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ minWidth: 760 }} role="img" aria-label="데이터 개념 지도">
          {AREAS.map((a, i) => (
            <g key={a.id}>
              <rect x={i * COL_W + 6} y={8} width={COL_W - 12} height={H - 16} rx={10} fill="var(--bg-raised)" stroke="var(--line)" />
              <text x={i * COL_W + COL_W / 2} y={34} textAnchor="middle" style={{ fontSize: 12, fill: "var(--ink-dim)" }}>{a.label}</text>
            </g>
          ))}
          {edges().map(([a, b]) => {
            const pa = pos.get(a)!, pb = pos.get(b)!;
            const on = linked.has(a) && linked.has(b) && (a === active || b === active);
            return <line key={a + b} x1={pa.x} y1={pa.y} x2={pb.x} y2={pb.y} stroke={on ? "var(--accent)" : "var(--line)"} strokeWidth={on ? 2 : 1} />;
          })}
          {CONCEPTS.map((c) => {
            const p = pos.get(c.slug)!;
            const on = linked.has(c.slug);
            const isActive = c.slug === active;
            return (
              <Link key={c.slug} href={`/concepts/${c.slug}`} onMouseEnter={() => setHover(c.slug)} onMouseLeave={() => setHover(null)}>
                <g style={{ cursor: "pointer" }}>
                  <rect x={p.x - 62} y={p.y - 18} width={124} height={36} rx={18}
                    fill={isActive ? "var(--accent)" : on ? "color-mix(in srgb, var(--accent) 18%, var(--bg))" : "var(--bg)"}
                    stroke={isActive || on ? "var(--accent)" : "var(--line)"} />
                  <text x={p.x} y={p.y + 4} textAnchor="middle" style={{ fontSize: 12, fill: isActive ? "var(--bg)" : "var(--ink)" }}>{c.name}</text>
                </g>
              </Link>
            );
          })}
        </svg>
      </div>
      <p className="mt-2 min-h-5 text-xs text-dim">{activeC ? `${activeC.name} — ${activeC.definition}` : "노드에 올리면 정의가, 누르면 개념 페이지가 열린다."}</p>
    </div>
  );
}
