// =============================================================================
// StockPilot AI Agent Organization Registry
// Generated from: .claude/agents/*.md
// Last updated: 2026-04-09
// =============================================================================

export type AgentTier = "ceo" | "c-suite" | "department" | "unit";
export type AgentGroup =
  | "executive"
  | "strategy"
  | "product"
  | "engineering"
  | "support"
  | "audit"
  | "specialist";

export interface Agent {
  id: string;
  name: string;
  nameEn: string;
  description: string;
  tier: AgentTier;
  group: AgentGroup;
  benchmark: string;
  parentId: string | null;
  pdcaPhases: string[];
}

export interface AgentRelation {
  from: string;
  to: string;
  type: "reports_to" | "collaborates" | "audits";
}

// =============================================================================
// Agent Registry
// =============================================================================

export const AGENTS: readonly Agent[] = [
  // ---------------------------------------------------------------------------
  // CEO (Tier 0)
  // ---------------------------------------------------------------------------
  {
    id: "ceo",
    name: "CEO",
    nameEn: "CEO",
    description: "1인 창업자, 전체 AI 조직 총괄 지휘",
    tier: "ceo",
    group: "executive",
    benchmark: "Solo Founder",
    parentId: null,
    pdcaPhases: ["plan", "do", "check", "act"],
  },

  // ---------------------------------------------------------------------------
  // CEO Staff (CEO 직속)
  // ---------------------------------------------------------------------------
  {
    id: "secretary",
    name: "비서",
    nameEn: "Secretary",
    description:
      "CEO 전담 비서, 부서 지휘, 인수인계, 브리핑, 품질 관리 총괄",
    tier: "department",
    group: "executive",
    benchmark: "CEO Chief of Staff",
    parentId: "ceo",
    pdcaPhases: ["plan", "do", "check", "act"],
  },
  {
    id: "investigator",
    name: "조사부",
    nameEn: "Investigator",
    description:
      "코드베이스 정밀 조사, 의존성 분석, API 매핑, 함수 추적, 아키텍처 파악 전담",
    tier: "department",
    group: "specialist",
    benchmark: "Codebase Intelligence Specialist",
    parentId: "ceo",
    pdcaPhases: ["check"],
  },

  // ---------------------------------------------------------------------------
  // C-Suite (Tier 1)
  // ---------------------------------------------------------------------------
  {
    id: "cto",
    name: "CTO",
    nameEn: "CTO",
    description:
      "Google VP Engineering 수준의 기술 총괄, 아키텍처 결정, 기술 부서 지휘",
    tier: "c-suite",
    group: "engineering",
    benchmark: "Google VP Engineering",
    parentId: "ceo",
    pdcaPhases: ["plan", "do", "check"],
  },
  {
    id: "cpo",
    name: "CPO",
    nameEn: "CPO",
    description:
      "Stripe Head of Product 수준의 제품 총괄, 기능 기획, UX 지휘",
    tier: "c-suite",
    group: "product",
    benchmark: "Stripe Head of Product",
    parentId: "ceo",
    pdcaPhases: ["plan", "do", "check"],
  },
  {
    id: "coo",
    name: "COO",
    nameEn: "COO",
    description:
      "Amazon VP Operations 수준의 운영 총괄, 프로세스, 인사 지휘",
    tier: "c-suite",
    group: "support",
    benchmark: "Amazon VP Operations",
    parentId: "ceo",
    pdcaPhases: ["plan", "do", "check"],
  },
  {
    id: "cfo",
    name: "CFO",
    nameEn: "CFO",
    description:
      "Sequoia 포트폴리오 CFO 수준의 재무 총괄, 예산, 투자, 수익화 지휘",
    tier: "c-suite",
    group: "strategy",
    benchmark: "Sequoia Portfolio CFO",
    parentId: "ceo",
    pdcaPhases: ["plan", "check", "act"],
  },
  {
    id: "cmo",
    name: "CMO",
    nameEn: "CMO",
    description:
      "Airbnb VP Marketing 수준의 마케팅 총괄, 그로스, 브랜드 지휘",
    tier: "c-suite",
    group: "strategy",
    benchmark: "Airbnb VP Marketing",
    parentId: "ceo",
    pdcaPhases: ["plan", "do", "check"],
  },
  {
    id: "cdo",
    name: "CDO",
    nameEn: "CDO",
    description:
      "Google Head of Data 수준의 데이터 총괄, 분석, 퀀트 모델 지휘",
    tier: "c-suite",
    group: "strategy",
    benchmark: "Google Head of Data",
    parentId: "ceo",
    pdcaPhases: ["plan", "check", "act"],
  },
  {
    id: "clo",
    name: "CLO",
    nameEn: "CLO",
    description:
      "Kim & Chang 대표변호사 수준의 법무 총괄, 규제, 컴플라이언스 지휘",
    tier: "c-suite",
    group: "support",
    benchmark: "Kim & Chang Senior Partner",
    parentId: "ceo",
    pdcaPhases: ["check", "act"],
  },

  // ---------------------------------------------------------------------------
  // CEO 직속 부서 (Tier 2)
  // ---------------------------------------------------------------------------
  {
    id: "strategy",
    name: "기획부",
    nameEn: "Strategy",
    description:
      "McKinsey 파트너 수준의 전략 분석, 로드맵, 의사결정 전담",
    tier: "department",
    group: "strategy",
    benchmark: "McKinsey Partner",
    parentId: "ceo",
    pdcaPhases: ["plan", "act"],
  },
  {
    id: "pitch",
    name: "피칭부",
    nameEn: "Pitch",
    description:
      "Y Combinator Demo Day 수준의 피치, 면접 준비, 스토리텔링 전담",
    tier: "department",
    group: "strategy",
    benchmark: "YC Demo Day",
    parentId: "ceo",
    pdcaPhases: ["plan", "act"],
  },
  {
    id: "audit",
    name: "검수부",
    nameEn: "Audit",
    description:
      "Goldman Sachs 수준의 리스크 관리, 최종 검수, 의사결정 검증 전담",
    tier: "department",
    group: "audit",
    benchmark: "Goldman Sachs Executive Review",
    parentId: "ceo",
    pdcaPhases: ["check", "act"],
  },
  {
    id: "user-tester",
    name: "유저테스트부",
    nameEn: "User Tester",
    description:
      "Goldman Sachs 회장이 직접 앱을 써보는 것처럼 모든 기능을 클릭하고 검증하는 E2E 테스트 에이전트",
    tier: "department",
    group: "audit",
    benchmark: "Goldman Sachs Chairman Hands-On",
    parentId: "ceo",
    pdcaPhases: ["check"],
  },
  {
    id: "stockpilot-improver",
    name: "개선분석부",
    nameEn: "StockPilot Improver",
    description:
      "레거시 vs React 갭 분석, 기능 완성도 추적, 개선 우선순위 제안 전담",
    tier: "department",
    group: "specialist",
    benchmark: "Gap Closer & Feature Completer",
    parentId: "ceo",
    pdcaPhases: ["check", "act"],
  },

  // ---------------------------------------------------------------------------
  // CTO 산하 (Tier 2)
  // ---------------------------------------------------------------------------
  {
    id: "engineering",
    name: "개발부",
    nameEn: "Engineering",
    description:
      "Google Staff Engineer 수준의 코드 품질, 시스템 설계, 기술 구현 전담",
    tier: "department",
    group: "engineering",
    benchmark: "Google Staff Engineer",
    parentId: "cto",
    pdcaPhases: ["plan", "do", "check"],
  },
  {
    id: "frontend-dev",
    name: "프론트개발부",
    nameEn: "Frontend Dev",
    description:
      "Vercel Core Team 수준의 Next.js, React, UI 구현 전담",
    tier: "department",
    group: "engineering",
    benchmark: "Vercel Core Team",
    parentId: "cto",
    pdcaPhases: ["do"],
  },
  {
    id: "backend-dev",
    name: "백엔드개발부",
    nameEn: "Backend Dev",
    description: "Stripe Backend Team 수준의 Flask API, DB, 인증 전담",
    tier: "department",
    group: "engineering",
    benchmark: "Stripe Backend Team",
    parentId: "cto",
    pdcaPhases: ["do"],
  },
  {
    id: "realtime-dev",
    name: "실시간개발부",
    nameEn: "Realtime Dev",
    description:
      "Discord Engineering 수준의 WebSocket, SSE, 실시간 데이터 전담",
    tier: "department",
    group: "engineering",
    benchmark: "Discord Engineering",
    parentId: "cto",
    pdcaPhases: ["do"],
  },
  {
    id: "infra-dev",
    name: "인프라개발부",
    nameEn: "Infra Dev",
    description:
      "Netflix Platform Team 수준의 CI/CD, 자동화, 스크립트 전담",
    tier: "department",
    group: "engineering",
    benchmark: "Netflix Platform Team",
    parentId: "cto",
    pdcaPhases: ["do"],
  },
  {
    id: "performance",
    name: "성능부",
    nameEn: "Performance",
    description:
      "Google Core Web Vitals 수준의 프론트엔드/백엔드 성능 최적화 전담",
    tier: "department",
    group: "engineering",
    benchmark: "Google PageSpeed",
    parentId: "cto",
    pdcaPhases: ["check", "act"],
  },
  {
    id: "security",
    name: "보안부",
    nameEn: "Security",
    description:
      "NSA Red Team 수준의 보안 감사, 금융 데이터 보호, 취약점 제로 전담",
    tier: "department",
    group: "engineering",
    benchmark: "NSA Red Team",
    parentId: "cto",
    pdcaPhases: ["check", "act"],
  },
  {
    id: "qa",
    name: "QA부",
    nameEn: "QA",
    description:
      "NASA JPL 수준의 테스팅, 금융 시스템급 결함 제로 목표 전담",
    tier: "department",
    group: "engineering",
    benchmark: "NASA JPL",
    parentId: "cto",
    pdcaPhases: ["check"],
  },
  {
    id: "code-janitor",
    name: "코드정리부",
    nameEn: "Code Janitor",
    description:
      "코드 품질 자동 관리 시스템, 4개 전문 유닛 조율",
    tier: "department",
    group: "engineering",
    benchmark: "Code Quality Automation",
    parentId: "cto",
    pdcaPhases: ["check", "act"],
  },

  // ---------------------------------------------------------------------------
  // Code Janitor 산하 유닛 (Tier 3)
  // ---------------------------------------------------------------------------
  {
    id: "import-police",
    name: "Import 경찰",
    nameEn: "Import Police",
    description:
      "미사용 import 탐지, import 순서 강제, 중복 제거 전담",
    tier: "unit",
    group: "engineering",
    benchmark: "Import Linter",
    parentId: "code-janitor",
    pdcaPhases: ["check"],
  },
  {
    id: "dead-code-hunter",
    name: "Dead Code 사냥꾼",
    nameEn: "Dead Code Hunter",
    description:
      "안 쓰는 코드, 주석 블록, 도달 불가 코드 탐지 및 제거",
    tier: "unit",
    group: "engineering",
    benchmark: "Dead Code Eliminator",
    parentId: "code-janitor",
    pdcaPhases: ["check"],
  },
  {
    id: "style-enforcer",
    name: "스타일 집행관",
    nameEn: "Style Enforcer",
    description:
      "네이밍, 포맷팅, 코딩 컨벤션 일관성 강제 전담",
    tier: "unit",
    group: "engineering",
    benchmark: "Style Linter",
    parentId: "code-janitor",
    pdcaPhases: ["check"],
  },
  {
    id: "architecture-guard",
    name: "아키텍처 수호자",
    nameEn: "Architecture Guard",
    description:
      "파일 위치, 레이어 분리, 프로젝트 구조 규칙 감시 전담",
    tier: "unit",
    group: "engineering",
    benchmark: "Architecture Enforcer",
    parentId: "code-janitor",
    pdcaPhases: ["check"],
  },
  {
    id: "file-organizer",
    name: "파일정리부",
    nameEn: "File Organizer",
    description:
      "프로젝트 폴더 구조, 파일 위치, 네이밍, 중복 파일 관리 전담",
    tier: "unit",
    group: "engineering",
    benchmark: "Project Organizer",
    parentId: "code-janitor",
    pdcaPhases: ["check"],
  },

  // ---------------------------------------------------------------------------
  // CPO 산하 (Tier 2)
  // ---------------------------------------------------------------------------
  {
    id: "product",
    name: "프로덕트부",
    nameEn: "Product",
    description:
      "Stripe PM 수준의 제품 사고, 기능 기획, 사용자 중심 설계 전담",
    tier: "department",
    group: "product",
    benchmark: "Stripe PM",
    parentId: "cpo",
    pdcaPhases: ["plan", "check"],
  },
  {
    id: "design",
    name: "디자인부",
    nameEn: "Design",
    description:
      "Apple HIG + Bloomberg Terminal 수준의 UI/UX, 디자인 시스템 전담",
    tier: "department",
    group: "product",
    benchmark: "Apple x Bloomberg",
    parentId: "cpo",
    pdcaPhases: ["plan", "do", "check"],
  },
  {
    id: "onboarding",
    name: "온보딩부",
    nameEn: "Onboarding",
    description:
      "Duolingo 수준의 신규 유저 첫 경험 설계, 활성화율 극대화 전담",
    tier: "department",
    group: "product",
    benchmark: "Duolingo Activation",
    parentId: "cpo",
    pdcaPhases: ["plan", "do"],
  },
  {
    id: "i18n",
    name: "국제화부",
    nameEn: "i18n",
    description: "다국어 지원, 로컬라이징, 번역 품질 관리 전담",
    tier: "department",
    group: "product",
    benchmark: "Airbnb Localization",
    parentId: "cpo",
    pdcaPhases: ["do"],
  },

  // ---------------------------------------------------------------------------
  // Design 산하 유닛 (Tier 3)
  // ---------------------------------------------------------------------------
  {
    id: "visual-designer",
    name: "비주얼디자이너",
    nameEn: "Visual Designer",
    description:
      "금융 차트/아이콘/일러스트, 데이터 시각화, 브랜드 비주얼 전담",
    tier: "unit",
    group: "product",
    benchmark: "Fintech Data Visualization Specialist",
    parentId: "design",
    pdcaPhases: ["do"],
  },
  {
    id: "motion-designer",
    name: "모션디자이너",
    nameEn: "Motion Designer",
    description:
      "차트 애니메이션, 페이지 트랜지션, 마이크로인터랙션 전담",
    tier: "unit",
    group: "product",
    benchmark: "Fintech Micro-interaction Specialist",
    parentId: "design",
    pdcaPhases: ["do"],
  },
  {
    id: "ux-researcher",
    name: "UX리서처",
    nameEn: "UX Researcher",
    description:
      "금융 앱 유저 플로우 분석, 이탈 포인트 탐지, 유저빌리티 테스트 설계 전담",
    tier: "unit",
    group: "product",
    benchmark: "Fintech UX Specialist",
    parentId: "design",
    pdcaPhases: ["plan", "check"],
  },

  // ---------------------------------------------------------------------------
  // COO 산하 (Tier 2)
  // ---------------------------------------------------------------------------
  {
    id: "operations",
    name: "오퍼레이션부",
    nameEn: "Operations",
    description:
      "Amazon Operations 수준의 일일 운영, SLA 관리, 프로세스 자동화 전담",
    tier: "department",
    group: "support",
    benchmark: "Amazon Operations",
    parentId: "coo",
    pdcaPhases: ["do", "check"],
  },
  {
    id: "hr",
    name: "HR부",
    nameEn: "HR",
    description:
      "Google People Ops 수준의 채용, 팀 빌딩, 프리랜서 관리 전담",
    tier: "department",
    group: "support",
    benchmark: "Google People Operations",
    parentId: "coo",
    pdcaPhases: ["plan"],
  },
  {
    id: "docs",
    name: "문서부",
    nameEn: "Docs",
    description:
      "Stripe Docs 수준의 기술 문서, API 레퍼런스, 사용자 가이드 전담",
    tier: "department",
    group: "support",
    benchmark: "Stripe Docs",
    parentId: "coo",
    pdcaPhases: ["do", "act"],
  },

  // ---------------------------------------------------------------------------
  // CFO 산하 (Tier 2)
  // ---------------------------------------------------------------------------
  {
    id: "finance",
    name: "재무부",
    nameEn: "Finance",
    description:
      "CFO 수준의 예산 관리, 유닛 이코노믹스, 손익 분석 전담",
    tier: "department",
    group: "strategy",
    benchmark: "Sequoia CFO",
    parentId: "cfo",
    pdcaPhases: ["plan", "check"],
  },
  {
    id: "ir",
    name: "IR부",
    nameEn: "IR",
    description:
      "Sequoia 포트폴리오사 수준의 투자자 관계, 월간 리포트, 지표 관리 전담",
    tier: "department",
    group: "strategy",
    benchmark: "Sequoia Portfolio IR",
    parentId: "cfo",
    pdcaPhases: ["plan", "act"],
  },
  {
    id: "revenue-ops",
    name: "Revenue Ops부",
    nameEn: "Revenue Ops",
    description:
      "Stripe Revenue Team 수준의 결제/구독/환불 관리, 매출 분석 전담",
    tier: "department",
    group: "strategy",
    benchmark: "Stripe Revenue Team",
    parentId: "cfo",
    pdcaPhases: ["do", "check"],
  },

  // ---------------------------------------------------------------------------
  // CMO 산하 (Tier 2)
  // ---------------------------------------------------------------------------
  {
    id: "marketing",
    name: "마케팅부",
    nameEn: "Marketing",
    description:
      "Ogilvy 수준의 카피, 브랜드 전략, 채널 최적화 전담",
    tier: "department",
    group: "strategy",
    benchmark: "Ogilvy Creative",
    parentId: "cmo",
    pdcaPhases: ["plan", "do"],
  },
  {
    id: "growth",
    name: "그로스부",
    nameEn: "Growth",
    description:
      "Airbnb Growth Team 수준의 실험 설계, 전환 최적화, 바이럴 전담",
    tier: "department",
    group: "strategy",
    benchmark: "Airbnb Growth",
    parentId: "cmo",
    pdcaPhases: ["plan", "do", "check", "act"],
  },
  {
    id: "customer",
    name: "고객부",
    nameEn: "Customer",
    description:
      "Zappos 수준의 고객 경험, 온보딩, 이탈 방지 전담",
    tier: "department",
    group: "support",
    benchmark: "Zappos",
    parentId: "cmo",
    pdcaPhases: ["do", "check"],
  },
  {
    id: "competitive-intel",
    name: "경쟁정보부",
    nameEn: "Competitive Intel",
    description:
      "Palantir 수준의 경쟁사 모니터링, 시장 인텔리전스, 위협 탐지 전담",
    tier: "department",
    group: "strategy",
    benchmark: "Palantir Intelligence",
    parentId: "cmo",
    pdcaPhases: ["check"],
  },

  // ---------------------------------------------------------------------------
  // CDO 산하 (Tier 2)
  // ---------------------------------------------------------------------------
  {
    id: "analytics",
    name: "데이터부",
    nameEn: "Analytics",
    description:
      "Google Analytics Team 수준의 데이터 분석, KPI 추적, 인사이트 도출 전담",
    tier: "department",
    group: "strategy",
    benchmark: "Google Analytics",
    parentId: "cdo",
    pdcaPhases: ["check", "act"],
  },
  {
    id: "quant",
    name: "퀀트부",
    nameEn: "Quant",
    description:
      "Renaissance Technologies 수준의 퀀트 모델 개발, 백테스트, 알파 리서치 전담",
    tier: "department",
    group: "specialist",
    benchmark: "Renaissance Technologies",
    parentId: "cdo",
    pdcaPhases: ["plan", "do", "check"],
  },

  // ---------------------------------------------------------------------------
  // CLO 산하 (Tier 2)
  // ---------------------------------------------------------------------------
  {
    id: "legal",
    name: "법무부",
    nameEn: "Legal",
    description:
      "Kim & Chang 수준의 금융 규제, 컴플라이언스, 법적 리스크 관리 전담",
    tier: "department",
    group: "support",
    benchmark: "Kim & Chang",
    parentId: "clo",
    pdcaPhases: ["check", "act"],
  },
  {
    id: "compliance-ai",
    name: "컴플라이언스AI부",
    nameEn: "Compliance AI",
    description:
      "자동 금융 규제 체크, 투자 권유 문구 검증, 실시간 컴플라이언스 전담",
    tier: "department",
    group: "support",
    benchmark: "Automated Regulatory Check",
    parentId: "clo",
    pdcaPhases: ["check"],
  },

  // ---------------------------------------------------------------------------
  // Audit 산하 유닛 (Tier 3)
  // ---------------------------------------------------------------------------
  {
    id: "audit-code",
    name: "코드 검수관",
    nameEn: "Audit Code",
    description:
      "engineering/qa/security 결과물의 2차 교차검증, 아키텍처 일관성, 코딩 규칙 준수 확인",
    tier: "unit",
    group: "audit",
    benchmark: "Code Cross-Verification",
    parentId: "audit",
    pdcaPhases: ["check"],
  },
  {
    id: "audit-finance",
    name: "재무 검수관",
    nameEn: "Audit Finance",
    description:
      "finance 에이전트 수치의 교차검증, 30% 버퍼 확인, 가정 현실성 검증",
    tier: "unit",
    group: "audit",
    benchmark: "Financial Cross-Verification",
    parentId: "audit",
    pdcaPhases: ["check"],
  },
  {
    id: "audit-compliance",
    name: "규정 검수관",
    nameEn: "Audit Compliance",
    description:
      "legal 에이전트 검토의 2차 확인, 체크리스트 기반 규정 준수, 약관/방침 상태 추적",
    tier: "unit",
    group: "audit",
    benchmark: "Compliance Cross-Verification",
    parentId: "audit",
    pdcaPhases: ["check"],
  },

  // ---------------------------------------------------------------------------
  // 연동부 / 인프라부 (Tier 2 — CTO 산하로 재분류)
  // ---------------------------------------------------------------------------
  {
    id: "integrations",
    name: "연동부",
    nameEn: "Integrations",
    description:
      "Stripe Integration Team 수준의 외부 API 연동, 데이터 파이프라인 전담",
    tier: "department",
    group: "engineering",
    benchmark: "Stripe Integration",
    parentId: "cto",
    pdcaPhases: ["do", "check"],
  },
  {
    id: "devops",
    name: "인프라부",
    nameEn: "DevOps",
    description:
      "Netflix SRE 수준의 인프라 안정성, 배포 자동화, 모니터링 전담",
    tier: "department",
    group: "engineering",
    benchmark: "Netflix SRE",
    parentId: "cto",
    pdcaPhases: ["do", "check", "act"],
  },
] as const;

// =============================================================================
// Agent Relations (보고 체계 + 협업 + 감사 관계)
// =============================================================================

export const AGENT_RELATIONS: readonly AgentRelation[] = [
  // ---------------------------------------------------------------------------
  // C-Suite → CEO
  // ---------------------------------------------------------------------------
  { from: "cto", to: "ceo", type: "reports_to" },
  { from: "cpo", to: "ceo", type: "reports_to" },
  { from: "coo", to: "ceo", type: "reports_to" },
  { from: "cfo", to: "ceo", type: "reports_to" },
  { from: "cmo", to: "ceo", type: "reports_to" },
  { from: "cdo", to: "ceo", type: "reports_to" },
  { from: "clo", to: "ceo", type: "reports_to" },

  // ---------------------------------------------------------------------------
  // CEO 직속
  // ---------------------------------------------------------------------------
  { from: "secretary", to: "ceo", type: "reports_to" },
  { from: "investigator", to: "ceo", type: "reports_to" },
  { from: "strategy", to: "ceo", type: "reports_to" },
  { from: "pitch", to: "ceo", type: "reports_to" },
  { from: "audit", to: "ceo", type: "reports_to" },
  { from: "user-tester", to: "ceo", type: "reports_to" },
  { from: "stockpilot-improver", to: "ceo", type: "reports_to" },

  // ---------------------------------------------------------------------------
  // CTO 산하 부서
  // ---------------------------------------------------------------------------
  { from: "engineering", to: "cto", type: "reports_to" },
  { from: "frontend-dev", to: "cto", type: "reports_to" },
  { from: "backend-dev", to: "cto", type: "reports_to" },
  { from: "realtime-dev", to: "cto", type: "reports_to" },
  { from: "infra-dev", to: "cto", type: "reports_to" },
  { from: "performance", to: "cto", type: "reports_to" },
  { from: "security", to: "cto", type: "reports_to" },
  { from: "qa", to: "cto", type: "reports_to" },
  { from: "code-janitor", to: "cto", type: "reports_to" },
  { from: "integrations", to: "cto", type: "reports_to" },
  { from: "devops", to: "cto", type: "reports_to" },

  // ---------------------------------------------------------------------------
  // Code Janitor 산하 유닛
  // ---------------------------------------------------------------------------
  { from: "import-police", to: "code-janitor", type: "reports_to" },
  { from: "dead-code-hunter", to: "code-janitor", type: "reports_to" },
  { from: "style-enforcer", to: "code-janitor", type: "reports_to" },
  { from: "architecture-guard", to: "code-janitor", type: "reports_to" },
  { from: "file-organizer", to: "code-janitor", type: "reports_to" },

  // ---------------------------------------------------------------------------
  // CPO 산하 부서
  // ---------------------------------------------------------------------------
  { from: "product", to: "cpo", type: "reports_to" },
  { from: "design", to: "cpo", type: "reports_to" },
  { from: "onboarding", to: "cpo", type: "reports_to" },
  { from: "i18n", to: "cpo", type: "reports_to" },

  // ---------------------------------------------------------------------------
  // Design 산하 유닛
  // ---------------------------------------------------------------------------
  { from: "visual-designer", to: "design", type: "reports_to" },
  { from: "motion-designer", to: "design", type: "reports_to" },
  { from: "ux-researcher", to: "design", type: "reports_to" },

  // ---------------------------------------------------------------------------
  // COO 산하 부서
  // ---------------------------------------------------------------------------
  { from: "operations", to: "coo", type: "reports_to" },
  { from: "hr", to: "coo", type: "reports_to" },
  { from: "docs", to: "coo", type: "reports_to" },

  // ---------------------------------------------------------------------------
  // CFO 산하 부서
  // ---------------------------------------------------------------------------
  { from: "finance", to: "cfo", type: "reports_to" },
  { from: "ir", to: "cfo", type: "reports_to" },
  { from: "revenue-ops", to: "cfo", type: "reports_to" },

  // ---------------------------------------------------------------------------
  // CMO 산하 부서
  // ---------------------------------------------------------------------------
  { from: "marketing", to: "cmo", type: "reports_to" },
  { from: "growth", to: "cmo", type: "reports_to" },
  { from: "customer", to: "cmo", type: "reports_to" },
  { from: "competitive-intel", to: "cmo", type: "reports_to" },

  // ---------------------------------------------------------------------------
  // CDO 산하 부서
  // ---------------------------------------------------------------------------
  { from: "analytics", to: "cdo", type: "reports_to" },
  { from: "quant", to: "cdo", type: "reports_to" },

  // ---------------------------------------------------------------------------
  // CLO 산하 부서
  // ---------------------------------------------------------------------------
  { from: "legal", to: "clo", type: "reports_to" },
  { from: "compliance-ai", to: "clo", type: "reports_to" },

  // ---------------------------------------------------------------------------
  // Audit 산하 유닛
  // ---------------------------------------------------------------------------
  { from: "audit-code", to: "audit", type: "reports_to" },
  { from: "audit-finance", to: "audit", type: "reports_to" },
  { from: "audit-compliance", to: "audit", type: "reports_to" },

  // ---------------------------------------------------------------------------
  // 감사(Audit) 관계
  // ---------------------------------------------------------------------------
  { from: "audit-code", to: "engineering", type: "audits" },
  { from: "audit-code", to: "qa", type: "audits" },
  { from: "audit-code", to: "security", type: "audits" },
  { from: "audit-finance", to: "finance", type: "audits" },
  { from: "audit-compliance", to: "legal", type: "audits" },
  { from: "audit", to: "engineering", type: "audits" },
  { from: "audit", to: "finance", type: "audits" },
  { from: "audit", to: "legal", type: "audits" },
  { from: "audit", to: "product", type: "audits" },

  // ---------------------------------------------------------------------------
  // 협업(Collaborates) 관계
  // ---------------------------------------------------------------------------
  { from: "frontend-dev", to: "backend-dev", type: "collaborates" },
  { from: "frontend-dev", to: "design", type: "collaborates" },
  { from: "engineering", to: "qa", type: "collaborates" },
  { from: "engineering", to: "security", type: "collaborates" },
  { from: "marketing", to: "legal", type: "collaborates" },
  { from: "growth", to: "analytics", type: "collaborates" },
  { from: "growth", to: "onboarding", type: "collaborates" },
  { from: "product", to: "design", type: "collaborates" },
  { from: "product", to: "engineering", type: "collaborates" },
  { from: "devops", to: "security", type: "collaborates" },
  { from: "devops", to: "infra-dev", type: "collaborates" },
  { from: "finance", to: "revenue-ops", type: "collaborates" },
  { from: "ir", to: "finance", type: "collaborates" },
  { from: "ir", to: "analytics", type: "collaborates" },
  { from: "cdo", to: "clo", type: "collaborates" },
  { from: "compliance-ai", to: "marketing", type: "collaborates" },
  { from: "hr", to: "cto", type: "collaborates" },
  { from: "customer", to: "product", type: "collaborates" },
  { from: "quant", to: "engineering", type: "collaborates" },
  { from: "realtime-dev", to: "integrations", type: "collaborates" },
  { from: "performance", to: "frontend-dev", type: "collaborates" },
  { from: "performance", to: "backend-dev", type: "collaborates" },
  { from: "ux-researcher", to: "onboarding", type: "collaborates" },
  { from: "visual-designer", to: "frontend-dev", type: "collaborates" },
  { from: "motion-designer", to: "frontend-dev", type: "collaborates" },
  { from: "strategy", to: "finance", type: "collaborates" },
  { from: "pitch", to: "ir", type: "collaborates" },
  { from: "stockpilot-improver", to: "engineering", type: "collaborates" },
  { from: "investigator", to: "engineering", type: "collaborates" },
] as const;

// =============================================================================
// Utility Functions
// =============================================================================

/** ID로 에이전트 조회 */
export function getAgentById(id: string): Agent | undefined {
  return AGENTS.find((agent) => agent.id === id);
}

/** 특정 에이전트의 직속 하위 에이전트 목록 */
export function getChildAgents(parentId: string): Agent[] {
  return AGENTS.filter((agent) => agent.parentId === parentId);
}

/** 특정 에이전트의 보고 대상 */
export function getReportingTo(agentId: string): Agent | undefined {
  const agent = getAgentById(agentId);
  if (!agent?.parentId) return undefined;
  return getAgentById(agent.parentId);
}

/** 티어별 에이전트 필터 */
export function getAgentsByTier(tier: AgentTier): Agent[] {
  return AGENTS.filter((agent) => agent.tier === tier);
}

/** 그룹별 에이전트 필터 */
export function getAgentsByGroup(group: AgentGroup): Agent[] {
  return AGENTS.filter((agent) => agent.group === group);
}

/** 특정 에이전트와 관련된 모든 관계 */
export function getRelationsFor(agentId: string): AgentRelation[] {
  return AGENT_RELATIONS.filter(
    (relation) => relation.from === agentId || relation.to === agentId,
  );
}

/** 특정 에이전트가 감사하는 대상 목록 */
export function getAuditTargets(auditorId: string): AgentRelation[] {
  return AGENT_RELATIONS.filter(
    (relation) => relation.from === auditorId && relation.type === "audits",
  );
}

/** 특정 에이전트와 협업하는 대상 목록 */
export function getCollaborators(agentId: string): AgentRelation[] {
  return AGENT_RELATIONS.filter(
    (relation) =>
      (relation.from === agentId || relation.to === agentId) &&
      relation.type === "collaborates",
  );
}

/** 루트에서 특정 에이전트까지의 경로 (breadcrumb) */
export function getAgentPath(agentId: string): Agent[] {
  const path: Agent[] = [];
  let current = getAgentById(agentId);

  while (current) {
    path.unshift(current);
    current = current.parentId
      ? getAgentById(current.parentId)
      : undefined;
  }

  return path;
}

/** 조직도 통계 */
export function getOrganizationStats(): {
  totalAgents: number;
  byTier: Record<AgentTier, number>;
  byGroup: Record<AgentGroup, number>;
  maxDepth: number;
} {
  const tiers: AgentTier[] = ["ceo", "c-suite", "department", "unit"];
  const groups: AgentGroup[] = [
    "executive",
    "strategy",
    "product",
    "engineering",
    "support",
    "audit",
    "specialist",
  ];

  const byTier = {} as Record<AgentTier, number>;
  for (const tier of tiers) {
    byTier[tier] = AGENTS.filter((a) => a.tier === tier).length;
  }

  const byGroup = {} as Record<AgentGroup, number>;
  for (const group of groups) {
    byGroup[group] = AGENTS.filter((a) => a.group === group).length;
  }

  let maxDepth = 0;
  for (const agent of AGENTS) {
    const pathLength = getAgentPath(agent.id).length;
    if (pathLength > maxDepth) {
      maxDepth = pathLength;
    }
  }

  return {
    totalAgents: AGENTS.length,
    byTier,
    byGroup,
    maxDepth,
  };
}
