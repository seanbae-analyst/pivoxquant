# AI 에이전트 보안 사건 — 45건

증거 수준: primary 15 · vendor 18 · press 12

AI 역할: 공격자가 에이전트 사용 17 · 공격자가 AI 도구 보조 5 · 피해자의 AI 시스템이 뚫림 12 · AI 취약점 공개 6 · AI 관여 추정 1 · AI 시스템이 스스로 일탈(평가·연구 중) 3 · AI 관여 없음(비교 사례) 1

## 통제별 — 이 통제가 실패했거나 관련된 사건 수

| # | 통제 | 전체 | 1차 | 벤더 | 보도 |
|---|---|---|---|---|---|
| 1 | 인벤토리 | **7** | 2 | 2 | 3 |
| 2 | 공급자 관리 | **10** | 4 | 4 | 2 |
| 3 | 고유 식별자 | **9** | 1 | 5 | 3 |
| 4 | 최소 권한 | **23** | 8 | 9 | 6 |
| 5 | 사람 승인 | **12** | 4 | 3 | 5 |
| 6 | 감사 기록 | **20** | 9 | 5 | 6 |
| 7 | 즉시 중단 | **14** | 5 | 6 | 3 |

related_controls 는 finder 판단이다 — 논문에 쓰려면 2차 코딩 대상.

## 목록 (최신순)

- 2026-11-10 · KR · AI 관여 없음(비교 사례) · press — [금융보안원 '정보보호 상시평가 지원시스템' 침해 — 금감원 사칭 허위 계정으로 침투](https://www.boannews.com/news/articleView.html?idxno=147156) · 통제: unique_id, least_privilege, audit_trail
- 2026-11-09 · INTL · 공격자가 에이전트 사용 · vendor — [ARTEX 에이전트가 AWS 환경에서 금융 데이터·장기 키를 탐색 (Datadog 관측)](https://securitylabs.datadoghq.com/articles/artex-agentic-attacks-aws-environments/) · 통제: least_privilege, inventory, audit_trail, kill_switch
- 2026-10-26 · INTL · 피해자의 AI 시스템이 뚫림 · press — [다운로드 폴더에 심은 AGENTS.md/CLAUDE.md 로 Codex·Claude Code 하이재킹 — 악성코드 설치·OAuth 토큰 노출(실제 공격)](https://www.helpnetsecurity.com/2026/10/26/ai-coding-agents-malware-openai-codex/) · 통제: least_privilege, human_approval
- 2026-10-22 · US · 공격자가 에이전트 사용 · vendor — [Storm-0940(중국 연계) ARTEX 에이전트 — ConnectWise 클라우드 백업 공급망 침해·M365 테넌트 2,250+ 시도](https://www.wiz.io/blog/artex-in-the-wild-storm-0940-expands-targeting-of-it-and-software-vendors) · 통제: vendors, unique_id, least_privilege, kill_switch
- 2026-10-21 · INTL · 공격자가 에이전트 사용 · vendor — [CrowdStrike — Claude Code 기반 침입 에이전트를 운영한 미보고 행위자 4곳(의료·정부·SaaS)](https://www.crowdstrike.com/en-us/blog/crowdstrike-uncovers-new-agentic-ai-campaigns/) · 통제: audit_trail
- 2026-10-21 · INTL · 공격자가 에이전트 사용 · vendor — [Unit 42 — Telegram 위 Hermes Agent+DeepSeek V4 와 안전장치 끈 Cursor 로 대학 PII 5,200건·ETH 대량보유자 프로파일링](https://unit42.paloaltonetworks.com/ai-assisted-cybercrime-analysis/) · 통제: human_approval, least_privilege
- 2026-10-21 · US · 피해자의 AI 시스템이 뚫림 · primary — [LiteLLM 1.107.0 PyPI/Docker 자격증명 탈취 릴리스 — 폐기 안 된 에이전트 플랫폼 마스터 키가 근본 원인](https://docs.litellm.ai/blog/security-incident-oct-21-2026-attack-chain) · 통제: unique_id, least_privilege, kill_switch, audit_trail, vendors
- 2026-10-21 · INTL · 공격자가 에이전트 사용 · vendor — ['Skynet' 자율 공격 에이전트가 노출된 LLM 엔드포인트를 가로채 스캔·익스플로잇·채굴(모델 소유자 비용 부담)](https://www.security.com/threat-intelligence/ai-llmjacking-skynet) · 통제: inventory, unique_id, kill_switch
- 2026-10-19 · INTL · 공격자가 에이전트 사용 · press — [노출된 Cairn 에이전트 패널 — 1,200+ 사이트 공격·100+ 기업 도달에 토큰 비용 약 $5,000](https://thehackernews.com/2026/10/hackers-use-autonomous-ai-agents-to.html) · 통제: inventory
- 2026-10-15 · US · AI 시스템이 스스로 일탈(평가·연구 중) · primary — [OpenAI 내부 연구 모델이 승인 없이 타인의 테스트넷 지갑 자금을 사용](https://alignment.openai.com/misalignment-reports/using-a-funded-test-cryptocurrency-wallet-without-authorization/) · 통제: least_privilege, human_approval, audit_trail
- 2026-10-14 · KR · AI 관여 추정 · primary — [한국 금융권 연쇄 침해(신한은행 등 16개사→20개사) — AI 에이전트 도구 ARTEX 흔적, 당국은 '추정'](https://www.fsc.go.kr/no010101/87927) · 통제: inventory, least_privilege, audit_trail
- 2026-10-08 · US · AI 취약점 공개 · vendor — [AgentCorruption — AWS Bedrock AgentCore 에이전트에 프롬프트 하나로 IMDS 자격증명 추출, 계정·리전 내 전 에이전트 장악](https://labs.zenity.io/post/agentcorruption-how-a-single-prompt-collapsed-the-entire-cloud-security-model) · 통제: least_privilege, unique_id
- 2026-10-06 · INTL · 공격자가 에이전트 사용 · vendor — [CyberXero — 러시아어 초기접근 브로커가 Claude Code 에이전트 최대 51개와 PentAGI 로 우크라이나 에너지 기업 공격](https://socradar.io/blog/cyberxero-ai-iab-ukraine-critical-infrastructure/) · 통제: —
- 2026-10-01 · EU · 공격자가 에이전트 사용 · press — [자율 에이전트가 Zammad 제로데이 2개를 연결해 네덜란드 취약점공개기관(DIVD) 침해](https://www.helpnetsecurity.com/2026/10/01/divd-agentic-ai-attack-breach/) · 통제: audit_trail, kill_switch
- 2026-09-22 · INTL · 공격자가 에이전트 사용 · press — [오픈소스 에이전트 3종(Strix·Cairn·Hermes)으로 리테일러 27곳 침해, 카드 60만 건 탈취](https://www.techradar.com/pro/security/massive-chinese-hack-uses-ai-agents-to-steal-over-600-000-credit-cards-and-hit-hundreds-of-sites-with-malware) · 통제: inventory, audit_trail
- 2026-09-14 · EU · 공격자가 에이전트 사용 · primary — [스페인 AEPD — AI 에이전트가 공격 단계를 연결한 첫 개인정보 침해 신고 접수](https://www.aepd.es/prensa-y-comunicacion/blog/primera-notiviacion-brecha-datos-personales-causada-por-ataque-ejecutado-mediante-agente-ia) · 통제: audit_trail
- 2026-09-10 · US · 공격자가 에이전트 사용 · primary — [Anthropic 2026-09 위협 보고 — 2025-12~2026-08 7개 영역, '1인 공격자가 국가급 팀 수준' 사이버 사례](https://www.anthropic.com/threat-intelligence-report-september-2026) · 통제: —
- 2026-09-10 · INTL · 공격자가 에이전트 사용 · vendor — [수백 개 에이전트(Codex 하네스+DeepSeek)가 PaperCut 결함으로 48개국 395개 조직 침해, 자체 제외 목록 무시](https://www.greynoise.io/blog/ai-orchestrated-campaign-against-papercut-ng-mf) · 통제: kill_switch, audit_trail
- 2026-09-08 · INTL · 피해자의 AI 시스템이 뚫림 · vendor — [상용 인포스틸러 8종이 AI 코딩 에이전트 토큰·MCP 설정을 수집 목록에 추가; 유출 덤프에서 AI 서비스 토큰 555개(Okta)](https://www.gendigital.com/blog/insights/research/infostealers-your-ai-agent) · 통제: unique_id, kill_switch, audit_trail
- 2026-08-12 · OTHER · 공격자가 에이전트 사용 · press — [준자율 다중 에이전트가 4일간 대만 정부·원자력안전 규제기관 침해(7~8개 서브에이전트, 12개 공격 파동)](https://www.theregister.com/security/2026/08/12/near-autonomous-ai-agents-attack-taiwans-nuclear-safety-agency/5287055) · 통제: unique_id, audit_trail
- 2026-08-09 · KR · 공격자가 AI 도구 보조 · vendor — [북한 Kimsuky 가 자체 공격 서버에 오프라인 LLM 스택을 구축해 탈취 데이터 분류(한국 가상자산·외교 표적)](https://www.genians.co.kr/en/blog/threat_intelligence/kimsuky_ai_llm) · 통제: —
- 2026-07-30 · US · AI 시스템이 스스로 일탈(평가·연구 중) · primary — [Anthropic — 사이버 평가 중 Claude 가 외부 인터넷으로 나가 실제 조직 3곳에 무단 접근(이후 4번째·UK AISI 사례 추가)](https://www.anthropic.com/news/investigating-incidents-cybersecurity-evals) · 통제: kill_switch, least_privilege, audit_trail
- 2026-07-24 · OTHER · 공격자가 에이전트 사용 · press — [태국 재무부 내부망에서 Hermes 에이전트를 무인 실행한 사후 침투](https://thehackernews.com/2026/07/hacker-runs-hermes-ai-agent-unattended.html) · 통제: human_approval, audit_trail
- 2026-07-16 · US · AI 시스템이 스스로 일탈(평가·연구 중) · primary — [OpenAI 평가용 에이전트가 샌드박스를 탈출해 Hugging Face 프로덕션 침해(에이전트 1,200개·서버 41대)](https://huggingface.co/blog/security-incident-july-2026) · 통제: kill_switch, least_privilege, audit_trail, human_approval
- 2026-05-21 · US · 피해자의 AI 시스템이 뚫림 · primary — [에이전트 도구 연동 브로커 Composio 침해 — 고객 자격증명 1만 건 이상 유출](https://composio.dev/blog/composio-may-2026-security-incident) · 통제: vendors, least_privilege, kill_switch
- 2026-05-11 · US · 공격자가 AI 도구 보조 · vendor — [GTIG — 범죄 조직이 LLM 으로 2FA 우회 제로데이를 개발해 대량 악용을 준비, 사용 전 차단](https://cloud.google.com/blog/topics/threat-intelligence/ai-vulnerability-exploitation-initial-access) · 통제: —
- 2026-05-04 · INTL · 피해자의 AI 시스템이 뚫림 · press — [모스 부호 프롬프트 인젭션으로 Grok+Bankr 트레이딩 에이전트 지갑 $174~204k 유출](https://oecd.ai/en/incidents/2026-05-04-4a73) · 통제: least_privilege, human_approval
- 2026-04-22 · INTL · 공격자가 AI 도구 보조 · vendor — [북한 연계 그룹이 AI 코딩 도구로 Web3 개발자 공격 산업화 — 지갑 26,584건·약 $12M(1Q26)](https://expel.com/blog/inside-lazarus-how-north-korea-uses-ai-to-industrialize-attacks-on-developers/) · 통제: vendors, least_privilege
- 2026-04-21 · US · 피해자의 AI 시스템이 뚫림 · press — [Anthropic Claude Mythos Preview(제한 배포 사이버 모델)에 비인가 그룹이 제3자 벤더 환경 경유로 접근](https://techcrunch.com/2026/04/21/unauthorized-group-has-gained-access-to-anthropics-exclusive-cyber-tool-mythos-report-claims/) · 통제: vendors, unique_id
- 2026-02-09 · US · 피해자의 AI 시스템이 뚫림 · press — [Clinejection — GitHub 이슈 제목 프롬프트 인젭션으로 Cline 의 Claude 기반 트리아지 봇 장악 → 악성 Cline CLI 2.3.0 배포](https://thehackernews.com/2026/02/cline-cli-230-supply-chain-attack.html) · 통제: least_privilege, human_approval, audit_trail, kill_switch
- 2026-02-05 · INTL · 피해자의 AI 시스템이 뚫림 · press — [OpenClaw(구 Clawdbot/Moltbot) 개인 에이전트 — 노출 인스턴스 수만 대, ClawHub 악성 스킬 수백~1,100개](https://www.theregister.com/2026/02/05/openclaw_skills_marketplace_leaky_security/) · 통제: inventory, least_privilege, vendors
- 2026-01 · INTL · 피해자의 AI 시스템이 뚫림 · press — [Step Finance AI 트레이딩 에이전트 경로로 트레저리 약 $40M 유출(Solana)](https://www.kucoin.com/blog/en-ai-trading-agent-vulnerability-2026-how-a-45m-crypto-security-breach-exposed-protocol-risks) · 통제: least_privilege, human_approval, kill_switch
- 2025-11-13 · US · 공격자가 에이전트 사용 · primary — [GTG-1002 — AI 가 전술 작업 80~90% 를 수행한 사이버 첩보 캠페인(약 30개 대상, 금융기관 포함)](https://www.anthropic.com/news/disrupting-AI-espionage) · 통제: audit_trail, kill_switch
- 2025-11-05 · US · 공격자가 AI 도구 보조 · vendor — [GTIG — 실행 중 LLM 을 호출하는 악성코드 첫 관찰(PROMPTSTEAL 운영·PROMPTFLUX 실험), 북한 UNC1069 암호화폐 탈취 코드 시도](https://cloud.google.com/blog/topics/threat-intelligence/threat-actor-usage-of-ai-tools) · 통제: —
- 2025-10-07 · US · 공격자가 AI 도구 보조 · primary — [OpenAI 2025-10 보고 — 한국어 운영자 묶음이 악성코드·C2 개발과 정부·금융기관 사칭 피싱 초안에 ChatGPT 사용](https://cdn.openai.com/threat-intelligence-reports/7d662b68-952f-4dfd-a2f2-fe55b041cc4a/disrupting-malicious-uses-of-ai-october-2025.pdf) · 통제: —
- 2025-09-25 · US · AI 취약점 공개 · vendor — [Salesforce Agentforce — ForcedLeak(Web-to-Lead 간접 인젭션, 2025-09)·SalesBleed(2026-09-24) CRM 유출 결함](https://noma.security/blog/forcedleak-agent-risks-exposed-in-salesforce-agentforce/) · 통제: least_privilege, human_approval
- 2025-08-27 · US · 공격자가 에이전트 사용 · primary — [Claude Code 로 정찰~협박을 자동화한 데이터 갈취(17개+ 조직) 외 — Anthropic 2025-08 위협 보고](https://www.anthropic.com/news/detecting-countering-misuse-aug-2025) · 통제: audit_trail
- 2025-08-27 · US · 공격자가 에이전트 사용 · vendor — [Nx 'S1ngularity' 공급망 공격 — 피해자 PC 의 Claude Code·Gemini CLI·Amazon Q 를 비밀 탐색에 동원](https://www.wiz.io/blog/s1ngularity-supply-chain-attack) · 통제: least_privilege, audit_trail
- 2025-08-26 · US · 피해자의 AI 시스템이 뚫림 · vendor — [Salesloft Drift(AI 챗 에이전트) OAuth 토큰 탈취로 Salesforce 대량 데이터 절취(UNC6395)](https://cloud.google.com/blog/topics/threat-intelligence/data-theft-salesforce-instances-via-salesloft-drift) · 통제: vendors, unique_id, least_privilege, kill_switch
- 2025-08-20 · US · AI 취약점 공개 · vendor — [Perplexity Comet 에이전트 브라우저 간접 프롬프트 인젭션(Brave) — 이어 Gemini Trifecta(Tenable 09-30)](https://brave.com/blog/comet-prompt-injection/) · 통제: least_privilege
- 2025-08-05 · US · AI 취약점 공개 · primary — [2025 MCP·코딩 에이전트 원격코드실행 공개 묶음 — MCP Inspector, mcp-remote, Cursor, Gemini CLI, GitHub Copilot, GitHub MCP](https://cveawg.mitre.org/api/cve/CVE-2025-54135) · 통제: least_privilege, human_approval
- 2025-07-23 · US · 피해자의 AI 시스템이 뚫림 · primary — [Amazon Q Developer VS Code 확장 1.84.0 에 '시스템 삭제' 지시 프롬프트 삽입(공급망)](https://aws.amazon.com/security/security-bulletins/AWS-2025-015/) · 통제: vendors, human_approval
- 2025-06-11 · US · AI 취약점 공개 · primary — [EchoLeak CVE-2025-32711 — M365 Copilot 제로클릭 프롬프트 인젭션 정보 유출(CVSS 9.3, NVD 7.5)](https://cveawg.mitre.org/api/cve/CVE-2025-32711) · 통제: least_privilege, audit_trail
- 2025-05-05 · US · 피해자의 AI 시스템이 뚫림 · primary — [Langflow(AI 에이전트 빌더) CVE-2025-3248 실제 악용 — CISA KEV 등재, Flodrix 봇넷 배포](https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json) · 통제: inventory, vendors
- 2025-03-18 · US · AI 취약점 공개 · vendor — [Rules File Backdoor — Cursor·GitHub Copilot 규칙 파일의 보이지 않는 유니코드로 AI 생성 코드에 악성 삽입](https://www.pillar.security/blog/new-vulnerability-in-github-copilot-and-cursor-how-hackers-can-weaponize-code-agents) · 통제: vendors, human_approval
