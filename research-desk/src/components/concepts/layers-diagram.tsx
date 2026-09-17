"use client";

/** 만져보기 — 레이크하우스 층 구조. 층을 누르면 앵커 데이터셋에서 그 층이 하는 일이 보인다. */
import { useState } from "react";
import { LAKE_LAYERS, LAKE_NOTE } from "@/lib/concepts/lakehouse";

export function LayersDiagram({ focus = "format" }: { focus?: string }) {
  const [sel, setSel] = useState(focus);
  const cur = LAKE_LAYERS.find((l) => l.id === sel)!;
  return (
    <div className="grid gap-4 md:grid-cols-[320px_1fr]">
      <ol className="space-y-1">
        {LAKE_LAYERS.map((l) => (
          <li key={l.id}>
            <button type="button" onClick={() => setSel(l.id)} className={`w-full rounded border px-3 py-2 text-left text-sm ${sel === l.id ? "border-accent bg-accent/10 text-ink" : "border-line text-dim hover:text-ink"}`}>
              <span className="block">{l.label}</span>
              <span className="block font-mono text-[11px] text-faint">{l.items}</span>
            </button>
          </li>
        ))}
      </ol>
      <div className="rounded border border-line p-4 text-sm">
        <p className="text-xs uppercase tracking-widest text-faint">이 층이 하는 일</p>
        <p className="mt-1 text-ink">{cur.label}</p>
        <p className="mt-2 text-dim">{cur.role}</p>
        <p className="mt-4 text-xs text-faint">{LAKE_NOTE}</p>
      </div>
    </div>
  );
}
