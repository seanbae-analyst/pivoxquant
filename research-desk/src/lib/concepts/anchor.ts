/**
 * 앵커 데이터셋 — 사이트 전체가 같은 데이터를 쓴다. 개념이 바뀌어도 데이터는 안 바뀐다.
 * 온라인 쇼핑몰: customers(고객) → orders(주문) → daily_revenue(일별 매출, 대시보드가 읽는다).
 */

export interface Column {
  name: string;
  type: "string" | "integer" | "decimal" | "date" | "timestamp" | "boolean";
  description: string | null;
  pii?: boolean;
  nullable?: boolean;
}

export interface Table {
  name: string;
  layer: "source" | "staging" | "mart" | "consumer";
  owner: string | null;
  description: string | null;
  freshness: string;
  columns: Column[];
}

export const TABLES: Table[] = [
  {
    name: "customers_raw",
    layer: "source",
    owner: "CRM 팀",
    description: "CRM 에서 매일 새벽 내려받는 고객 원본. 이메일이 평문이다.",
    freshness: "매일 04:00",
    columns: [
      { name: "customer_id", type: "integer", description: "고객 고유 번호" },
      { name: "name", type: "string", description: "고객 이름", pii: true },
      { name: "email", type: "string", description: "이메일 (평문)", pii: true },
      { name: "region", type: "string", description: "거주 지역 코드 (KR-11 등)" },
      { name: "signup_date", type: "date", description: null },
    ],
  },
  {
    name: "orders_raw",
    layer: "source",
    owner: null,
    description: "주문 시스템 이벤트 로그를 그대로 적재. 통화가 섞여 있다.",
    freshness: "15분마다",
    columns: [
      { name: "order_id", type: "string", description: "주문 번호" },
      { name: "customer_id", type: "integer", description: "customers_raw.customer_id 참조" },
      { name: "amount", type: "decimal", description: "결제 금액 (통화는 currency 컬럼)" },
      { name: "currency", type: "string", description: "KRW | USD" },
      { name: "status", type: "string", description: null },
      { name: "ordered_at", type: "timestamp", description: "주문 시각 (UTC)" },
    ],
  },
  {
    name: "stg_orders",
    layer: "staging",
    owner: "데이터 팀",
    description: "orders_raw 를 정리: 통화를 KRW 로 환산하고 취소 주문을 표시.",
    freshness: "시간마다",
    columns: [
      { name: "order_id", type: "string", description: "주문 번호" },
      { name: "customer_id", type: "integer", description: "고객 번호" },
      { name: "amount_krw", type: "decimal", description: "KRW 환산 금액 = amount × 환율(ordered_at 기준)" },
      { name: "is_cancelled", type: "boolean", description: "status = 'cancelled'" },
      { name: "ordered_date", type: "date", description: "ordered_at 을 KST 날짜로" },
    ],
  },
  {
    name: "fct_orders",
    layer: "mart",
    owner: "데이터 팀",
    description: "분석용 주문 사실 테이블. 취소 제외, 고객 지역 조인.",
    freshness: "시간마다",
    columns: [
      { name: "order_id", type: "string", description: "주문 번호" },
      { name: "customer_id", type: "integer", description: "고객 번호" },
      { name: "region", type: "string", description: "고객 지역 (customers_raw.region)" },
      { name: "amount_krw", type: "decimal", description: "KRW 금액" },
      { name: "ordered_date", type: "date", description: "주문 일자 (KST)" },
    ],
  },
  {
    name: "daily_revenue",
    layer: "mart",
    owner: "데이터 팀",
    description: "일별·지역별 매출 합계. 경영 대시보드가 읽는다.",
    freshness: "시간마다",
    columns: [
      { name: "date", type: "date", description: "일자" },
      { name: "region", type: "string", description: "지역" },
      { name: "revenue_krw", type: "decimal", description: "sum(amount_krw)" },
      { name: "order_count", type: "integer", description: "count(order_id)" },
    ],
  },
  {
    name: "매출 대시보드",
    layer: "consumer",
    owner: "경영기획",
    description: "daily_revenue 를 읽는 BI 대시보드. 매주 월요일 경영회의에 올라간다.",
    freshness: "열 때마다",
    columns: [
      { name: "revenue_krw", type: "decimal", description: "일별 매출 차트" },
      { name: "order_count", type: "integer", description: "일별 주문 수" },
    ],
  },
];

export const ORDERS_SAMPLE = [
  { order_id: "O-1001", customer_id: 1, amount: 42000, currency: "KRW", status: "paid", ordered_at: "2026-09-01T02:14:00Z" },
  { order_id: "O-1002", customer_id: 2, amount: 18.5, currency: "USD", status: "paid", ordered_at: "2026-09-01T05:40:00Z" },
  { order_id: "O-1003", customer_id: 1, amount: 9900, currency: "KRW", status: "cancelled", ordered_at: "2026-09-02T11:02:00Z" },
  { order_id: "O-1004", customer_id: 3, amount: 129000, currency: "KRW", status: "paid", ordered_at: "2026-09-02T13:30:00Z" },
  { order_id: "O-1005", customer_id: 4, amount: 7.99, currency: "USD", status: "paid", ordered_at: "2026-09-03T00:05:00Z" },
];

/** 컬럼 수준 리니지 — 어떤 컬럼이 어떤 컬럼에서 왔나. */
export const LINEAGE: Array<{ from: string; to: string; how: string }> = [
  { from: "orders_raw.order_id", to: "stg_orders.order_id", how: "그대로" },
  { from: "orders_raw.customer_id", to: "stg_orders.customer_id", how: "그대로" },
  { from: "orders_raw.amount", to: "stg_orders.amount_krw", how: "× 환율" },
  { from: "orders_raw.currency", to: "stg_orders.amount_krw", how: "환율 선택" },
  { from: "orders_raw.status", to: "stg_orders.is_cancelled", how: "= 'cancelled'" },
  { from: "orders_raw.ordered_at", to: "stg_orders.ordered_date", how: "UTC→KST 날짜" },
  { from: "stg_orders.order_id", to: "fct_orders.order_id", how: "취소 제외" },
  { from: "stg_orders.customer_id", to: "fct_orders.customer_id", how: "취소 제외" },
  { from: "stg_orders.amount_krw", to: "fct_orders.amount_krw", how: "취소 제외" },
  { from: "stg_orders.ordered_date", to: "fct_orders.ordered_date", how: "취소 제외" },
  { from: "customers_raw.region", to: "fct_orders.region", how: "customer_id 조인" },
  { from: "fct_orders.ordered_date", to: "daily_revenue.date", how: "group by" },
  { from: "fct_orders.region", to: "daily_revenue.region", how: "group by" },
  { from: "fct_orders.amount_krw", to: "daily_revenue.revenue_krw", how: "sum" },
  { from: "fct_orders.order_id", to: "daily_revenue.order_count", how: "count" },
  { from: "daily_revenue.revenue_krw", to: "매출 대시보드.revenue_krw", how: "차트" },
  { from: "daily_revenue.order_count", to: "매출 대시보드.order_count", how: "차트" },
];

export function tableByName(name: string): Table | undefined {
  return TABLES.find((t) => t.name === name);
}

/** 컬럼 기준 상류·하류를 재귀로 모은다. */
export function upstreamOf(col: string, acc = new Set<string>()): Set<string> {
  for (const e of LINEAGE) if (e.to === col && !acc.has(e.from)) {
    acc.add(e.from);
    upstreamOf(e.from, acc);
  }
  return acc;
}
export function downstreamOf(col: string, acc = new Set<string>()): Set<string> {
  for (const e of LINEAGE) if (e.from === col && !acc.has(e.to)) {
    acc.add(e.to);
    downstreamOf(e.to, acc);
  }
  return acc;
}
