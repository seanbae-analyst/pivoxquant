#!/usr/bin/env node
/**
 * sync-agents.mjs
 *
 * .claude/agents/*.md 파일을 스캔해서
 * src/data/agents-registry.ts의 AGENTS 배열과 AGENT_RELATIONS 배열을 동기화한다.
 *
 * 실행: node scripts/sync-agents.mjs
 * 또는:  npm run sync-agents
 */

import { readFileSync, readdirSync, writeFileSync } from "fs";
import { join, basename, dirname } from "path";
import { fileURLToPath } from "url";

// ---------------------------------------------------------------------------
// 경로 설정
// ---------------------------------------------------------------------------
const __dirname = dirname(fileURLToPath(import.meta.url));
const AGENTS_DIR = "/Users/seanbae/Desktop/취준/.claude/agents";
const REGISTRY_PATH = join(
  __dirname,
  "../src/data/agents-registry.ts"
);
const README_PATH = join(AGENTS_DIR, "README.md");

// ---------------------------------------------------------------------------
// 헬퍼: frontmatter 파싱 (gray-matter 없이 regex로)
// ---------------------------------------------------------------------------
function parseFrontmatter(content) {
  const match = content.match(/^---\s*\n([\s\S]*?)\n---\s*\n?([\s\S]*)$/);
  if (!match) return { data: {}, body: content };

  const rawYaml = match[1];
  const body = match[2] || "";

  // 단순 key: "value" 또는 key: value 파싱 (중첩 없음)
  const data = {};
  for (const line of rawYaml.split("\n")) {
    const kv = line.match(/^(\w[\w-]*):\s*"?(.*?)"?\s*$/);
    if (kv) {
      data[kv[1].trim()] = kv[2].trim();
    }
  }

  return { data, body };
}

// ---------------------------------------------------------------------------
// 헬퍼: description에서 벤치마크 추출
// "Netflix Platform Team 수준의..." → "Netflix Platform Team"
// ---------------------------------------------------------------------------
function extractBenchmark(description, body) {
  // description에서 "XXX 수준" 패턴 추출
  const benchmarkMatch = description.match(/^([^,—\-]+?)\s+수준/);
  if (benchmarkMatch) {
    return benchmarkMatch[1].trim();
  }

  // body의 첫 번째 h1 이후 부제목에서 찾기
  // e.g. "# Analytics Agent (데이터부) — Google Data Science Standard"
  const bodyBenchmark = body.match(/^#[^\n]+—\s*(.+?)(?:\s+Standard)?\s*$/m);
  if (bodyBenchmark) {
    return bodyBenchmark[1].trim().replace(/ Standard$/, "");
  }

  return "Agent";
}

// ---------------------------------------------------------------------------
// 헬퍼: description에서 한글 이름 추출
// "비서 — CEO 전담 비서, ..." → "비서"
// "인프라개발부 — Netflix Platform..." → "인프라개발부"
// ---------------------------------------------------------------------------
function extractKoreanName(description, agentId) {
  // "한글명 — ..." 패턴
  const dashMatch = description.match(/^([^—]+?)\s*—/);
  if (dashMatch) {
    const candidate = dashMatch[1].trim();
    // 순수 한글/한자/영문 조합이면 사용
    if (/^[가-힣A-Za-z0-9\s\-]+$/.test(candidate) && candidate.length < 20) {
      return candidate;
    }
  }

  // ID에서 추론 (fallback)
  return agentId
    .split("-")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

// ---------------------------------------------------------------------------
// 헬퍼: ID에서 영문 이름 생성
// "infra-dev" → "Infra Dev"
// "audit-code" → "Audit Code"
// ---------------------------------------------------------------------------
function idToNameEn(id) {
  return id
    .split("-")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

// ---------------------------------------------------------------------------
// 헬퍼: tier 추론
// C-suite 키워드 포함이면 c-suite, CEO면 ceo, 나머지는 body/id로 판단
// ---------------------------------------------------------------------------
const C_SUITE_IDS = ["cto", "cpo", "coo", "cfo", "cmo", "cdo", "clo"];
const KNOWN_UNITS = [
  "import-police",
  "dead-code-hunter",
  "style-enforcer",
  "architecture-guard",
  "file-organizer",
  "visual-designer",
  "motion-designer",
  "ux-researcher",
  "audit-code",
  "audit-finance",
  "audit-compliance",
];

function inferTier(id) {
  if (id === "ceo") return "ceo";
  if (C_SUITE_IDS.includes(id)) return "c-suite";
  if (KNOWN_UNITS.includes(id)) return "unit";
  return "department";
}

// ---------------------------------------------------------------------------
// 헬퍼: group 추론
// ---------------------------------------------------------------------------
const GROUP_MAP = {
  // executive
  ceo: "executive",
  secretary: "executive",
  investigator: "specialist",
  // c-suite
  cto: "engineering",
  cpo: "product",
  coo: "support",
  cfo: "strategy",
  cmo: "strategy",
  cdo: "strategy",
  clo: "support",
  // strategy
  strategy: "strategy",
  pitch: "strategy",
  finance: "strategy",
  ir: "strategy",
  "revenue-ops": "strategy",
  marketing: "strategy",
  growth: "strategy",
  analytics: "strategy",
  "competitive-intel": "strategy",
  // product
  product: "product",
  design: "product",
  onboarding: "product",
  i18n: "product",
  "visual-designer": "product",
  "motion-designer": "product",
  "ux-researcher": "product",
  // engineering
  engineering: "engineering",
  "frontend-dev": "engineering",
  "backend-dev": "engineering",
  "realtime-dev": "engineering",
  "infra-dev": "engineering",
  performance: "engineering",
  security: "engineering",
  qa: "engineering",
  "code-janitor": "engineering",
  "import-police": "engineering",
  "dead-code-hunter": "engineering",
  "style-enforcer": "engineering",
  "architecture-guard": "engineering",
  "file-organizer": "engineering",
  integrations: "engineering",
  devops: "engineering",
  // support
  operations: "support",
  hr: "support",
  docs: "support",
  customer: "support",
  legal: "support",
  "compliance-ai": "support",
  // audit
  audit: "audit",
  "user-tester": "audit",
  "audit-code": "audit",
  "audit-finance": "audit",
  "audit-compliance": "audit",
  // specialist
  quant: "specialist",
  "stockpilot-improver": "specialist",
};

function inferGroup(id) {
  return GROUP_MAP[id] || "specialist";
}

// ---------------------------------------------------------------------------
// 헬퍼: pdcaPhases 추론 (body 키워드로)
// ---------------------------------------------------------------------------
function inferPdcaPhases(body, id) {
  const lower = body.toLowerCase();
  const phases = [];

  if (lower.includes("plan") || lower.includes("기획") || lower.includes("계획"))
    phases.push("plan");
  if (
    lower.includes(" do ") ||
    lower.includes("구현") ||
    lower.includes("개발") ||
    lower.includes("실행") ||
    lower.includes("작성")
  )
    phases.push("do");
  if (
    lower.includes("check") ||
    lower.includes("검증") ||
    lower.includes("검수") ||
    lower.includes("테스트") ||
    lower.includes("분석")
  )
    phases.push("check");
  if (
    lower.includes("act") ||
    lower.includes("개선") ||
    lower.includes("최적화") ||
    lower.includes("배포")
  )
    phases.push("act");

  return phases.length > 0 ? phases : ["do"];
}

// ---------------------------------------------------------------------------
// README.md 파싱 → parentId 맵 구축
// 조직도 텍스트에서 "child → parent" 관계 추출
// ---------------------------------------------------------------------------
function buildParentMapFromReadme(readmeContent) {
  const parentMap = {};

  // C-Suite → CEO
  C_SUITE_IDS.forEach((id) => {
    parentMap[id] = "ceo";
  });

  // README의 부서별 요약 표에서 파일명 추출
  // 각 섹션 헤더로 그룹화: "### 전략 그룹", "### 제품 그룹", "### 지원 그룹", "### 감사"
  // 파일명 → C-Suite 매핑은 README 구조로 파악

  // 전략 그룹: CFO 또는 CMO 또는 CDO 하위
  const strategyGroupDepts = ["strategy", "finance", "growth", "marketing", "analytics"];
  // strategy, pitch는 CEO 직속
  // finance → cfo, growth/marketing → cmo, analytics → cdo
  parentMap["strategy"] = "ceo";
  parentMap["pitch"] = "ceo";
  parentMap["finance"] = "cfo";
  parentMap["ir"] = "cfo";
  parentMap["revenue-ops"] = "cfo";
  parentMap["growth"] = "cmo";
  parentMap["marketing"] = "cmo";
  parentMap["competitive-intel"] = "cmo";
  parentMap["analytics"] = "cdo";
  parentMap["quant"] = "cdo";

  // 제품 그룹 → CPO
  parentMap["product"] = "cpo";
  parentMap["design"] = "cpo";
  parentMap["onboarding"] = "cpo";
  parentMap["i18n"] = "cpo";

  // Design 산하
  parentMap["visual-designer"] = "design";
  parentMap["motion-designer"] = "design";
  parentMap["ux-researcher"] = "design";

  // 지원 그룹
  parentMap["legal"] = "clo";
  parentMap["compliance-ai"] = "clo";
  parentMap["security"] = "cto";
  parentMap["devops"] = "cto";
  parentMap["docs"] = "coo";
  parentMap["customer"] = "cmo";
  parentMap["operations"] = "coo";
  parentMap["hr"] = "coo";

  // CTO 산하 공학 부서
  parentMap["engineering"] = "cto";
  parentMap["frontend-dev"] = "cto";
  parentMap["backend-dev"] = "cto";
  parentMap["realtime-dev"] = "cto";
  parentMap["infra-dev"] = "cto";
  parentMap["performance"] = "cto";
  parentMap["qa"] = "cto";
  parentMap["code-janitor"] = "cto";
  parentMap["integrations"] = "cto";

  // Code Janitor 산하 유닛
  parentMap["import-police"] = "code-janitor";
  parentMap["dead-code-hunter"] = "code-janitor";
  parentMap["style-enforcer"] = "code-janitor";
  parentMap["architecture-guard"] = "code-janitor";
  parentMap["file-organizer"] = "code-janitor";

  // CEO 직속 감사/특수
  parentMap["audit"] = "ceo";
  parentMap["user-tester"] = "ceo";
  parentMap["stockpilot-improver"] = "ceo";
  parentMap["secretary"] = "ceo";
  parentMap["investigator"] = "ceo";

  // Audit 산하 유닛
  parentMap["audit-code"] = "audit";
  parentMap["audit-finance"] = "audit";
  parentMap["audit-compliance"] = "audit";

  // CEO 자신
  parentMap["ceo"] = null;

  return parentMap;
}

// ---------------------------------------------------------------------------
// agents-registry.ts 현재 내용 파싱
// AGENTS 배열에서 기존 에이전트 정보 추출 (name, nameEn, benchmark 등 보존용)
// ---------------------------------------------------------------------------
function parseExistingAgents(registryContent) {
  const existing = {};

  // 각 에이전트 블록 추출
  const agentBlockRegex =
    /\{\s*\n\s*id:\s*"([^"]+)"[\s\S]*?\},/g;
  let match;

  while ((match = agentBlockRegex.exec(registryContent)) !== null) {
    const block = match[0];
    const id = match[1];

    const getName = (key) => {
      const m = block.match(new RegExp(`${key}:\\s*(?:"([^"]*)")`));
      return m ? m[1] : null;
    };
    const getMultiline = (key) => {
      // multiline string (concatenated)
      const m = block.match(
        new RegExp(`${key}:\\s*\\n\\s*"([^"]+(?:\\s*\\n\\s*[^"]+)*)"`)
      );
      if (m) return m[1].replace(/"\s*\+\s*"/g, "").replace(/\s+/g, " ").trim();
      return getName(key);
    };

    const getTier = () => {
      const m = block.match(/tier:\s*"([^"]+)"/);
      return m ? m[1] : null;
    };
    const getGroup = () => {
      const m = block.match(/group:\s*"([^"]+)"/);
      return m ? m[1] : null;
    };
    const getBenchmark = () => {
      const m = block.match(/benchmark:\s*"([^"]+)"/);
      return m ? m[1] : null;
    };
    const getParentId = () => {
      const m = block.match(/parentId:\s*(?:"([^"]+)"|null)/);
      return m ? (m[1] || null) : null;
    };
    const getPdcaPhases = () => {
      const m = block.match(/pdcaPhases:\s*\[([^\]]+)\]/);
      if (!m) return [];
      return m[1]
        .split(",")
        .map((s) => s.trim().replace(/"/g, ""))
        .filter(Boolean);
    };

    existing[id] = {
      id,
      name: getName("name"),
      nameEn: getName("nameEn"),
      description: getMultiline("description") || getName("description"),
      tier: getTier(),
      group: getGroup(),
      benchmark: getBenchmark(),
      parentId: getParentId(),
      pdcaPhases: getPdcaPhases(),
    };
  }

  return existing;
}

// ---------------------------------------------------------------------------
// 에이전트 .md 파일 스캔
// ---------------------------------------------------------------------------
function scanAgentFiles(agentsDir) {
  const files = readdirSync(agentsDir).filter(
    (f) => f.endsWith(".md") && f !== "README.md"
  );

  const agents = [];
  for (const file of files) {
    const id = basename(file, ".md");
    const content = readFileSync(join(agentsDir, file), "utf-8");
    const { data, body } = parseFrontmatter(content);

    agents.push({ id, data, body, file });
  }

  return agents;
}

// ---------------------------------------------------------------------------
// 에이전트 객체 빌드
// 우선순위: 기존 registry 값 > .md 파싱값 > 추론값
// ---------------------------------------------------------------------------
function buildAgent(id, data, body, existing, parentMap) {
  const existingAgent = existing[id] || {};

  // description: .md의 frontmatter description 우선
  const rawDescription = data.description || existingAgent.description || id;
  // 파일명 접두사 제거: "비서 — ..." 형태에서 한글명 부분 제거해 설명만 남기기
  const description = rawDescription
    .replace(/^[^—]+—\s*/, "") // "비서 — CEO 전담..." → "CEO 전담..."
    .trim() || rawDescription;

  // name (한글): 기존값 보존 > .md에서 추출
  const name =
    existingAgent.name ||
    extractKoreanName(rawDescription, id);

  // nameEn: 기존값 보존 > ID에서 생성
  const nameEn = existingAgent.nameEn || idToNameEn(id);

  // tier: 기존값 보존 > 추론
  const tier = existingAgent.tier || inferTier(id);

  // group: 기존값 보존 > 추론
  const group = existingAgent.group || inferGroup(id);

  // benchmark: .md body에서 추출 시도 > 기존값 보존 > description에서 추출
  const benchmark =
    existingAgent.benchmark ||
    extractBenchmark(rawDescription, body);

  // parentId: 기존값 보존 > README 맵 > null
  const parentId =
    id in parentMap
      ? parentMap[id]
      : existingAgent.parentId !== undefined
      ? existingAgent.parentId
      : null;

  // pdcaPhases: 기존값 보존 > body에서 추론
  const pdcaPhases =
    existingAgent.pdcaPhases && existingAgent.pdcaPhases.length > 0
      ? existingAgent.pdcaPhases
      : inferPdcaPhases(body, id);

  return { id, name, nameEn, description, tier, group, benchmark, parentId, pdcaPhases };
}

// ---------------------------------------------------------------------------
// AGENTS 배열 → TypeScript 소스 직렬화
// ---------------------------------------------------------------------------
function serializeAgents(agents, existingContent) {
  // 기존 섹션 그룹화를 최대한 유지하기 위해
  // tier + parentId 기준으로 정렬

  const tierOrder = { ceo: 0, "c-suite": 1, department: 2, unit: 3 };
  const sorted = [...agents].sort((a, b) => {
    const ta = tierOrder[a.tier] ?? 9;
    const tb = tierOrder[b.tier] ?? 9;
    if (ta !== tb) return ta - tb;
    // 같은 tier면 parentId 기준 (alphabetical)
    const pa = a.parentId || "";
    const pb = b.parentId || "";
    if (pa !== pb) return pa.localeCompare(pb);
    return a.id.localeCompare(b.id);
  });

  const lines = [];

  for (const agent of sorted) {
    // description이 길면 멀티라인
    const desc = agent.description.replace(/"/g, '\\"');
    const descStr =
      desc.length > 50
        ? `\n      "${desc}"`
        : `"${desc}"`;

    const parentStr =
      agent.parentId === null ? "null" : `"${agent.parentId}"`;
    const phasesStr = agent.pdcaPhases
      .map((p) => `"${p}"`)
      .join(", ");

    lines.push(
      `  {
    id: "${agent.id}",
    name: "${agent.name}",
    nameEn: "${agent.nameEn}",
    description: ${descStr},
    tier: "${agent.tier}",
    group: "${agent.group}",
    benchmark: "${agent.benchmark}",
    parentId: ${parentStr},
    pdcaPhases: [${phasesStr}],
  },`
    );
  }

  return lines.join("\n\n");
}

// ---------------------------------------------------------------------------
// AGENT_RELATIONS 배열 재생성
// 기존 relations 보존 + 새 에이전트는 reports_to 자동 추가
// ---------------------------------------------------------------------------
function buildRelations(agents, existingContent) {
  // 기존 AGENT_RELATIONS 블록 추출
  const relationsMatch = existingContent.match(
    /export const AGENT_RELATIONS[^=]+=\s*\[([^;]+?)\] as const;/s
  );

  if (!relationsMatch) return null; // relations 섹션 없으면 건드리지 않음

  const existingRelationsBlock = relationsMatch[1];
  const existingRelations = [];
  const relRegex =
    /\{\s*from:\s*"([^"]+)",\s*to:\s*"([^"]+)",\s*type:\s*"([^"]+)"\s*\}/g;
  let rm;
  while ((rm = relRegex.exec(existingRelationsBlock)) !== null) {
    existingRelations.push({ from: rm[1], to: rm[2], type: rm[3] });
  }

  const agentIds = new Set(agents.map((a) => a.id));

  // 1. 삭제된 에이전트 관련 relations 제거
  const filtered = existingRelations.filter(
    (r) => agentIds.has(r.from) && agentIds.has(r.to)
  );

  // 2. 새 에이전트 reports_to 추가 (parentId 있으면)
  const existingFromTo = new Set(
    filtered.map((r) => `${r.from}__${r.to}__${r.type}`)
  );

  for (const agent of agents) {
    if (agent.parentId) {
      const key = `${agent.id}__${agent.parentId}__reports_to`;
      if (!existingFromTo.has(key)) {
        filtered.push({ from: agent.id, to: agent.parentId, type: "reports_to" });
        existingFromTo.add(key);
      }
    }
  }

  return filtered;
}

function serializeRelations(relations) {
  return relations
    .map((r) => `  { from: "${r.from}", to: "${r.to}", type: "${r.type}" },`)
    .join("\n");
}

// ---------------------------------------------------------------------------
// 메인
// ---------------------------------------------------------------------------
function main() {
  console.log("sync-agents: 시작");
  console.log(`  소스 디렉토리: ${AGENTS_DIR}`);
  console.log(`  대상 파일: ${REGISTRY_PATH}`);
  console.log();

  // 1. 에이전트 .md 파일 스캔
  const scannedFiles = scanAgentFiles(AGENTS_DIR);
  console.log(`  .md 파일 발견: ${scannedFiles.length}개`);

  // 2. 기존 registry 읽기
  const existingContent = readFileSync(REGISTRY_PATH, "utf-8");
  const existingAgents = parseExistingAgents(existingContent);
  const existingIds = new Set(Object.keys(existingAgents));
  console.log(`  registry 기존 에이전트: ${existingIds.size}개`);

  // 3. README 파싱 → parentId 맵
  let readmeContent = "";
  try {
    readmeContent = readFileSync(README_PATH, "utf-8");
  } catch {
    console.warn("  WARNING: README.md 없음 — parentId 맵을 기본값으로 생성");
  }
  const parentMap = buildParentMapFromReadme(readmeContent);

  // 4. 새 에이전트 목록 빌드
  const scannedIds = new Set(scannedFiles.map((f) => f.id));

  const added = scannedFiles.filter((f) => !existingIds.has(f.id));
  const removed = [...existingIds].filter((id) => !scannedIds.has(id));
  const updated = scannedFiles.filter(
    (f) => existingIds.has(f.id)
  );

  console.log(`  추가: ${added.length}개, 삭제: ${removed.length}개, 유지: ${updated.length}개`);

  if (added.length === 0 && removed.length === 0) {
    console.log("\n  변경사항 없음 — registry 업데이트 생략");
    return;
  }

  // 5. 전체 에이전트 객체 배열 생성
  const allAgents = scannedFiles.map(({ id, data, body }) =>
    buildAgent(id, data, body, existingAgents, parentMap)
  );

  // 6. AGENTS 직렬화
  const agentsBlock = serializeAgents(allAgents, existingContent);

  // 7. AGENT_RELATIONS 재생성
  const newRelations = buildRelations(allAgents, existingContent);

  // 8. registry 파일 교체
  const today = new Date().toISOString().slice(0, 10);
  let newContent = existingContent;

  // 헤더 날짜 업데이트
  newContent = newContent.replace(
    /\/\/ Last updated: \S+/,
    `// Last updated: ${today}`
  );

  // AGENTS 배열 교체
  newContent = newContent.replace(
    /(export const AGENTS[^=]+=\s*\[)[^;]+(] as const;)/s,
    `$1\n${agentsBlock}\n$2`
  );

  // AGENT_RELATIONS 배열 교체 (relations가 있을 때만)
  if (newRelations) {
    const relationsBlock = serializeRelations(newRelations);
    newContent = newContent.replace(
      /(export const AGENT_RELATIONS[^=]+=\s*\[)[^;]+(] as const;)/s,
      `$1\n${relationsBlock}\n$2`
    );
  }

  writeFileSync(REGISTRY_PATH, newContent, "utf-8");

  // 9. 변경 요약 출력
  console.log("\n  === 변경 요약 ===");
  if (added.length > 0) {
    console.log(`  [추가됨] (${added.length}개):`);
    added.forEach((f) => console.log(`    + ${f.id}`));
  }
  if (removed.length > 0) {
    console.log(`  [삭제됨] (${removed.length}개):`);
    removed.forEach((id) => console.log(`    - ${id}`));
  }
  console.log(`\n  registry 업데이트 완료: ${REGISTRY_PATH}`);
  console.log(`  총 에이전트 수: ${allAgents.length}개`);
  if (newRelations) {
    console.log(`  총 relations 수: ${newRelations.length}개`);
  }
}

main();
