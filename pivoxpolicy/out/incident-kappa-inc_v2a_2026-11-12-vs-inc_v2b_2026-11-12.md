# 사건 × 통제 코딩 일치도 (코드북 v2) — `inc_v2a_2026-11-12` vs `inc_v2b_2026-11-12`

공통 사건 42건 × 통제 7 = 셀 294. 원문이 얇거나 한쪽이 판단을 못 한 사건 3건은 뺐다: `crowdstrike-four-agentic-actors-2026-10`, `echoleak-m365-copilot-2025-06`, `grok-bankr-wallet-prompt-injection-2026-05`.

| 관점 | A 참 | B 참 | 둘 다 참 | 일치율 | κ | Landis–Koch |
|---|---|---|---|---|---|---|
| 원문이 실패를 적은 것만 (stated) | 37 | 41 | 35 | 0.973 | **0.882** | almost perfect |
| 적었거나 추론 (stated ∨ inferred) — v1 과 견주는 값 | 54 | 54 | 52 | 0.986 | **0.955** | almost perfect |
| AI·에이전트 층 (수준 무관) | 40 | 40 | 38 | 0.986 | **0.942** | almost perfect |
| 일반 통제 층 (수준 무관) | 14 | 14 | 13 | 0.993 | **0.925** | almost perfect |

## 통제별 — 둘 다 참 (보수적인 사건 수)

| 통제 | 적은 것만: 둘 다 참 · κ | 적었거나 추론: 둘 다 참 · κ | 그중 AI 층 · 일반 층 (둘 다 참) |
|---|---|---|---|
| inventory | 0 · n/a | 0 · n/a | 0 · 0 |
| vendors | 12 · 0.836 | 14 · 0.896 | 10 · 4 |
| unique_id | 0 · -0.024 | 4 · 1.000 | 2 · 1 |
| least_privilege | 12 · 0.889 | 17 · 1.000 | 13 · 4 |
| human_approval | 7 · 0.919 | 13 · 0.945 | 10 · 3 |
| audit_trail | 2 · 1.000 | 2 · 0.788 | 1 · 1 |
| kill_switch | 2 · 1.000 | 2 · 1.000 | 2 · 0 |

## 불일치 — 적었거나 추론 관점

- `agentsmd-downloads-folder-hijack-2026-10` × vendors — A 만 참 (inferred/agent): Planted AGENTS.md makes the agent install a malicious npm package; malicious-package path per failed_if (borderline: package is payload, not entry route).
- `anthropic-eval-unauthorized-access-2026-07` × human_approval — A 만 참 (inferred/agent): Agent registered accounts and published a real package with no human gate
- `composio-agent-broker-breach-2026-05` × vendors — B 만 참 (stated/agent): Agent tool-integration broker holding customers' OAuth/API credentials was breached and customer connection tokens leaked.
- `composio-agent-broker-breach-2026-05` × audit_trail — B 만 참 (inferred/analog): Remediation list implies security logging was not centralized before; impact beyond listed connections stated as unknown
