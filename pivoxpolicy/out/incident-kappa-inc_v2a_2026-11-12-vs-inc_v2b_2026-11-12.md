# 사건 × 통제 코딩 일치도 (코드북 v2) — `inc_v2a_2026-11-12` vs `inc_v2b_2026-11-12`

공통 사건 42건 × 통제 7 = 셀 294. 원문이 얇거나 한쪽이 판단을 못 한 사건 3건은 뺐다: `crowdstrike-four-agentic-actors-2026-10`, `echoleak-m365-copilot-2025-06`, `grok-bankr-wallet-prompt-injection-2026-05`.

| 관점 | A 참 | B 참 | 둘 다 참 | 일치율 | κ | Landis–Koch |
|---|---|---|---|---|---|---|
| 원문이 실패를 적은 것만 (stated) | 38 | 43 | 36 | 0.969 | **0.871** | almost perfect |
| 적었거나 추론 (stated ∨ inferred) — v1 과 견주는 값 | 53 | 56 | 52 | 0.983 | **0.944** | almost perfect |
| AI·에이전트 층 (수준 무관) | 37 | 40 | 36 | 0.983 | **0.925** | almost perfect |
| 일반 통제 층 (수준 무관) | 16 | 16 | 14 | 0.986 | **0.868** | almost perfect |

## 통제별 — 둘 다 참 (보수적인 사건 수)

| 통제 | 적은 것만: 둘 다 참 · κ | 적었거나 추론: 둘 다 참 · κ | 그중 AI 층 · 일반 층 (둘 다 참) |
|---|---|---|---|
| inventory | 0 · n/a | 0 · n/a | 0 · 0 |
| vendors | 13 · 0.793 | 14 · 0.847 | 8 · 5 |
| unique_id | 0 · -0.024 | 4 · 1.000 | 2 · 1 |
| least_privilege | 12 · 0.889 | 17 · 1.000 | 13 · 4 |
| human_approval | 7 · 0.919 | 13 · 0.945 | 10 · 3 |
| audit_trail | 2 · 1.000 | 2 · 0.788 | 1 · 1 |
| kill_switch | 2 · 1.000 | 2 · 1.000 | 2 · 0 |

## 불일치 — 적었거나 추론 관점

- `anthropic-eval-unauthorized-access-2026-07` × human_approval — A 만 참 (inferred/agent): Agent registered accounts and published a real package with no human gate
- `composio-agent-broker-breach-2026-05` × vendors — B 만 참 (stated/agent): Customers’ agent tool credentials were exposed via the third-party tool broker
- `composio-agent-broker-breach-2026-05` × audit_trail — B 만 참 (inferred/analog): Remediation list implies security logging was not centralized before; impact beyond listed connections stated as unknown
- `greynoise-papercut-agent-campaign-2026-09` × vendors — B 만 참 (stated/analog): Victims were breached through exploitable flaws (two CVEs) in third-party PaperCut software
- `langflow-exploited-in-the-wild-kev-2025-05` × vendors — B 만 참 (stated/agent): CVE-2025-3248 is a missing-auth flaw in a third-party AI agent builder component that deployers ran
