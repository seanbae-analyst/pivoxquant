/**
 * 레이크하우스 층 — 2D 다이어그램과 3D 스택이 같은 데이터를 쓴다 (두 벌 금지).
 * 아래가 바닥(객체 스토리지), 위가 사용자에 가까운 층.
 */
export interface LakeLayer {
  id: string;
  label: string;
  items: string;
  role: string;
}

/** 위 → 아래 순서. 3D 스택은 역순으로 쌓는다. */
export const LAKE_LAYERS: LakeLayer[] = [
  { id: "engines", label: "쿼리 엔진", items: "Spark · Trino · Snowflake · DuckDB", role: "같은 테이블을 여러 엔진이 읽고 쓴다. stg_orders 를 Spark 가 쓰고 Trino 가 대시보드용으로 읽는다." },
  { id: "catalog", label: "카탈로그", items: "Unity Catalog · Glue · Nessie · REST catalog", role: "“orders_raw” 라는 이름이 어느 metadata.json 을 가리키는지 안다. 접근제어도 여기 붙는다." },
  { id: "format", label: "오픈 테이블 포맷", items: "Iceberg · Delta · Hudi", role: "스냅숏·스키마·파티션 정보. 덮어쓰기 중에도 읽는 쪽은 완성된 스냅숏만 본다. 어제 버전으로 돌아갈 수 있다." },
  { id: "files", label: "파일", items: "Parquet · ORC · Avro", role: "실제 행이 들어 있는 컬럼 지향 파일. orders_raw 의 2026-09-01 파티션은 파일 12개다." },
  { id: "storage", label: "객체 스토리지", items: "S3 · GCS · Azure Blob · MinIO", role: "값싸고 무한한 바이트 창고. 트랜잭션도 스키마도 모른다. 위 층들이 그걸 보탠다." },
];

export const LAKE_NOTE =
  "레이크하우스 = 이 다섯 층 전체. 웨어하우스는 아래 세 층을 벤더가 감춰 놓은 것이고, 데이터 레이크는 아래 두 층만 있는 상태다.";
