# 통제 × 관할 구속력 매트릭스 — 코더 `deck_2026-11-01`

점수: 0 다루지 않음 · 1 자율 · 2 구속력(에이전트 미명시) · 3 구속력+에이전트 명시 · `–` 평가 문서 없음 · `?` 코딩 필요

`*` 최고점 문서가 에이전트를 명시 · `†` 자율 문서 중 에이전트를 명시한 것이 따로 있음

| # | 통제 | KR | US | EU | INTL |
|---|---|---|---|---|---|
| 1 | 인벤토리 (Inventory) | 0 | 2 | ? (1 코딩 필요) | 1 |
| 2 | 공급자 관리 (Vendors / third-party) | 2 | 2 | ? (1 코딩 필요) | 1* |
| 3 | 고유 식별자 (Unique ID) | 2 | 1* | ? (1 코딩 필요) | 1* |
| 4 | 최소 권한 (Least privilege) | 2† | 2 | ? (1 코딩 필요) | 1* |
| 5 | 사람 승인 (Human approval) | 1* | 0 | ? (1 코딩 필요) | 1* |
| 6 | 감사 기록 (Audit trail) | 2† | 2† | ? (1 코딩 필요) | 1* |
| 7 | 즉시 중단 (Kill switch) | 1* | 0 | 2 | 1* |

## 셀별 근거 문서

### KR

- 1 인벤토리: **0** ← `kr-efsr-art13`
- 2 공급자 관리: **2** ← `kr-outsourcing-regulation`
- 3 고유 식별자: **2** ← `kr-efsr-art13`
- 4 최소 권한: **2†** ← `kr-efsr-art13` · 에이전트 명시 자율문서: `kr-fsi-agent-criteria-2026-10`
- 5 사람 승인: **1*** ← `kr-fsc-ai-guidelines-2026-06`, `kr-fsi-agent-criteria-2026-10` · 에이전트 명시 자율문서: `kr-fsi-agent-criteria-2026-10`
- 6 감사 기록: **2†** ← `kr-efsr-art13` · 에이전트 명시 자율문서: `kr-fsi-agent-criteria-2026-10`
- 7 즉시 중단: **1*** ← `kr-fsi-agent-criteria-2026-10` · 에이전트 명시 자율문서: `kr-fsi-agent-criteria-2026-10`

### US

- 1 인벤토리: **2** ← `us-nydfs-part500`
- 2 공급자 관리: **2** ← `us-nydfs-part500`
- 3 고유 식별자: **1*** ← `us-nist-csf-2-0`, `us-nist-nccoe-agent-identity-2026-02` · 에이전트 명시 자율문서: `us-nist-nccoe-agent-identity-2026-02`
- 4 최소 권한: **2** ← `us-nydfs-part500`
- 5 사람 승인: **0** ← `us-nydfs-part500`
- 6 감사 기록: **2†** ← `us-nydfs-part500` · 에이전트 명시 자율문서: `us-nist-nccoe-agent-identity-2026-02`
- 7 즉시 중단: **0** ← `us-nydfs-part500`

### EU

- 7 즉시 중단: **2** ← `eu-ai-act-art14`

### INTL

- 1 인벤토리: **1** ← `intl-iso-iec-27001-2022`
- 2 공급자 관리: **1*** ← `intl-fsb-ai-sound-practices-2026-10`, `intl-fsb-ai-sound-practices-consultation-2026-06`, `intl-iso-iec-27001-2022` · 에이전트 명시 자율문서: `intl-fsb-ai-sound-practices-2026-10`, `intl-fsb-ai-sound-practices-consultation-2026-06`
- 3 고유 식별자: **1*** ← `intl-fsb-ai-sound-practices-consultation-2026-06`, `intl-iso-iec-27001-2022` · 에이전트 명시 자율문서: `intl-fsb-ai-sound-practices-consultation-2026-06`
- 4 최소 권한: **1*** ← `intl-fsb-ai-sound-practices-2026-10`, `intl-fsb-ai-sound-practices-consultation-2026-06`, `intl-iso-iec-27001-2022` · 에이전트 명시 자율문서: `intl-fsb-ai-sound-practices-2026-10`, `intl-fsb-ai-sound-practices-consultation-2026-06`
- 5 사람 승인: **1*** ← `intl-fsb-ai-sound-practices-2026-10` · 에이전트 명시 자율문서: `intl-fsb-ai-sound-practices-2026-10`
- 6 감사 기록: **1*** ← `intl-fsb-ai-sound-practices-2026-10`, `intl-fsb-ai-sound-practices-consultation-2026-06`, `intl-iso-iec-27001-2022` · 에이전트 명시 자율문서: `intl-fsb-ai-sound-practices-2026-10`, `intl-fsb-ai-sound-practices-consultation-2026-06`
- 7 즉시 중단: **1*** ← `intl-fsb-ai-sound-practices-2026-10` · 에이전트 명시 자율문서: `intl-fsb-ai-sound-practices-2026-10`
