# 사건 × 통제 — 조정본 `consensus_2026-11-12` (`inc_v2a_2026-11-12` + `inc_v2b_2026-11-12`)

원문으로 판단할 수 있었던 사건 **42**건. 칸 = 이 통제가 실패했다고 본 사건 수.

| # | 통제 | 사건 | 원문이 적음 | 추론 | AI 층 | 일반 층 | 1차 출처 | 벤더 | 보도 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 인벤토리 | **0** | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2 | 공급자 관리 | **15** | 15 | 0 | 11 | 4 | 5 | 7 | 3 |
| 3 | 고유 식별자 | **4** | 1 | 3 | 2 | 2 | 2 | 1 | 1 |
| 4 | 최소 권한 | **17** | 13 | 4 | 13 | 4 | 8 | 5 | 4 |
| 5 | 사람 승인 | **13** | 7 | 6 | 10 | 3 | 4 | 5 | 4 |
| 6 | 감사 기록 | **2** | 2 | 0 | 1 | 1 | 1 | 1 | 0 |
| 7 | 즉시 중단 | **2** | 2 | 0 | 2 | 0 | 2 | 0 | 0 |

## 판정 18칸 — 두 코더가 갈린 칸

- `agentic-browser-prompt-injection-2025-08` × unique_id → **inferred/agent** (`inc_v2a_2026-11-12` 쪽): 두 인용 모두 에이전트가 사용자 세션으로 움직인다는 사실이다 — '구별·귀속할 수 없었다' 를 원문이 이름 붙이지 않았다 → inferred.
- `agentsmd-downloads-folder-hijack-2026-10` × vendors → **false** (`inc_v2b_2026-11-12` 쪽): 들어온 경로는 다운로드 폴더에 심은 AGENTS.md 다. 악성 npm 패키지는 그 결과로 깔린 페이로드라 피해 쪽의 제3자 관계가 경로가 아니다(v2.2 failed_if 첫 줄).
- `agentsmd-downloads-folder-hijack-2026-10` × human_approval → **inferred/agent** (`inc_v2a_2026-11-12` 쪽): 인용은 '설정을 바꾸고 패키지를 깔았다' 는 사실 — 승인이 없었다는 말은 원문에 없다 → inferred.
- `anthropic-eval-unauthorized-access-2026-07` × least_privilege → **stated/agent** (`inc_v2b_2026-11-12` 쪽): 'a misconfiguration left the machines … with live internet access' — 원문이 접근 범위의 오설정을 사실로 적었다 → stated.
- `anthropic-eval-unauthorized-access-2026-07` × human_approval → **false** (`inc_v2b_2026-11-12` 쪽): 원문은 계정 등록·업로드를 적을 뿐 승인 단계가 있어야 했다거나 우회됐다고 적지 않는다. 언급이 없다는 데서 '승인 없음' 을 끌어내는 것은 추론이 아니라 일반론(levels.inferred).
- `composio-agent-broker-breach-2026-05` × vendors → **true (stated/agent)** (`inc_v2b_2026-11-12` 쪽): 공급자에게 맡긴 기능(에이전트 도구 연동 · 고객 OAuth/API 자격증명 보관)이 침해돼 고객 자격증명이 노출됐다고 원문이 적었다 — v2.2 failed_if 셋째 줄. 하류(고객)로 닿은 서술이 있어 false_if 에 걸리지 않는다.
- `composio-agent-broker-breach-2026-05` × unique_id → **inferred/analog** (`inc_v2a_2026-11-12` 쪽): 공유 정적 비밀은 Composio 내부 서비스 사이의 것 — 대상이 일반 시스템이라 analog.
- `composio-agent-broker-breach-2026-05` × audit_trail → **false** (`inc_v2a_2026-11-12` 쪽): '로그를 중앙화했다' 는 사후 개선 목록이다. 이전에 기록이 없었다는 서술이 아니다 — R4 · levels.inferred(일반론 금지).
- `crowdstrike-four-agentic-actors-2026-10` × inventory → **null (thin)** (`inc_v2b_2026-11-12` 쪽): 추출한 본문이 블로그 사이드바 위주라 사례 서술이 거의 없다 — B 의 thin 판정을 따른다(R1). 원문 재추출 대상(inbox.md).
- `crowdstrike-four-agentic-actors-2026-10` × unique_id → **null (thin)** (`inc_v2b_2026-11-12` 쪽): 추출한 본문이 블로그 사이드바 위주라 사례 서술이 거의 없다 — B 의 thin 판정을 따른다(R1). 원문 재추출 대상(inbox.md).
- `crowdstrike-four-agentic-actors-2026-10` × least_privilege → **null (thin)** (`inc_v2b_2026-11-12` 쪽): 추출한 본문이 블로그 사이드바 위주라 사례 서술이 거의 없다 — B 의 thin 판정을 따른다(R1). 원문 재추출 대상(inbox.md).
- `crowdstrike-four-agentic-actors-2026-10` × human_approval → **null (thin)** (`inc_v2b_2026-11-12` 쪽): 추출한 본문이 블로그 사이드바 위주라 사례 서술이 거의 없다 — B 의 thin 판정을 따른다(R1). 원문 재추출 대상(inbox.md).
- `crowdstrike-four-agentic-actors-2026-10` × audit_trail → **null (thin)** (`inc_v2b_2026-11-12` 쪽): 추출한 본문이 블로그 사이드바 위주라 사례 서술이 거의 없다 — B 의 thin 판정을 따른다(R1). 원문 재추출 대상(inbox.md).
- `crowdstrike-four-agentic-actors-2026-10` × kill_switch → **null (thin)** (`inc_v2b_2026-11-12` 쪽): 추출한 본문이 블로그 사이드바 위주라 사례 서술이 거의 없다 — B 의 thin 판정을 따른다(R1). 원문 재추출 대상(inbox.md).
- `kr-fsi-assessment-system-breach-2026-11` × unique_id → **stated/analog** (`inc_v2a_2026-11-12` 쪽): '가짜 금감원 계정 만들어 침투' — failed_if '위조·사칭 계정이 정상으로 통했다' 를 원문이 그대로 적었다 → stated. 단 인용이 관련 기사 제목이다(inbox.md).
- `mcp-coding-agent-rce-disclosures-2025` × least_privilege → **inferred/agent** (`inc_v2a_2026-11-12` 쪽): 인용이 적는 것은 승인 없는 설정 쓰기·RCE 다. 권한 범위를 이름 붙이지 않았다 → 최소 권한은 inferred (사람 승인은 두 팀 모두 stated).
- `pillar-rules-file-backdoor-2025-03` × vendors → **stated/agent** (`inc_v2b_2026-11-12` 쪽): 'one compromised file can lead to widespread vulnerabilities' — 공유되는 규칙 파일이 변조된 공급 경로라는 것을 원문이 적었다 → stated.
- `salesforce-agentforce-forcedleak-salesbleed-2025-09` × vendors → **stated/agent** (`inc_v2a_2026-11-12` 쪽): 'whitelisted but had expired … creating a trusted exfiltration channel' — 공급자 운영 플랫폼의 결함이 노출 경로였다고 원문이 적었다(failed_if 셋째 줄) → stated.
