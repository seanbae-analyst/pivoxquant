"use client";

/** 만져보기 — 미니 데이터 카탈로그. 앵커 데이터셋을 검색하고 컬럼 메타데이터와 빈칸을 본다. */
import { useMemo, useState } from "react";
import { TABLES, type Column, type Table } from "@/lib/concepts/anchor";

const LAYER_KO: Record<Table["layer"], string> = { source: "원본", staging: "정리", mart: "분석", consumer: "소비" };

export function MiniCatalog({ highlight = "search" }: { highlight?: "search" | "owner" | "pii" }) {
  const [q, setQ] = useState(highlight === "pii" ? "email" : highlight === "owner" ? "orders" : "매출");
  const [sel, setSel] = useState<{ table: Table; col: Column } | null>(null);

  const hits = useMemo(() => {
    const t = q.trim().toLowerCase();
    return TABLES.map((table) => ({
      table,
      cols: table.columns.filter((c) => !t || [table.name, table.description ?? "", c.name, c.description ?? ""].some((s) => s.toLowerCase().includes(t))),
    })).filter((x) => x.cols.length > 0);
  }, [q]);

  const total = TABLES.reduce((n, t) => n + t.columns.length, 0);
  const described = TABLES.reduce((n, t) => n + t.columns.filter((c) => c.description).length, 0);
  const ownerless = TABLES.filter((t) => !t.owner).length;

  return (
    <div className="grid gap-4 md:grid-cols-[1fr_260px]">
      <div>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="테이블·컬럼·설명 검색 (예: 매출, 환율, email)"
          className="w-full rounded border border-line bg-bg px-3 py-2 text-sm outline-none placeholder:text-faint focus:border-accent"
          aria-label="카탈로그 검색"
        />
        <div className="mt-3 space-y-3">
          {hits.length === 0 && <p className="text-sm text-faint">검색 결과가 없다.</p>}
          {hits.map(({ table, cols }) => (
            <div key={table.name} className="rounded border border-line">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-line px-3 py-2">
                <span className="font-mono text-sm text-ink">{table.name}</span>
                <span className="text-xs text-faint">{LAYER_KO[table.layer]}</span>
                <span className={`text-xs ${table.owner ? "text-dim" : "text-bad"}`}>오너 {table.owner ?? "없음"}</span>
                <span className="text-xs text-faint">갱신 {table.freshness}</span>
              </div>
              {table.description && <p className="px-3 pt-2 text-xs text-dim">{table.description}</p>}
              <ul className="px-3 py-2">
                {cols.map((c) => (
                  <li key={c.name}>
                    <button
                      type="button"
                      onClick={() => setSel({ table, col: c })}
                      className={`flex w-full items-baseline gap-2 rounded px-1 py-0.5 text-left text-sm hover:bg-raised ${sel?.col === c ? "bg-raised" : ""}`}
                    >
                      <span className="font-mono text-ink">{c.name}</span>
                      <span className="font-mono text-xs text-faint">{c.type}</span>
                      {c.pii && <span className="rounded bg-bad/15 px-1 text-[10px] text-bad">PII</span>}
                      <span className={`ml-auto truncate text-xs ${c.description ? "text-dim" : "text-open"}`}>{c.description ?? "설명 없음"}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
      <aside className="space-y-3 text-sm">
        <div className="rounded border border-line p-3">
          <p className="text-xs uppercase tracking-widest text-faint">채움률</p>
          <p className="mt-1">컬럼 설명 <span className="text-ink">{described}/{total}</span></p>
          <div className="mt-1 h-1.5 w-full rounded bg-bg"><div className="h-1.5 rounded bg-accent" style={{ width: `${(described / total) * 100}%` }} /></div>
          <p className="mt-2">오너 없는 테이블 <span className={ownerless ? "text-bad" : "text-ok"}>{ownerless}</span></p>
          <p className="mt-2 text-xs text-dim">카탈로그의 첫 가치는 검색이 아니라 이 빈칸이 보인다는 것이다.</p>
        </div>
        <div className="rounded border border-line p-3">
          <p className="text-xs uppercase tracking-widest text-faint">선택한 컬럼</p>
          {sel ? (
            <dl className="mt-1 space-y-1 text-xs">
              <div><dt className="inline text-faint">위치 </dt><dd className="inline font-mono">{sel.table.name}.{sel.col.name}</dd></div>
              <div><dt className="inline text-faint">타입 </dt><dd className="inline font-mono">{sel.col.type}</dd></div>
              <div><dt className="inline text-faint">뜻 </dt><dd className="inline">{sel.col.description ?? <span className="text-open">비어 있음 — 사람이 적어야 한다</span>}</dd></div>
              <div><dt className="inline text-faint">개인정보 </dt><dd className="inline">{sel.col.pii ? "예 (마스킹 대상)" : "아니오"}</dd></div>
              <div><dt className="inline text-faint">오너 </dt><dd className="inline">{sel.table.owner ?? <span className="text-bad">없음</span>}</dd></div>
            </dl>
          ) : (
            <p className="mt-1 text-xs text-faint">컬럼을 누르면 메타데이터가 보인다. 타입은 자동으로 채워졌고, 뜻은 사람이 적었다.</p>
          )}
        </div>
      </aside>
    </div>
  );
}
