# 사건 × 통제 코딩 일치도 — 1차(finder) vs `inc_v2a_2026-11-12`

공통 사건 43건 × 통제 7 = 셀 301. 관측 일치율 0.751 · κ 0.332 (fair)

'둘 다 참' 은 두 코더가 모두 이 통제의 실패를 본 사건 수 — 코더에 덜 기대는 보수적인 숫자다.

| 통제 | 1차 참 | 2차 참 | 둘 다 참 | 일치율 | κ |
|---|---|---|---|---|---|
| inventory | 7 | 0 | 0 | 0.837 | 0.000 |
| vendors | 10 | 15 | 8 | 0.791 | 0.501 |
| unique_id | 9 | 4 | 2 | 0.791 | 0.205 |
| least_privilege | 21 | 17 | 14 | 0.767 | 0.533 |
| human_approval | 11 | 14 | 8 | 0.791 | 0.495 |
| audit_trail | 19 | 2 | 1 | 0.558 | 0.012 |
| kill_switch | 14 | 2 | 2 | 0.721 | 0.184 |

한쪽에만 있는 사건 — 1차만 2 · 2차만 0 (κ 에서 뺐다)

## 불일치 75칸

- `aepd-first-ai-agent-breach-notification-2026-09` × audit_trail — 1차만 참
- `agentic-browser-prompt-injection-2025-08` × unique_id — 2차만 참
- `agentic-browser-prompt-injection-2025-08` × human_approval — 2차만 참
- `agentsmd-downloads-folder-hijack-2026-10` × vendors — 2차만 참
- `amazon-q-extension-prompt-tamper-2025-07` × least_privilege — 2차만 참
- `anthropic-agentic-extortion-2025-08` × audit_trail — 1차만 참
- `anthropic-eval-unauthorized-access-2026-07` × vendors — 2차만 참
- `anthropic-eval-unauthorized-access-2026-07` × human_approval — 2차만 참
- `anthropic-eval-unauthorized-access-2026-07` × audit_trail — 1차만 참
- `anthropic-eval-unauthorized-access-2026-07` × kill_switch — 1차만 참
- `anthropic-gtg-1002-2025-11` × audit_trail — 1차만 참
- `anthropic-gtg-1002-2025-11` × kill_switch — 1차만 참
- `anthropic-threat-report-2026-09` × vendors — 2차만 참
- `anthropic-threat-report-2026-09` × least_privilege — 2차만 참
- `cairn-exposed-agent-panels-2026-10` × inventory — 1차만 참
- `clinejection-cline-triage-agent-2026-02` × vendors — 2차만 참
- `clinejection-cline-triage-agent-2026-02` × audit_trail — 1차만 참
- `clinejection-cline-triage-agent-2026-02` × kill_switch — 1차만 참
- `composio-agent-broker-breach-2026-05` × vendors — 1차만 참
- `composio-agent-broker-breach-2026-05` × unique_id — 2차만 참
- `crowdstrike-four-agentic-actors-2026-10` × audit_trail — 1차만 참
- `datadog-artex-aws-financial-data-2026-11` × inventory — 1차만 참
- `datadog-artex-aws-financial-data-2026-11` × least_privilege — 1차만 참
- `datadog-artex-aws-financial-data-2026-11` × audit_trail — 1차만 참
- `datadog-artex-aws-financial-data-2026-11` × kill_switch — 1차만 참
- `divd-zammad-zero-days-agent-2026-09` × audit_trail — 1차만 참
- `divd-zammad-zero-days-agent-2026-09` × kill_switch — 1차만 참
- `gambit-ai-agents-600k-cards-2026-09` × inventory — 1차만 참
- `gambit-ai-agents-600k-cards-2026-09` × audit_trail — 1차만 참
- `greynoise-papercut-agent-campaign-2026-09` × least_privilege — 2차만 참
- `greynoise-papercut-agent-campaign-2026-09` × audit_trail — 1차만 참
- `greynoise-papercut-agent-campaign-2026-09` × kill_switch — 1차만 참
- `hexagonalrodent-nk-web3-ai-tooling-2026-04` × least_privilege — 1차만 참
- `hexagonalrodent-nk-web3-ai-tooling-2026-04` × human_approval — 2차만 참
- `hugging-face-openai-eval-agent-breach-2026-07` × human_approval — 1차만 참
- `hugging-face-openai-eval-agent-breach-2026-07` × audit_trail — 1차만 참
- `hugging-face-openai-eval-agent-breach-2026-07` × kill_switch — 1차만 참
- `infostealers-target-ai-agent-tokens-2026-09` × unique_id — 1차만 참
- `infostealers-target-ai-agent-tokens-2026-09` × audit_trail — 1차만 참
- `infostealers-target-ai-agent-tokens-2026-09` × kill_switch — 1차만 참
- `kr-fin-chain-intrusions-2026-09` × inventory — 1차만 참
- `kr-fin-chain-intrusions-2026-09` × least_privilege — 1차만 참
- `kr-fin-chain-intrusions-2026-09` × audit_trail — 1차만 참
- `kr-fsi-assessment-system-breach-2026-11` × least_privilege — 1차만 참
- `kr-fsi-assessment-system-breach-2026-11` × audit_trail — 1차만 참
- `langflow-exploited-in-the-wild-kev-2025-05` × inventory — 1차만 참
- `langflow-exploited-in-the-wild-kev-2025-05` × vendors — 1차만 참
- `litellm-supply-chain-compromise-2026-10` × human_approval — 2차만 참
- `llmjacking-autonomous-agent-2026-10` × inventory — 1차만 참
- `llmjacking-autonomous-agent-2026-10` × unique_id — 1차만 참
- `llmjacking-autonomous-agent-2026-10` × kill_switch — 1차만 참
- `mythos-preview-unauthorized-access-2026-04` × unique_id — 1차만 참
- `nx-s1ngularity-ai-cli-abuse-2025-08` × vendors — 2차만 참
- `nx-s1ngularity-ai-cli-abuse-2025-08` × human_approval — 2차만 참
- `nx-s1ngularity-ai-cli-abuse-2025-08` × audit_trail — 1차만 참
- `openai-funded-test-wallet-2026-10` × audit_trail — 1차만 참
- `openclaw-exposed-agents-malicious-skills-2026-02` × inventory — 1차만 참
- `openclaw-exposed-agents-malicious-skills-2026-02` × human_approval — 2차만 참
- `pillar-rules-file-backdoor-2025-03` × audit_trail — 2차만 참
- `salesforce-agentforce-forcedleak-salesbleed-2025-09` × vendors — 2차만 참
- `salesloft-drift-oauth-theft-2025-08` × unique_id — 1차만 참
- `salesloft-drift-oauth-theft-2025-08` × least_privilege — 1차만 참
- `salesloft-drift-oauth-theft-2025-08` × kill_switch — 1차만 참
- `step-finance-ai-trading-agent-drain-2026-01` × kill_switch — 1차만 참
- `storm-0940-artex-connectwise-2026-10` × unique_id — 1차만 참
- `storm-0940-artex-connectwise-2026-10` × least_privilege — 1차만 참
- `storm-0940-artex-connectwise-2026-10` × kill_switch — 1차만 참
- `taiwan-gov-near-autonomous-agents-2026-08` × unique_id — 1차만 참
- `taiwan-gov-near-autonomous-agents-2026-08` × audit_trail — 1차만 참
- `thailand-mof-hermes-agent-2026-07` × human_approval — 1차만 참
- `thailand-mof-hermes-agent-2026-07` × audit_trail — 1차만 참
- `unit42-bugster-hermes-deepseek-2026-10` × least_privilege — 1차만 참
- `unit42-bugster-hermes-deepseek-2026-10` × human_approval — 1차만 참
- `zenity-agentcorruption-bedrock-agentcore-2026-10` × vendors — 2차만 참
- `zenity-agentcorruption-bedrock-agentcore-2026-10` × unique_id — 1차만 참
