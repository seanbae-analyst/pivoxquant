"use client";

/** 만져보기 — AI-ready 준비도. 앵커 데이터셋의 네 축을 켜고 끄며 점수가 어떻게 움직이는지 본다. */
import { useState } from "react";
import { TABLES } from "@/lib/concepts/anchor";

const AXES: Array<{ id: string; label: string; weight: number; before: string; after: string }> = [
  { id: "documented", label: "컬럼 설명이 있다", weight: 30, before: "customers_raw.signup_date, orders_raw.status 에 설명이 없다. AI 는 status 의 값이 무슨 뜻인지 추측한다.", after: "모든 컬럼에 뜻·단위·허용값이 적혀 있다." },
  { id: "consistent", label: "값이 일관된다", weight: 25, before: "amount 에 KRW 와 USD 가 섞여 있다. 합계를 내면 틀린다.", after: "amount_krw 로 통일됐고 currency 허용값 검사가 돈다." },
  { id: "pii", label: "개인정보가 처리됐다", weight: 25, before: "customers_raw.email 이 평문이다. 이대로 프롬프트에 넣으면 유출이다.", after: "email 은 해시, name 은 마스킹. PII 태그가 접근제어에 연결됐다." },
  { id: "fresh", label: "최신이고 도착이 보장된다", weight: 20, before: "orders_raw 가 15분마다 온다고 하지만 지키는지 아무도 안 본다.", after: "신선도 SLA 가 계약에 있고 관측이 감시한다." },
];

export function ReadinessMeter() {
  const [on, setOn] = useState<Set<string>>(new Set());
  const score = AXES.reduce((s, a) => s + (on.has(a.id) ? a.weight : 0), 0);
  const cols = TABLES.reduce((n, t) => n + t.columns.length, 0);
  const documented = TABLES.reduce((n, t) => n + t.columns.filter((c) => c.description).length, 0);

  return (
    <div className="grid gap-4 md:grid-cols-[1fr_220px]">
      <ul className="space-y-2 text-sm">
        {AXES.map((a) => {
          const done = on.has(a.id);
          return (
            <li key={a.id} className="rounded border border-line p-3">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={done} onChange={() => setOn((s) => { const n = new Set(s); if (n.has(a.id)) n.delete(a.id); else n.add(a.id); return n; })} />
                <span className={done ? "text-ink" : "text-dim"}>{a.label}</span>
                <span className="ml-auto font-mono text-xs text-faint">+{a.weight}</span>
              </label>
              <p className={`mt-1 text-xs ${done ? "text-ok" : "text-open"}`}>{done ? a.after : a.before}</p>
            </li>
          );
        })}
      </ul>
      <aside className="rounded border border-line p-3 text-sm">
        <p className="text-xs uppercase tracking-widest text-faint">준비도</p>
        <p className="mt-1 font-serif text-4xl text-ink">{score}<span className="text-base text-faint">/100</span></p>
        <div className="mt-2 h-1.5 w-full rounded bg-bg"><div className="h-1.5 rounded bg-accent transition-all" style={{ width: `${score}%` }} /></div>
        <p className="mt-3 text-xs text-dim">지금 앵커 데이터셋의 컬럼 설명은 {documented}/{cols}. 깨끗한 데이터라도 설명이 없으면 AI 가 잘못 해석한다.</p>
        <p className="mt-2 text-xs text-faint">실제 CSV 는 <a href="https://pivoxdata.vercel.app" target="_blank" rel="noreferrer noopener" className="text-accent underline">DataReady</a> 에 올리면 같은 방식으로 점수가 나온다. 브라우저 안에서만 계산한다.</p>
      </aside>
    </div>
  );
}
