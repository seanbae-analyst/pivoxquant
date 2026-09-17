"use client";

/** 만져보기 — 스키마 진화. 변경을 골라 포맷별 지원과 파일 재작성 여부를 본다. */
import { useState } from "react";

type Op = "add" | "drop" | "rename" | "widen" | "narrow" | "partition";
const OPS: Array<{ id: Op; label: string; iceberg: string; delta: string; rewrite: boolean; contract: "허용" | "협의" | "차단" }> = [
  { id: "add", label: "coupon_code 컬럼 추가", iceberg: "지원 (ADD COLUMN)", delta: "지원 (mergeSchema / ALTER TABLE)", rewrite: false, contract: "허용" },
  { id: "widen", label: "customer_id int → bigint (타입 승격)", iceberg: "지원 (int→long 승격)", delta: "지원 (byte→short→int 승격 계열)", rewrite: false, contract: "허용" },
  { id: "rename", label: "amount → total 이름 변경", iceberg: "지원 (컬럼 ID 기반, 파일 그대로)", delta: "컬럼 매핑 모드 필요", rewrite: false, contract: "협의" },
  { id: "drop", label: "currency 컬럼 삭제", iceberg: "지원 (DROP COLUMN, 데이터는 남음)", delta: "컬럼 매핑 모드 필요", rewrite: false, contract: "차단" },
  { id: "narrow", label: "amount decimal → string (타입 변경)", iceberg: "미지원 (새 컬럼 + 마이그레이션)", delta: "미지원 (덮어쓰기 필요)", rewrite: true, contract: "차단" },
  { id: "partition", label: "파티션을 day → month 로", iceberg: "지원 (파티션 진화, 옛 데이터 유지)", delta: "재작성 필요", rewrite: false, contract: "허용" },
];

export function SchemaSim() {
  const [sel, setSel] = useState<Op>("add");
  const op = OPS.find((o) => o.id === sel)!;
  return (
    <div className="grid gap-4 md:grid-cols-[300px_1fr]">
      <ul className="space-y-1">
        {OPS.map((o) => (
          <li key={o.id}>
            <button type="button" onClick={() => setSel(o.id)} className={`w-full rounded border px-3 py-2 text-left text-sm ${sel === o.id ? "border-accent bg-accent/10 text-ink" : "border-line text-dim hover:text-ink"}`}>{o.label}</button>
          </li>
        ))}
      </ul>
      <div className="rounded border border-line p-4 text-sm">
        <table className="w-full text-xs">
          <tbody>
            <tr className="border-b border-line"><td className="py-1.5 pr-3 text-faint">Iceberg</td><td className="py-1.5">{op.iceberg}</td></tr>
            <tr className="border-b border-line"><td className="py-1.5 pr-3 text-faint">Delta Lake</td><td className="py-1.5">{op.delta}</td></tr>
            <tr className="border-b border-line"><td className="py-1.5 pr-3 text-faint">옛 파일 재작성</td><td className={`py-1.5 ${op.rewrite ? "text-bad" : "text-ok"}`}>{op.rewrite ? "필요 — 테라바이트면 몇 시간" : "불필요 — 메타데이터만 바뀐다"}</td></tr>
            <tr><td className="py-1.5 pr-3 text-faint">데이터 계약</td><td className={`py-1.5 ${op.contract === "허용" ? "text-ok" : op.contract === "협의" ? "text-open" : "text-bad"}`}>{op.contract}</td></tr>
          </tbody>
        </table>
        <p className="mt-3 text-xs text-dim">포맷이 “할 수 있다”와 계약이 “해도 된다”는 다르다. 삭제는 Iceberg 가 지원하지만 하류가 깨지므로 계약이 막는다. 버전마다 지원 범위가 바뀌니 실제 판단은 아래 근거(공식 문서)로.</p>
      </div>
    </div>
  );
}
