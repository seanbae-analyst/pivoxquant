"use client";

/** 만져보기 — 레이크하우스 층 구조. 층을 누르면 앵커 데이터셋에서 그 층이 하는 일이 보인다. */
import { useState } from "react";

const LAYERS = [
  { id: "engines", label: "쿼리 엔진", items: "Spark · Trino · Snowflake · DuckDB", role: "같은 테이블을 여러 엔진이 읽고 쓴다. stg_orders 를 Spark 가 쓰고 Trino 가 대시보드용으로 읽는다." },
  { id: "catalog", label: "카탈로그 (테이블 → 메타데이터 위치)", items: "Unity Catalog · Glue · Nessie · REST catalog", role: "\"orders_raw\" 라는 이름이 어느 metadata.json 을 가리키는지 안다. 접근제어도 여기 붙는다." },
  { id: "format", label: "오픈 테이블 포맷", items: "Iceberg · Delta · Hudi", role: "스냅숏·스키마·파티션 정보. 덮어쓰기 중에도 읽는 쪽은 완성된 스냅숏만 본다. 어제 버전으로 돌아갈 수 있다." },
  { id: "files", label: "파일", items: "Parquet · ORC · Avro", role: "실제 행이 들어 있는 컬럼 지향 파일. orders_raw 의 2026-09-01 파티션은 파일 12개다." },
  { id: "storage", label: "객체 스토리지", items: "S3 · GCS · Azure Blob · MinIO", role: "값싸고 무한한 바이트 창고. 트랜잭션도 스키마도 모른다. 위 층들이 그걸 보탠다." },
];

export function LayersDiagram({ focus = "format" }: { focus?: string }) {
  const [sel, setSel] = useState(focus);
  const cur = LAYERS.find((l) => l.id === sel)!;
  return (
    <div className="grid gap-4 md:grid-cols-[320px_1fr]">
      <ol className="space-y-1">
        {LAYERS.map((l) => (
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
        <p className="mt-4 text-xs text-faint">레이크하우스 = 이 다섯 층 전체. 웨어하우스는 아래 세 층을 벤더가 감춰 놓은 것이고, 데이터 레이크는 아래 두 층만 있는 상태다.</p>
      </div>
    </div>
  );
}
