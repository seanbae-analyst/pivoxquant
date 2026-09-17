"use client";

/** 만져보기 — 데이터 계약 시뮬레이션. 생산자가 스키마를 바꾸면 하류 어디가 깨지는지, 계약이 무엇을 막는지. */
import { useState } from "react";
import { downstreamOf } from "@/lib/concepts/anchor";

type Change = "rename_amount" | "amount_to_string" | "drop_currency" | "add_coupon" | "currency_lowercase";

const CHANGES: Array<{ id: Change; label: string; kind: "breaking" | "safe" | "quality"; explain: string; column: string }> = [
  { id: "add_coupon", label: "coupon_code 컬럼 추가 (nullable)", kind: "safe", column: "", explain: "하위 호환 변경. 계약은 허용하고, 스키마 진화가 옛 파일을 다시 쓰지 않고 적용한다." },
  { id: "rename_amount", label: "amount → total 이름 변경", kind: "breaking", column: "orders_raw.amount", explain: "stg_orders 의 SQL 이 amount 를 찾지 못한다. 계약 검사가 배포를 막고, 이름을 유지하거나 새 컬럼을 더한 뒤 마이그레이션하라고 요구한다." },
  { id: "amount_to_string", label: "amount 타입 decimal → string", kind: "breaking", column: "orders_raw.amount", explain: "환율 곱셈이 실패하거나 조용히 NULL 이 된다. 타입 변경은 계약 위반이다." },
  { id: "drop_currency", label: "currency 컬럼 삭제", kind: "breaking", column: "orders_raw.currency", explain: "KRW 환산이 불가능해진다. 삭제는 항상 호환성을 깬다." },
  { id: "currency_lowercase", label: "currency 에 'krw' 소문자 유입", kind: "quality", column: "orders_raw.currency", explain: "스키마는 그대로지만 허용값 규칙(KRW|USD)을 어긴다. 계약의 품질 조항이 잡는다. 스키마만 검사하면 놓친다." },
];

export function ContractSim() {
  const [applied, setApplied] = useState<Set<Change>>(new Set());
  const [enforced, setEnforced] = useState(true);
  const toggle = (id: Change) => setApplied((s) => {
    const n = new Set(s);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });
  const broken = new Set<string>();
  const blocked: string[] = [];
  for (const c of CHANGES) {
    if (!applied.has(c.id) || c.kind === "safe") continue;
    if (enforced) blocked.push(c.label);
    else for (const d of downstreamOf(c.column)) broken.add(d.split(".")[0]);
  }
  const tables = ["orders_raw", "stg_orders", "fct_orders", "daily_revenue", "매출 대시보드"];

  return (
    <div className="grid gap-4 md:grid-cols-[300px_1fr]">
      <div className="space-y-3 text-sm">
        <div className="rounded border border-line p-3">
          <p className="text-xs uppercase tracking-widest text-faint">orders_raw 계약</p>
          <pre className="mt-1 whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-dim">{`schema:
  order_id: string, unique
  customer_id: integer
  amount: decimal > 0
  currency: enum [KRW, USD]
  ordered_at: timestamp
sla: 15분 안에 도착
owner: (미지정)`}</pre>
          <label className="mt-2 flex items-center gap-2 text-xs">
            <input type="checkbox" checked={enforced} onChange={(e) => setEnforced(e.target.checked)} />
            배포 전 계약 검사 (CI) 켜기
          </label>
        </div>
        <div className="rounded border border-line p-3">
          <p className="text-xs uppercase tracking-widest text-faint">주문 팀이 바꾼다</p>
          <ul className="mt-1 space-y-1">
            {CHANGES.map((c) => (
              <li key={c.id}>
                <label className="flex items-start gap-2 text-xs">
                  <input type="checkbox" checked={applied.has(c.id)} onChange={() => toggle(c.id)} className="mt-0.5" />
                  <span>{c.label} <span className={`ml-1 ${c.kind === "safe" ? "text-ok" : c.kind === "quality" ? "text-open" : "text-bad"}`}>{c.kind === "safe" ? "호환" : c.kind === "quality" ? "품질 위반" : "호환 깨짐"}</span></span>
                </label>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="text-sm">
        <div className="flex flex-wrap items-center gap-2">
          {tables.map((t, i) => (
            <div key={t} className="flex items-center gap-2">
              <span className={`rounded border px-2 py-1 font-mono text-xs ${broken.has(t) ? "border-bad bg-bad/15 text-bad" : "border-line text-ink"}`}>{t}</span>
              {i < tables.length - 1 && <span className="text-faint">→</span>}
            </div>
          ))}
        </div>
        <div className="mt-3 space-y-2">
          {applied.size === 0 && <p className="text-xs text-faint">왼쪽에서 변경을 골라 보라.</p>}
          {blocked.length > 0 && (
            <div className="rounded border border-ok/40 bg-ok/10 p-3 text-xs">
              <p className="text-ok">계약 검사가 배포를 막았다.</p>
              <ul className="mt-1 list-disc pl-4 text-dim">{blocked.map((b) => <li key={b}>{b}</li>)}</ul>
              <p className="mt-1 text-dim">하류는 한 줄도 안 깨졌다. 생산자와 소비자가 새 버전을 합의한 뒤에 바꾼다.</p>
            </div>
          )}
          {broken.size > 0 && (
            <div className="rounded border border-bad/40 bg-bad/10 p-3 text-xs">
              <p className="text-bad">검사 없이 배포됐다. 깨진 테이블 {broken.size}개: {[...broken].join(", ")}</p>
              <p className="mt-1 text-dim">월요일 경영회의 대시보드가 비거나 틀린 숫자를 보여준다. 리니지가 없으면 원인을 찾는 데 하루가 간다.</p>
            </div>
          )}
          {[...applied].map((id) => {
            const c = CHANGES.find((x) => x.id === id)!;
            return <p key={id} className="text-xs text-dim"><span className="text-ink">{c.label}</span> — {c.explain}</p>;
          })}
        </div>
      </div>
    </div>
  );
}
