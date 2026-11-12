# 통제 × 관할 — 두 층 (코더 `ai_v2a_2026-11-11`)

칸 = **일반 통제 층 / AI·에이전트 층**. 일반 층 0~2 (0 다루지 않음 · 1 자율 · 2 구속력), AI·에이전트 층 0~3 (2 = 구속력 있고 AI 일반 대상 · 3 = 구속력 있고 에이전트 명시). `*` 최고점 문서의 근거 조항이 에이전트를 명시 · `†` 에이전트를 명시한 자율 문서가 따로 있음 · `–` 평가 문서 없음.

| # | 통제 | KR | US | EU | INTL |
|---|---|---|---|---|---|
| 1 | 인벤토리 (Inventory) | 2 / 1 | 2 / 1* | 2 / 0 | 1 / 1 |
| 2 | 공급자 관리 (Vendors / third-party) | 2 / 1* | 2 / 1 | 2 / 0 | 0 / 1* |
| 3 | 고유 식별자 (Unique ID) | 2 / 0 | 1 / 1* | 0 / 0 | 0 / 1* |
| 4 | 최소 권한 (Least privilege) | 2 / 1* | 2 / 1* | 2 / 0 | 0 / 1* |
| 5 | 사람 승인 (Human approval) | 2 / 2† | 2 / 1* | 2 / 2 | 0 / 1* |
| 6 | 감사 기록 (Audit trail) | 2 / 1* | 2 / 1* | 2 / 0 | 1 / 1* |
| 7 | 즉시 중단 (Kill switch) | 2 / 1* | 2 / 1* | 2 / 2 | 0 / 1* |

## 간극 — 일반 통제는 구속력(2)인데 AI·에이전트 층은 2 미만: 16칸

- KR · 1 인벤토리: 일반 **2** ← `kr-efsr-art13` · AI·에이전트 **1** ← `kr-fsc-ai-guidelines-2026-06`
- KR · 2 공급자 관리: 일반 **2** ← `kr-outsourcing-regulation` · AI·에이전트 **1*** ← `kr-fsc-ai-guidelines-2026-06`, `kr-fsi-agent-criteria-2026-10`
- KR · 3 고유 식별자: 일반 **2** ← `kr-efsr-art13` · AI·에이전트 **0** ← –
- KR · 4 최소 권한: 일반 **2** ← `kr-efsr-art13` · AI·에이전트 **1*** ← `kr-fsc-ai-guidelines-2026-06`, `kr-fsc-frontier-ai-guide-2026-07`, `kr-fsi-agent-criteria-2026-10`
- KR · 6 감사 기록: 일반 **2** ← `kr-efsr-art13` · AI·에이전트 **1*** ← `kr-fsc-ai-guidelines-2026-06`, `kr-fsi-agent-criteria-2026-10`
- KR · 7 즉시 중단: 일반 **2** ← `kr-efsr-art13` · AI·에이전트 **1*** ← `kr-fsc-ai-guidelines-2026-06`, `kr-fsc-frontier-ai-guide-2026-07`, `kr-fsi-agent-criteria-2026-10`
- US · 1 인벤토리: 일반 **2** ← `us-cisa-bod-26-04`, `us-nydfs-part500` · AI·에이전트 **1*** ← `us-nist-ir-8596-cyber-ai-profile`, `us-nydfs-letter-2024-10-16`, `us-treasury-fs-ai-rmf-2026-02`
- US · 2 공급자 관리: 일반 **2** ← `us-cisa-bod-26-04`, `us-nydfs-part500` · AI·에이전트 **1** ← `us-nist-ir-8596-cyber-ai-profile`, `us-nydfs-letter-2024-10-16`, `us-treasury-fs-ai-rmf-2026-02`
- US · 4 최소 권한: 일반 **2** ← `us-nydfs-part500` · AI·에이전트 **1*** ← `us-nist-ir-8596-cyber-ai-profile`, `us-nist-nccoe-agent-identity-2026-02`
- US · 5 사람 승인: 일반 **2** ← `us-nydfs-part500` · AI·에이전트 **1*** ← `us-nist-ir-8596-cyber-ai-profile`, `us-nist-nccoe-agent-identity-2026-02`, `us-nydfs-letters-2026-05-21`
- US · 6 감사 기록: 일반 **2** ← `us-nydfs-part500` · AI·에이전트 **1*** ← `us-nist-ir-8596-cyber-ai-profile`, `us-nist-nccoe-agent-identity-2026-02`, `us-treasury-fs-ai-rmf-2026-02`
- US · 7 즉시 중단: 일반 **2** ← `us-cisa-bod-26-04`, `us-nydfs-part500` · AI·에이전트 **1*** ← `us-nist-ir-8596-cyber-ai-profile`, `us-nist-nccoe-agent-identity-2026-02`, `us-treasury-fs-ai-rmf-2026-02`
- EU · 1 인벤토리: 일반 **2** ← `eu-dora-2022-2554` · AI·에이전트 **0** ← –
- EU · 2 공급자 관리: 일반 **2** ← `eu-dora-2022-2554` · AI·에이전트 **0** ← –
- EU · 4 최소 권한: 일반 **2** ← `eu-dora-2022-2554` · AI·에이전트 **0** ← –
- EU · 6 감사 기록: 일반 **2** ← `eu-dora-2022-2554` · AI·에이전트 **0** ← –

구속력 있는 문서가 에이전트를 명시해 요구하는 칸(점수 3): **0**
