/**
 * 개념 12개 — 여섯 영역. 모든 개념 페이지는 같은 다섯 블록(정의 → 만져보기 → 어디에 놓이나 → 실무 장면 → 근거와 묻기).
 * 앵커 데이터셋(anchor.ts) 위에서 설명한다.
 */

export type AreaId = "storage" | "metadata" | "quality" | "governance" | "ai" | "org";

export const AREAS: Array<{ id: AreaId; label: string; blurb: string }> = [
  { id: "storage", label: "저장·처리", blurb: "데이터가 어디에 어떤 형태로 놓이는가" },
  { id: "metadata", label: "메타데이터·카탈로그", blurb: "무슨 데이터가 있고 누가 아는가" },
  { id: "quality", label: "품질·관측·리니지", blurb: "데이터가 믿을 만한가, 어디서 왔는가" },
  { id: "governance", label: "거버넌스·규제", blurb: "누가 책임지고 무엇이 허용되는가" },
  { id: "ai", label: "AI-ready·활용", blurb: "AI 가 바로 쓸 수 있는 상태인가" },
  { id: "org", label: "조직·운영", blurb: "사람과 절차" },
];

export type InteractiveId = "catalog" | "lineage" | "contract" | "readiness" | "layers" | "schema";

export interface Concept {
  slug: string;
  name: string;
  en: string;
  area: AreaId;
  /** 두 줄 넘지 않는 정의. */
  definition: string;
  /** 앵커 데이터셋에서 이 개념이 하는 일 — 한두 문장. */
  onAnchor: string;
  interactive: InteractiveId | null;
  neighbors: Array<{ slug: string; relation: string }>;
  confusedWith: Array<{ slug: string; howDiffer: string }>;
  practice: Array<{ tool: string; where: string; note?: string }>;
  /** 근거 블록의 지식 베이스 질문. */
  askQuestion: string;
}

export const CONCEPTS: Concept[] = [
  {
    slug: "data-catalog",
    name: "데이터 카탈로그",
    en: "Data Catalog",
    area: "metadata",
    definition: "조직에 어떤 데이터가 있고, 무슨 뜻이며, 누가 책임지고, 어디서 왔는지를 한곳에서 찾게 하는 메타데이터 시스템.",
    onAnchor: "누군가 \"지역별 매출\"을 검색하면 daily_revenue 가 뜨고, 오너가 데이터 팀이며, region 이 customers_raw 에서 왔다는 것까지 보인다. orders_raw 는 오너가 비어 있어 카탈로그가 그 빈칸을 드러낸다.",
    interactive: "catalog",
    neighbors: [
      { slug: "metadata", relation: "카탈로그가 담는 내용물" },
      { slug: "data-lineage", relation: "카탈로그의 한 탭" },
      { slug: "data-ownership", relation: "카탈로그가 드러내는 빈칸" },
    ],
    confusedWith: [
      { slug: "metadata", howDiffer: "메타데이터는 내용물, 카탈로그는 그것을 모아 검색·탐색하게 하는 도구다." },
    ],
    practice: [
      { tool: "OpenMetadata", where: "Explore → 테이블 → Schema / Lineage / Profiler 탭", note: "커넥터가 스키마·리니지를 자동 수집, 설명·오너는 사람이 채운다" },
      { tool: "DataHub", where: "Dataset 페이지 → Documentation / Lineage / Queries", note: "메타데이터 변경 이벤트를 스트림으로 받는다" },
      { tool: "Unity Catalog", where: "카탈로그 > 스키마 > 테이블 3계층", note: "접근제어와 한 몸" },
    ],
    askQuestion: "데이터 카탈로그가 자동으로 수집하는 메타데이터와 사람이 직접 적어야 하는 메타데이터는 각각 무엇인가?",
  },
  {
    slug: "metadata",
    name: "메타데이터",
    en: "Metadata",
    area: "metadata",
    definition: "데이터에 대한 데이터. 기술 메타데이터(스키마·타입·통계·갱신 시각)와 비즈니스 메타데이터(뜻·오너·용어·분류)로 나뉜다.",
    onAnchor: "orders_raw.amount 의 타입이 decimal 이라는 건 기술 메타데이터, \"통화는 currency 컬럼을 봐야 한다\"는 건 비즈니스 메타데이터다. 후자는 자동으로 안 채워진다.",
    interactive: "catalog",
    neighbors: [
      { slug: "data-catalog", relation: "메타데이터를 담는 그릇" },
      { slug: "data-contract", relation: "메타데이터 중 약속으로 굳힌 부분" },
    ],
    confusedWith: [{ slug: "data-catalog", howDiffer: "카탈로그 없이도 메타데이터는 존재한다 (스키마 파일, 위키). 카탈로그는 그걸 모아 찾게 한다." }],
    practice: [
      { tool: "dbt", where: "schema.yml 의 description · meta · tags", note: "코드 옆에 두면 갱신이 같이 된다" },
      { tool: "OpenMetadata", where: "Description · Owner · Tags · Glossary Term" },
    ],
    askQuestion: "기술 메타데이터와 비즈니스 메타데이터를 한 모델로 묶는 표준(DCAT, OpenMetadata 스키마 등)은 무엇이 있나?",
  },
  {
    slug: "data-lineage",
    name: "데이터 리니지",
    en: "Data Lineage",
    area: "quality",
    definition: "어떤 데이터가 어디서 와서 어떤 변환을 거쳐 어디로 가는지의 흐름. 테이블 수준과 컬럼 수준이 있다.",
    onAnchor: "daily_revenue.revenue_krw 는 fct_orders.amount_krw 의 합이고, 그건 stg_orders 에서 환율을 곱한 값이며, 원본은 orders_raw.amount 와 currency 다. 환율이 틀리면 대시보드 매출이 틀린다.",
    interactive: "lineage",
    neighbors: [
      { slug: "data-catalog", relation: "카탈로그가 보여주는 탭" },
      { slug: "data-observability", relation: "장애 영향 범위를 리니지로 안다" },
      { slug: "data-contract", relation: "계약 위반이 하류 어디까지 번지나" },
    ],
    confusedWith: [{ slug: "data-observability", howDiffer: "리니지는 지도(어디서 어디로), 관측은 계기판(지금 상태가 정상인가)." }],
    practice: [
      { tool: "OpenLineage", where: "Job 실행마다 이벤트(입력·출력·facet)를 표준 형식으로 내보낸다", note: "Airflow·Spark·dbt 연동" },
      { tool: "dbt", where: "ref() 로 테이블 수준 리니지가 자동, 컬럼 수준은 SQL 파싱 필요" },
      { tool: "DataHub / OpenMetadata", where: "Lineage 탭, 컬럼 클릭 시 상·하류 강조" },
    ],
    askQuestion: "컬럼 수준 리니지를 SQL 파싱으로 자동 추출할 때의 한계는 무엇인가?",
  },
  {
    slug: "data-quality",
    name: "데이터 품질",
    en: "Data Quality",
    area: "quality",
    definition: "데이터가 쓰임에 맞는 정도. 정확성·완전성·일관성·적시성·유일성 같은 차원으로 재고, 규칙(테스트)으로 지킨다.",
    onAnchor: "orders_raw.currency 는 KRW 또는 USD 여야 한다(허용값), order_id 는 유일해야 한다, amount 는 0 보다 커야 한다. 이 규칙이 없으면 환산이 조용히 틀린다.",
    interactive: "contract",
    neighbors: [
      { slug: "data-observability", relation: "규칙 밖의 이상을 잡는 쪽" },
      { slug: "data-contract", relation: "규칙을 생산자와의 약속으로 올린 것" },
    ],
    confusedWith: [{ slug: "data-observability", howDiffer: "품질은 내가 정한 규칙을 검사하고, 관측은 정하지 않은 이상(볼륨 급감, 지연)을 감지한다." }],
    practice: [
      { tool: "dbt tests", where: "schema.yml 의 unique · not_null · accepted_values · relationships" },
      { tool: "Great Expectations", where: "Expectation Suite → Checkpoint 로 검사·보고" },
      { tool: "Soda", where: "SodaCL 로 검사 선언, 스캔 결과를 카탈로그로" },
    ],
    askQuestion: "데이터 품질 규칙은 수집 계층·변환 계층·카탈로그 중 어디에 두는 것이 실무에서 권장되나?",
  },
  {
    slug: "data-observability",
    name: "데이터 관측",
    en: "Data Observability",
    area: "quality",
    definition: "데이터 파이프라인의 신선도·볼륨·스키마 변경·분포를 지속 감시해 규칙으로 정하지 않은 이상을 알리는 것.",
    onAnchor: "orders_raw 가 15분마다 와야 하는데 2시간째 안 오면, 규칙은 없어도 관측이 잡는다. 어느 날 USD 주문 비율이 0% 가 되면 분포 이상으로 경보가 뜬다.",
    interactive: "lineage",
    neighbors: [
      { slug: "data-quality", relation: "정한 규칙은 품질, 안 정한 이상은 관측" },
      { slug: "data-lineage", relation: "경보의 영향 범위를 리니지로 본다" },
    ],
    confusedWith: [{ slug: "data-quality", howDiffer: "관측은 기준선(평소 패턴)과 비교하고, 품질은 명시된 규칙과 비교한다." }],
    practice: [
      { tool: "Monte Carlo / Bigeye", where: "테이블별 신선도·볼륨·스키마 모니터 자동 생성", note: "벤더 제품" },
      { tool: "Elementary", where: "dbt 실행 결과 위에 이상 탐지" },
    ],
    askQuestion: "데이터 관측 도구의 자동 이상 탐지가 실제로 잡는 것과 놓치는 것, 오탐률은 어떻게 보고되나?",
  },
  {
    slug: "data-contract",
    name: "데이터 계약",
    en: "Data Contract",
    area: "governance",
    definition: "생산자와 소비자가 스키마·의미·품질·SLA 를 명시적으로 약속한 문서. 위반은 배포 전에 검사로 잡는다.",
    onAnchor: "orders_raw 계약: amount 는 decimal, currency 는 KRW|USD, order_id 는 유일, 15분 안에 도착. 주문 팀이 amount 를 문자열로 바꾸면 stg_orders 부터 대시보드까지 깨진다. 계약 검사가 그 배포를 막는다.",
    interactive: "contract",
    neighbors: [
      { slug: "schema-evolution", relation: "계약이 허용하는 변경과 막는 변경" },
      { slug: "data-quality", relation: "계약 안의 품질 조항" },
      { slug: "data-ownership", relation: "계약의 당사자" },
    ],
    confusedWith: [{ slug: "schema-evolution", howDiffer: "스키마 진화는 변경을 안전하게 적용하는 기술, 계약은 어떤 변경을 허용할지의 약속이다." }],
    practice: [
      { tool: "Open Data Contract Standard (ODCS)", where: "YAML 로 스키마·품질·SLA 를 기술" },
      { tool: "dbt model contracts", where: "contract: enforced: true 로 컬럼·타입 강제" },
      { tool: "Schema Registry", where: "이벤트 스키마 호환성 검사 (BACKWARD/FORWARD)" },
    ],
    askQuestion: "데이터 계약을 CI 에서 강제하는 구체적인 방법과 도구는 무엇인가?",
  },
  {
    slug: "schema-evolution",
    name: "스키마 진화",
    en: "Schema Evolution",
    area: "storage",
    definition: "이미 쌓인 데이터를 다시 쓰지 않고 컬럼 추가·삭제·이름 변경·타입 변경을 적용하는 능력. 테이블 포맷마다 지원 범위가 다르다.",
    onAnchor: "orders_raw 에 coupon_code 컬럼을 더해도 옛 파일을 다시 쓰지 않는다. 하지만 amount 를 decimal→string 으로 바꾸는 건 포맷이 허용해도 계약이 막아야 한다.",
    interactive: "schema",
    neighbors: [
      { slug: "open-table-format", relation: "진화를 지원하는 포맷" },
      { slug: "data-contract", relation: "허용 범위를 정하는 약속" },
    ],
    confusedWith: [{ slug: "data-contract", howDiffer: "진화는 '할 수 있다', 계약은 '해도 된다'." }],
    practice: [
      { tool: "Apache Iceberg", where: "ALTER TABLE ... ADD/DROP/RENAME COLUMN, 컬럼 ID 기반이라 이름 변경에 안전" },
      { tool: "Delta Lake", where: "mergeSchema 옵션 · ALTER TABLE, 컬럼 매핑 모드" },
    ],
    askQuestion: "Iceberg 와 Delta Lake 의 스키마 진화 지원 범위(추가·삭제·이름 변경·타입 승격·파티션 진화)는 각각 어디까지인가?",
  },
  {
    slug: "lakehouse",
    name: "레이크하우스",
    en: "Lakehouse",
    area: "storage",
    definition: "객체 스토리지의 파일 위에 트랜잭션·스키마·인덱스를 얹어 웨어하우스처럼 쓰는 아키텍처. 오픈 테이블 포맷이 그 핵심 부품.",
    onAnchor: "orders_raw 파일이 S3 에 쌓이고, Iceberg 테이블로 선언되면 SQL 로 조회하고 갱신할 수 있다. 같은 파일을 Spark 와 Trino 가 함께 읽는다.",
    interactive: "layers",
    neighbors: [
      { slug: "open-table-format", relation: "레이크하우스의 부품" },
      { slug: "schema-evolution", relation: "포맷이 주는 능력" },
    ],
    confusedWith: [{ slug: "open-table-format", howDiffer: "레이크하우스는 아키텍처(그림 전체), 테이블 포맷은 그 안의 한 층이다." }],
    practice: [
      { tool: "Databricks (Delta)", where: "Unity Catalog + Delta 테이블" },
      { tool: "Snowflake / Trino + Iceberg", where: "외부 Iceberg 테이블을 카탈로그에 등록" },
    ],
    askQuestion: "레이크하우스와 클라우드 웨어하우스의 선택 기준과 실제 비용 사례는 무엇인가?",
  },
  {
    slug: "open-table-format",
    name: "오픈 테이블 포맷",
    en: "Open Table Format",
    area: "storage",
    definition: "Parquet 같은 파일 위에 스냅숏·스키마·파티션 정보를 두어 ACID 트랜잭션과 시간 여행을 가능하게 하는 메타데이터 규격. Iceberg, Delta, Hudi.",
    onAnchor: "stg_orders 를 매시간 덮어써도 스냅숏이 남아 어제 버전으로 돌아갈 수 있다. 여러 엔진이 같은 테이블을 읽어도 반쯤 쓰인 파일을 보지 않는다.",
    interactive: "layers",
    neighbors: [
      { slug: "lakehouse", relation: "이 포맷이 만드는 아키텍처" },
      { slug: "schema-evolution", relation: "포맷이 지원하는 변경" },
    ],
    confusedWith: [{ slug: "lakehouse", howDiffer: "포맷은 파일 옆의 메타데이터 규격, 레이크하우스는 그것으로 만든 시스템." }],
    practice: [
      { tool: "Apache Iceberg", where: "metadata.json → manifest list → manifest → data files" },
      { tool: "Delta Lake", where: "_delta_log 의 JSON 커밋 + 체크포인트" },
    ],
    askQuestion: "Iceberg, Delta, Hudi 의 현재 지배 구조(재단·벤더)와 엔진 지원 범위는 어떻게 다른가?",
  },
  {
    slug: "data-ownership",
    name: "데이터 오너십",
    en: "Data Ownership",
    area: "org",
    definition: "데이터 자산마다 뜻·품질·접근을 책임지는 사람(팀)을 지정하는 것. 오너 없는 데이터는 아무도 고치지 않는다.",
    onAnchor: "orders_raw 는 오너가 비어 있다. currency 에 'krw' 소문자가 섞여 들어와도 물어볼 사람이 없다. 카탈로그가 이 빈칸을 보여주고, 거버넌스가 채우게 한다.",
    interactive: "catalog",
    neighbors: [
      { slug: "data-governance", relation: "오너십을 정하는 체계" },
      { slug: "data-contract", relation: "오너가 서명하는 약속" },
    ],
    confusedWith: [{ slug: "data-governance", howDiffer: "오너십은 '누가', 거버넌스는 '어떤 규칙으로'." }],
    practice: [
      { tool: "OpenMetadata / DataHub", where: "Owner 필드 (사용자·팀), 미지정 자산 리포트" },
      { tool: "dbt", where: "meta: owner 또는 groups" },
    ],
    askQuestion: "데이터 오너와 데이터 스튜어드의 역할 차이와, 규모별로 실제로 작동한 배치는?",
  },
  {
    slug: "data-governance",
    name: "데이터 거버넌스",
    en: "Data Governance",
    area: "governance",
    definition: "데이터의 분류·접근·품질·보존을 정하는 규칙과, 그것을 실제로 강제하는 체계. 문서만 있으면 거버넌스가 아니다.",
    onAnchor: "customers_raw.email 은 개인정보다. 거버넌스는 이 컬럼을 PII 로 분류하고, 마케팅 팀은 마스킹된 값만 보게 하며, 90일 뒤 삭제하게 한다. 카탈로그의 태그가 접근제어에 연결되면 '강제'가 된다.",
    interactive: "catalog",
    neighbors: [
      { slug: "data-ownership", relation: "거버넌스의 사람 축" },
      { slug: "data-contract", relation: "거버넌스를 자산 단위로 내린 것" },
      { slug: "ai-ready-data", relation: "AI 사용 전 거버넌스 점검" },
    ],
    confusedWith: [{ slug: "data-ownership", howDiffer: "거버넌스는 규칙과 강제 수단, 오너십은 그 규칙을 지킬 사람." }],
    practice: [
      { tool: "Unity Catalog / Purview", where: "태그 기반 접근제어, 컬럼 마스킹" },
      { tool: "DAMA DMBOK", where: "거버넌스 지식 영역의 참조 프레임워크" },
    ],
    askQuestion: "데이터 거버넌스 정책 중 코드로 강제되는 것(policy as code)과 문서로만 남는 것은 실무에서 어떻게 갈리나?",
  },
  {
    slug: "ai-ready-data",
    name: "AI-ready 데이터",
    en: "AI-ready Data",
    area: "ai",
    definition: "AI(학습·RAG·에이전트)가 추가 정리 없이 바로 쓸 수 있는 상태. 문서화·품질·접근성·개인정보 처리·최신성이 갖춰진 데이터.",
    onAnchor: "orders 를 AI 에 넣으려면: 컬럼 뜻이 적혀 있고(메타데이터), 통화가 통일돼 있고(품질), email 이 가려져 있고(거버넌스), 15분 안에 도착한다(신선도). 이 넷을 재면 준비도가 나온다.",
    interactive: "readiness",
    neighbors: [
      { slug: "metadata", relation: "AI 가 읽을 컬럼 설명" },
      { slug: "data-quality", relation: "준비도의 한 축" },
      { slug: "data-governance", relation: "개인정보 처리" },
    ],
    confusedWith: [{ slug: "data-quality", howDiffer: "품질은 준비도의 한 축일 뿐이다. 설명 없는 깨끗한 데이터는 AI 가 잘못 해석한다." }],
    practice: [
      { tool: "DataReady (pivoxdata)", where: "CSV 를 올리면 0~100 준비도 점수와 우선순위 처방", note: "브라우저 안에서만 계산" },
      { tool: "데이터 계약 + 의미 계층", where: "컬럼 뜻·단위·허용값을 기계가 읽게" },
    ],
    askQuestion: "AI-ready 데이터의 정의는 출처마다 어떻게 다르고, 공통으로 들어가는 요소는 무엇인가?",
  },
];

export function conceptBySlug(slug: string): Concept | undefined {
  return CONCEPTS.find((c) => c.slug === slug);
}

export function conceptsInArea(area: AreaId): Concept[] {
  return CONCEPTS.filter((c) => c.area === area);
}

/** 지도에 그릴 간선 — neighbors 를 양방향 중복 없이. */
export function edges(): Array<[string, string]> {
  const seen = new Set<string>();
  const out: Array<[string, string]> = [];
  for (const c of CONCEPTS) for (const n of c.neighbors) {
    const key = [c.slug, n.slug].sort().join("|");
    if (seen.has(key) || !conceptBySlug(n.slug)) continue;
    seen.add(key);
    out.push([c.slug, n.slug]);
  }
  return out;
}
