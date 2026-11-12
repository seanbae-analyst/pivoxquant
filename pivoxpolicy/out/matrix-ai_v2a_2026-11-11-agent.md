# 통제 × 관할 구속력 매트릭스 — 코더 `ai_v2a_2026-11-11` · AI·에이전트 적용 층

점수: 0 다루지 않음 · 1 자율 · 2 구속력(AI 일반) · 3 구속력+에이전트 명시 · `–` 평가 문서 없음 · `?` 코딩 필요

`*` 최고점 문서가 에이전트를 명시 · `†` 자율 문서 중 에이전트를 명시한 것이 따로 있음

| # | 통제 | KR | US | EU | INTL |
|---|---|---|---|---|---|
| 1 | 인벤토리 (Inventory) | 1 | 1* | 0 | 1 |
| 2 | 공급자 관리 (Vendors / third-party) | 1* | 1 | 0 | 1* |
| 3 | 고유 식별자 (Unique ID) | 0 | 1* | 0 | 1* |
| 4 | 최소 권한 (Least privilege) | 1* | 1* | 0 | 1* |
| 5 | 사람 승인 (Human approval) | 2† | 1* | 2 | 1* |
| 6 | 감사 기록 (Audit trail) | 1* | 1* | 0 | 1* |
| 7 | 즉시 중단 (Kill switch) | 1* | 1* | 2 | 1* |

## 셀별 근거 문서

### KR

- 1 인벤토리: **1** ← `kr-fsc-ai-guidelines-2026-06`
- 2 공급자 관리: **1*** ← `kr-fsc-ai-guidelines-2026-06`, `kr-fsi-agent-criteria-2026-10` · 에이전트 명시 자율문서: `kr-fsi-agent-criteria-2026-10`
- 3 고유 식별자: **0** ← `kr-ai-basic-act`, `kr-efsr-art13`, `kr-efsr-art37-2`, `kr-fsc-ai-guidelines-2026-06`, `kr-fsc-frontier-ai-guide-2026-07`, `kr-fsi-agent-criteria-2026-10`, `kr-fss-fsi-pentest-standards-2026`, `kr-outsourcing-regulation`
- 4 최소 권한: **1*** ← `kr-fsc-ai-guidelines-2026-06`, `kr-fsc-frontier-ai-guide-2026-07`, `kr-fsi-agent-criteria-2026-10` · 에이전트 명시 자율문서: `kr-fsi-agent-criteria-2026-10`
- 5 사람 승인: **2†** ← `kr-ai-basic-act` · 에이전트 명시 자율문서: `kr-fsi-agent-criteria-2026-10`
- 6 감사 기록: **1*** ← `kr-fsc-ai-guidelines-2026-06`, `kr-fsi-agent-criteria-2026-10` · 에이전트 명시 자율문서: `kr-fsi-agent-criteria-2026-10`
- 7 즉시 중단: **1*** ← `kr-fsc-ai-guidelines-2026-06`, `kr-fsc-frontier-ai-guide-2026-07`, `kr-fsi-agent-criteria-2026-10` · 에이전트 명시 자율문서: `kr-fsi-agent-criteria-2026-10`

### US

- 1 인벤토리: **1*** ← `us-nist-ir-8596-cyber-ai-profile`, `us-nydfs-letter-2024-10-16`, `us-treasury-fs-ai-rmf-2026-02` · 에이전트 명시 자율문서: `us-nist-ir-8596-cyber-ai-profile`
- 2 공급자 관리: **1** ← `us-nist-ir-8596-cyber-ai-profile`, `us-nydfs-letter-2024-10-16`, `us-treasury-fs-ai-rmf-2026-02`
- 3 고유 식별자: **1*** ← `us-nist-ir-8596-cyber-ai-profile`, `us-nist-nccoe-agent-identity-2026-02` · 에이전트 명시 자율문서: `us-nist-ir-8596-cyber-ai-profile`, `us-nist-nccoe-agent-identity-2026-02`
- 4 최소 권한: **1*** ← `us-nist-ir-8596-cyber-ai-profile`, `us-nist-nccoe-agent-identity-2026-02` · 에이전트 명시 자율문서: `us-nist-ir-8596-cyber-ai-profile`, `us-nist-nccoe-agent-identity-2026-02`
- 5 사람 승인: **1*** ← `us-nist-ir-8596-cyber-ai-profile`, `us-nist-nccoe-agent-identity-2026-02`, `us-nydfs-letters-2026-05-21`, `us-treasury-fs-ai-rmf-2026-02` · 에이전트 명시 자율문서: `us-nist-ir-8596-cyber-ai-profile`, `us-nist-nccoe-agent-identity-2026-02`
- 6 감사 기록: **1*** ← `us-nist-ir-8596-cyber-ai-profile`, `us-nist-nccoe-agent-identity-2026-02`, `us-treasury-fs-ai-rmf-2026-02` · 에이전트 명시 자율문서: `us-nist-nccoe-agent-identity-2026-02`
- 7 즉시 중단: **1*** ← `us-nist-ir-8596-cyber-ai-profile`, `us-nist-nccoe-agent-identity-2026-02`, `us-treasury-fs-ai-rmf-2026-02` · 에이전트 명시 자율문서: `us-nist-ir-8596-cyber-ai-profile`, `us-nist-nccoe-agent-identity-2026-02`

### EU

- 1 인벤토리: **0** ← `eu-ai-act-art14`
- 2 공급자 관리: **0** ← `eu-ai-act-art14`
- 3 고유 식별자: **0** ← `eu-ai-act-art14`
- 4 최소 권한: **0** ← `eu-ai-act-art14`
- 5 사람 승인: **2** ← `eu-ai-act-art14`
- 6 감사 기록: **0** ← `eu-ai-act-art14`
- 7 즉시 중단: **2** ← `eu-ai-act-art14`

### INTL

- 1 인벤토리: **1** ← `intl-fsb-ai-sound-practices-2026-10`
- 2 공급자 관리: **1*** ← `intl-fsb-ai-sound-practices-2026-10` · 에이전트 명시 자율문서: `intl-fsb-ai-sound-practices-2026-10`
- 3 고유 식별자: **1*** ← `intl-fsb-ai-sound-practices-2026-10` · 에이전트 명시 자율문서: `intl-fsb-ai-sound-practices-2026-10`
- 4 최소 권한: **1*** ← `intl-fsb-ai-sound-practices-2026-10` · 에이전트 명시 자율문서: `intl-fsb-ai-sound-practices-2026-10`
- 5 사람 승인: **1*** ← `intl-fsb-ai-sound-practices-2026-10` · 에이전트 명시 자율문서: `intl-fsb-ai-sound-practices-2026-10`
- 6 감사 기록: **1*** ← `intl-fsb-ai-sound-practices-2026-10` · 에이전트 명시 자율문서: `intl-fsb-ai-sound-practices-2026-10`
- 7 즉시 중단: **1*** ← `intl-fsb-ai-sound-practices-2026-10` · 에이전트 명시 자율문서: `intl-fsb-ai-sound-practices-2026-10`
