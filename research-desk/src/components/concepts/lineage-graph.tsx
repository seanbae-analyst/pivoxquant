"use client";

/** 만져보기 — 컬럼 수준 리니지. 컬럼을 고르면 상류·하류가 켜진다. */
import { useMemo, useState } from "react";
import { LINEAGE, TABLES, downstreamOf, upstreamOf } from "@/lib/concepts/anchor";

const LAYERS: Array<{ id: string; label: string; x: number }> = [
  { id: "source", label: "원본", x: 40 },
  { id: "staging", label: "정리", x: 260 },
  { id: "mart", label: "분석", x: 480 },
  { id: "consumer", label: "소비", x: 700 },
];
const W = 900;
const ROW = 22;
const HEAD = 26;
const BOX_W = 180;

export function LineageGraph({ initial = "daily_revenue.revenue_krw", mode = "lineage" }: { initial?: string; mode?: "lineage" | "incident" }) {
  const [sel, setSel] = useState(initial);
  const up = useMemo(() => upstreamOf(sel), [sel]);
  const down = useMemo(() => downstreamOf(sel), [sel]);
  const lit = new Set([sel, ...up, ...down]);

  // 테이블 배치: 레이어별 세로 스택
  const pos = new Map<string, { x: number; y: number; h: number }>();
  const layerY: Record<string, number> = {};
  let maxH = 0;
  for (const t of TABLES) {
    const lx = LAYERS.find((l) => l.id === t.layer)!.x;
    const y = (layerY[t.layer] ?? 30);
    const h = HEAD + t.columns.length * ROW + 8;
    pos.set(t.name, { x: lx, y, h });
    layerY[t.layer] = y + h + 24;
    maxH = Math.max(maxH, layerY[t.layer]);
  }
  const colPos = (ref: string) => {
    const [table, col] = ref.split(".");
    const t = TABLES.find((x) => x.name === table)!;
    const i = t.columns.findIndex((c) => c.name === col);
    const p = pos.get(table)!;
    return { x: p.x, y: p.y + HEAD + i * ROW + ROW / 2 };
  };

  const edgeOf = (e: (typeof LINEAGE)[number]) => lit.has(e.from) && lit.has(e.to) && (up.has(e.from) || e.from === sel || (down.has(e.to) && (down.has(e.from) || e.from === sel)));
  const options = TABLES.flatMap((t) => t.columns.map((c) => `${t.name}.${c.name}`));

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
        <label htmlFor="lin-col" className="text-dim">{mode === "incident" ? "이상이 난 컬럼" : "기준 컬럼"}</label>
        <select id="lin-col" value={sel} onChange={(e) => setSel(e.target.value)} className="rounded border border-line bg-bg px-2 py-1 font-mono text-xs">
          {options.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
        <span className="text-xs text-faint">상류 {up.size} · 하류 {down.size}</span>
      </div>
      <div className="overflow-x-auto rounded border border-line bg-bg">
        <svg viewBox={`0 0 ${W} ${maxH}`} width="100%" style={{ minWidth: 720 }} role="img" aria-label="컬럼 수준 리니지 그래프">
          {LAYERS.map((l) => <text key={l.id} x={l.x} y={18} className="fill-current text-faint" style={{ fontSize: 11, fill: "var(--ink-faint)" }}>{l.label}</text>)}
          {LINEAGE.map((e) => {
            const a = colPos(e.from), b = colPos(e.to);
            const on = edgeOf(e);
            const mx = (a.x + BOX_W + b.x) / 2;
            return (
              <path key={e.from + e.to} d={`M ${a.x + BOX_W} ${a.y} C ${mx} ${a.y}, ${mx} ${b.y}, ${b.x} ${b.y}`} fill="none"
                stroke={on ? (mode === "incident" ? "var(--bad)" : "var(--accent)") : "var(--line)"} strokeWidth={on ? 2 : 1} opacity={on ? 1 : 0.7} />
            );
          })}
          {TABLES.map((t) => {
            const p = pos.get(t.name)!;
            return (
              <g key={t.name}>
                <rect x={p.x} y={p.y} width={BOX_W} height={p.h} rx={6} fill="var(--bg-raised)" stroke="var(--line)" />
                <text x={p.x + 8} y={p.y + 17} style={{ fontSize: 12, fill: "var(--ink)", fontFamily: "var(--font-mono)" }}>{t.name}</text>
                {t.columns.map((c, i) => {
                  const ref = `${t.name}.${c.name}`;
                  const on = lit.has(ref);
                  const isSel = ref === sel;
                  return (
                    <g key={c.name} onClick={() => setSel(ref)} style={{ cursor: "pointer" }}>
                      <rect x={p.x + 4} y={p.y + HEAD + i * ROW} width={BOX_W - 8} height={ROW - 2} rx={3}
                        fill={isSel ? (mode === "incident" ? "var(--bad)" : "var(--accent)") : on ? "color-mix(in srgb, var(--accent) 18%, transparent)" : "transparent"} />
                      <text x={p.x + 10} y={p.y + HEAD + i * ROW + 14} style={{ fontSize: 11, fontFamily: "var(--font-mono)", fill: isSel ? "var(--bg)" : on ? "var(--ink)" : "var(--ink-dim)" }}>{c.name}</text>
                    </g>
                  );
                })}
              </g>
            );
          })}
        </svg>
      </div>
      <p className="mt-2 text-xs text-dim">
        {mode === "incident"
          ? `${sel} 에 이상이 나면 붉은 선을 따라 하류 ${down.size}개 컬럼이 영향을 받는다. 관측이 경보를 내고, 리니지가 누구에게 알릴지 정한다.`
          : `${sel} 는 상류 ${up.size}개 컬럼에서 온다. 그중 하나(예: orders_raw.currency)가 틀리면 이 값도 틀린다. 선 위의 변환은 리니지 도구가 SQL 을 파싱해 얻는다.`}
      </p>
    </div>
  );
}
